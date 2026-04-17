from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from history import parse_iso, utc_now


CORRUPTION_KEYWORDS = {
    "+skill": 1.5,
    "+ias": 1.0,
    "+40 pierce": 1.6,
    "+3 os": 1.4,
    "+5os": 1.6,
    "+cb": 1.1,
    "+ds": 1.1,
    "+ed": 1.1,
    "+pierce": 1.2,
}


def age_hours(posted_at: str | None) -> float | None:
    dt = parse_iso(posted_at)
    if not dt:
        return None
    return max(0.0, (utc_now() - dt).total_seconds() / 3600)


def score_deal(item: dict[str, Any], economy_value: float | None = None) -> float:
    price = item.get("price_hr")
    baseline = economy_value or item.get("economy_value_hr")
    score = 0.0
    if price is not None and baseline:
        discount = max(0.0, baseline - price)
        score += discount * 50
        score += max(0.0, (baseline / max(price, 0.01)) - 1.0) * 20
    elif price is not None:
        score += max(0.0, 1.0 - price) * 10

    text_bits = " ".join(
        str(part).lower()
        for part in [item.get("item_name"), item.get("filter_name"), *(item.get("corruption") or []), *(item.get("stats") or [])]
        if part
    )
    for keyword, value in CORRUPTION_KEYWORDS.items():
        if keyword in text_bits:
            score += value * 10

    posted_hours = age_hours(item.get("posted_at"))
    if posted_hours is not None:
        score += max(0.0, 24 - posted_hours) / 2
    else:
        score += 2

    offers = item.get("recent_offer_count") or 0
    score -= offers * 8
    return round(score, 2)


def enrich_and_rank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for item in items:
        enriched = dict(item)
        enriched["score"] = score_deal(enriched, economy_value=enriched.get("economy_value_hr"))
        ranked.append(enriched)
    return sorted(ranked, key=lambda entry: entry.get("score", 0), reverse=True)


def format_alert(item: dict[str, Any]) -> str:
    stats = ", ".join(str(v) for v in item.get("stats") or [] if v)
    corruption = ", ".join(str(v) for v in item.get("corruption") or [] if v)
    extras = "; ".join(part for part in [stats, corruption] if part)
    return (
        f"[{item.get('score', 0):.1f}] {item.get('item_name')} @ {item.get('price_hr')} HR | "
        f"seller={item.get('seller_name')} | filter={item.get('filter_name')} | "
        f"link={item.get('listing_url')}" + (f" | {extras}" if extras else "")
    )
