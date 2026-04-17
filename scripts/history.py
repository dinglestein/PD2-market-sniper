from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import (
    FILTER_EMPTY_WARNING_DAYS,
    OFFER_HISTORY_FILE,
    RECENT_DEAL_HISTORY_LIMIT,
    RECENT_OFFER_HISTORY_LIMIT,
    RECENT_SCAN_HISTORY_LIMIT,
    SEEN_EXPIRY_HOURS,
    SEEN_FILE,
    STATE_FILE,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(default)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


DEFAULT_STATE = {
    "created_at": to_iso(),
    "daily_scan": {"date": None, "count": 0},
    "rotation_offset": 0,
    "recent_scans": [],
    "recent_deals": [],
    "filters": {},
    "last_scan_at": None,
    "last_economy_refresh_at": None,
    "pending_confirmation": None,
}


class SeenStore:
    def __init__(self, path: Path = SEEN_FILE, expiry_hours: int = SEEN_EXPIRY_HOURS):
        self.path = path
        self.expiry = timedelta(hours=expiry_hours)
        self._data = read_json(path, {"items": {}})
        self.cleanup()

    @property
    def items(self) -> dict[str, dict[str, Any]]:
        return self._data.setdefault("items", {})

    def cleanup(self) -> int:
        cutoff = utc_now() - self.expiry
        removed = []
        for key, payload in list(self.items.items()):
            seen_at = parse_iso(payload.get("seen_at"))
            if seen_at is None or seen_at < cutoff:
                removed.append(key)
                self.items.pop(key, None)
        if removed:
            self.save()
        return len(removed)

    def make_key(self, item: dict[str, Any]) -> str:
        parts = [
            str(item.get("listing_id") or ""),
            str(item.get("item_name") or item.get("item") or ""),
            str(item.get("price_hr") or item.get("price") or ""),
            str(item.get("seller_name") or item.get("seller") or ""),
            str(item.get("listing_url") or item.get("url") or ""),
        ]
        return "|".join(parts)

    def is_new(self, item: dict[str, Any]) -> bool:
        key = self.make_key(item)
        return key not in self.items

    def mark_seen(self, item: dict[str, Any]) -> None:
        key = self.make_key(item)
        self.items[key] = {
            "seen_at": to_iso(),
            "filter_id": item.get("filter_id"),
            "filter_name": item.get("filter_name") or item.get("filter"),
            "item_name": item.get("item_name") or item.get("item"),
            "seller_name": item.get("seller_name") or item.get("seller"),
            "price_hr": item.get("price_hr") or item.get("price"),
            "listing_url": item.get("listing_url") or item.get("url"),
        }

    def save(self) -> None:
        write_json(self.path, self._data)


class OfferHistory:
    def __init__(self, path: Path = OFFER_HISTORY_FILE):
        self.path = path
        self.data = read_json(path, {"offers": []})

    @property
    def offers(self) -> list[dict[str, Any]]:
        return self.data.setdefault("offers", [])

    def record_offer(self, *, item: dict[str, Any], amount_hr: float, status: str, filter_name: str | None = None, note: str | None = None) -> dict[str, Any]:
        entry = {
            "timestamp": to_iso(),
            "status": status,
            "amount_hr": amount_hr,
            "item_name": item.get("item_name") or item.get("item"),
            "seller_name": item.get("seller_name") or item.get("seller"),
            "listing_id": item.get("listing_id"),
            "listing_url": item.get("listing_url") or item.get("url"),
            "filter_id": item.get("filter_id"),
            "filter_name": filter_name or item.get("filter_name") or item.get("filter"),
            "price_hr": item.get("price_hr") or item.get("price"),
            "note": note,
        }
        self.offers.append(entry)
        self.data["offers"] = self.offers[-RECENT_OFFER_HISTORY_LIMIT:]
        self.save()
        return entry

    def recent_for_listing(self, listing_id: str | None = None, listing_url: str | None = None) -> list[dict[str, Any]]:
        matches = []
        for offer in reversed(self.offers):
            if listing_id and offer.get("listing_id") == listing_id:
                matches.append(offer)
            elif listing_url and offer.get("listing_url") == listing_url:
                matches.append(offer)
        return matches

    def stats(self) -> dict[str, Any]:
        offers = self.offers
        status_counts: dict[str, int] = {}
        for offer in offers:
            status = offer.get("status") or "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
        return {"total": len(offers), "status_counts": status_counts, "recent": offers[-20:]}

    def save(self) -> None:
        write_json(self.path, self.data)


class StateStore:
    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self.data = read_json(path, DEFAULT_STATE)
        for key, value in DEFAULT_STATE.items():
            self.data.setdefault(key, deepcopy(value))

    def _today_key(self) -> str:
        return utc_now().date().isoformat()

    def get_daily_count(self) -> int:
        scan_state = self.data.setdefault("daily_scan", {"date": self._today_key(), "count": 0})
        if scan_state.get("date") != self._today_key():
            scan_state["date"] = self._today_key()
            scan_state["count"] = 0
        return int(scan_state.get("count", 0))

    def increment_daily_count(self, amount: int) -> int:
        current = self.get_daily_count()
        self.data["daily_scan"]["count"] = current + amount
        self.data["last_scan_at"] = to_iso()
        return self.data["daily_scan"]["count"]

    def next_rotation(self, filter_ids: list[str], filters_per_cycle: int) -> list[str]:
        if not filter_ids:
            return []
        offset = int(self.data.get("rotation_offset", 0)) % len(filter_ids)
        ordered = filter_ids[offset:] + filter_ids[:offset]
        selected = ordered[:filters_per_cycle]
        self.data["rotation_offset"] = (offset + filters_per_cycle) % len(filter_ids)
        return selected

    def record_filter_result(self, filter_id: str, filter_name: str, *, success: bool, listings: int, deals: int, error: str | None = None) -> None:
        filters = self.data.setdefault("filters", {})
        entry = filters.setdefault(
            filter_id,
            {
                "filter_id": filter_id,
                "filter_name": filter_name,
                "scan_count": 0,
                "empty_count": 0,
                "hit_count": 0,
                "deal_count": 0,
                "last_seen_result_at": None,
                "last_scan_at": None,
                "last_error": None,
            },
        )
        entry["scan_count"] += 1
        entry["last_scan_at"] = to_iso()
        entry["filter_name"] = filter_name
        entry["last_error"] = error
        if success:
            if listings > 0:
                entry["hit_count"] += 1
                entry["last_seen_result_at"] = to_iso()
            else:
                entry["empty_count"] += 1
            entry["deal_count"] += deals

    def filter_health(self) -> list[dict[str, Any]]:
        results = []
        cutoff = utc_now() - timedelta(days=FILTER_EMPTY_WARNING_DAYS)
        for filter_id, entry in self.data.get("filters", {}).items():
            last_hit = parse_iso(entry.get("last_seen_result_at"))
            stale = last_hit is None or last_hit < cutoff
            results.append({
                **entry,
                "status": "slow" if stale else "healthy",
                "days_since_hit": None if last_hit is None else round((utc_now() - last_hit).total_seconds() / 86400, 1),
            })
        return sorted(results, key=lambda item: (item["status"] != "slow", item.get("filter_name") or ""))

    def record_scan_summary(self, summary: dict[str, Any]) -> None:
        scans = self.data.setdefault("recent_scans", [])
        scans.append(summary)
        self.data["recent_scans"] = scans[-RECENT_SCAN_HISTORY_LIMIT:]
        deals = self.data.setdefault("recent_deals", [])
        deals.extend(summary.get("deals", []))
        self.data["recent_deals"] = deals[-RECENT_DEAL_HISTORY_LIMIT:]

    def set_economy_refresh(self) -> None:
        self.data["last_economy_refresh_at"] = to_iso()

    def set_pending_confirmation(self, deal: dict[str, Any] | None) -> None:
        self.data["pending_confirmation"] = deepcopy(deal) if deal else None
        self.save()

    def get_pending_confirmation(self) -> dict[str, Any] | None:
        pending = self.data.get("pending_confirmation")
        return deepcopy(pending) if pending else None

    def save(self) -> None:
        write_json(self.path, self.data)
