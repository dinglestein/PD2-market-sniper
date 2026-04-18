"""PD2 REST API client — direct HTTP access to PD2 APIs.

Replaces browser automation for economy data, market search, and offers.
Uses:
  - pd2trader.com for price data (median prices, trends, batch lookups)
  - api.projectdiablo2.com for market listings, offers, chat (requires JWT auth)
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

logger = logging.getLogger(__name__)

PD2TRADER_API = "https://pd2trader.com"
PD2_API = "https://api.projectdiablo2.com"


# ── PD2Trader Price API ────────────────────────────────────────────────────

def fetch_item_price(
    base_code: str,
    *,
    is_ladder: bool = True,
    is_hardcore: bool = False,
    hours: int = 168,
) -> dict[str, Any] | None:
    """Fetch median price for a single item by base_code."""
    params = urllib.parse.urlencode({
        "baseCode": base_code,
        "isLadder": str(is_ladder).lower(),
        "isHardcore": str(is_hardcore).lower(),
        "hours": hours,
    })
    url = f"{PD2TRADER_API}/item-prices/average?{params}"
    return _get_json(url)


def fetch_item_price_by_name(
    item_name: str,
    *,
    is_ladder: bool = True,
    is_hardcore: bool = False,
    hours: int = 168,
) -> dict[str, Any] | None:
    """Fetch median price for a single item by name (for uniques)."""
    params = urllib.parse.urlencode({
        "itemName": item_name,
        "isLadder": str(is_ladder).lower(),
        "isHardcore": str(is_hardcore).lower(),
        "hours": hours,
    })
    url = f"{PD2TRADER_API}/item-prices/average?{params}"
    return _get_json(url)


def fetch_batch_prices(
    base_codes: list[str],
    *,
    is_ladder: bool = True,
    is_hardcore: bool = False,
    hours: int = 168,
) -> dict[str, dict[str, Any]]:
    """Fetch median prices for multiple items in one request.

    Returns {base_code: price_data, ...}
    """
    body = json.dumps({
        "baseCodes": base_codes,
        "isLadder": is_ladder,
        "isHardcore": is_hardcore,
        "hours": hours,
    }).encode("utf-8")
    url = f"{PD2TRADER_API}/item-prices/average/batch"
    resp = _post_json(url, body)
    results: dict[str, dict[str, Any]] = {}
    if resp and isinstance(resp, dict) and "data" in resp:
        for item in resp["data"]:
            bc = item.get("baseCode")
            if bc:
                results[bc] = item
    return results


def fetch_corruption_prices(
    *,
    item_name: str | None = None,
    base_code: str | None = None,
    is_ladder: bool = True,
    is_hardcore: bool = False,
    hours: int = 168,
) -> dict[str, Any] | None:
    """Fetch corruption price breakdown for an item."""
    params: dict[str, Any] = {}
    if item_name:
        params["itemName"] = item_name
    if base_code:
        params["baseCode"] = base_code
    params.update({"isLadder": str(is_ladder).lower(), "isHardcore": str(is_hardcore).lower(), "hours": hours})
    qs = urllib.parse.urlencode(params)
    url = f"{PD2TRADER_API}/item-prices/corruption-prices?{qs}"
    return _get_json(url)


# ── PD2 Market API (requires auth) ─────────────────────────────────────────

def get_pd2_token() -> str | None:
    """Load PD2 auth token from config if available."""
    from config import SKILL_DIR
    token_file = SKILL_DIR / ".pd2_token"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    return None


def set_pd2_token(token: str) -> None:
    """Save PD2 auth token."""
    from config import SKILL_DIR
    (SKILL_DIR / ".pd2_token").write_text(token, encoding="utf-8")


def market_listings(
    query: dict[str, Any],
    *,
    token: str | None = None,
) -> dict[str, Any] | None:
    """Search market listings via GET /market/listing.

    Query uses MongoDB-style filters (same as pd2-trade app).
    """
    token = token or get_pd2_token()
    if not token:
        logger.warning("No PD2 auth token — market search unavailable")
        return None
    qs = urllib.parse.urlencode(query, doseq=True)
    url = f"{PD2_API}/market/listing?{qs}"
    return _get_json(url, headers={"Authorization": f"Bearer {token}"})


def submit_market_offer(
    listing_id: str,
    *,
    offer_text: str,
    hr_offer: float,
    token: str | None = None,
) -> dict[str, Any] | None:
    """Submit an offer on a market listing via POST."""
    token = token or get_pd2_token()
    if not token:
        logger.error("No PD2 auth token — cannot submit offer")
        return None
    body = json.dumps({
        "listing_id": listing_id,
        "offer": offer_text,
        "hr_offer": hr_offer,
    }).encode("utf-8")
    url = f"{PD2_API}/market/offer"
    return _post_json(url, body, headers={"Authorization": f"Bearer {token}"})


def get_incoming_offers(
    user_id: str,
    *,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Get incoming offers for the authenticated user."""
    token = token or get_pd2_token()
    if not token:
        return []
    query = urllib.parse.urlencode({
        "user_id": user_id,
        "$resolve": json.dumps({"offers": {"user": True}}),
        "$limit": 250,
        "$sort": json.dumps({"bumped_at": -1}),
    })
    url = f"{PD2_API}/market/listing?{query}"
    resp = _get_json(url, headers={"Authorization": f"Bearer {token}"})
    if resp and "data" in resp:
        return resp["data"]
    return []


def get_outgoing_offers(
    user_id: str,
    *,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Get offers made by the authenticated user."""
    token = token or get_pd2_token()
    if not token:
        return []
    query = urllib.parse.urlencode({
        "user_id": user_id,
        "$resolve": json.dumps({
            "listing": {"user": True},
            "listing_archive": {"user": True},
        }),
        "$limit": 250,
        "$sort": json.dumps({"created_at": -1}),
    })
    url = f"{PD2_API}/market/offer?{query}"
    resp = _get_json(url, headers={"Authorization": f"Bearer {token}"})
    if resp and "data" in resp:
        return resp["data"]
    return []


def accept_offer(listing_id: str, offer_id: str, *, token: str | None = None) -> bool:
    """Accept an offer on a listing."""
    token = token or get_pd2_token()
    if not token:
        return False
    url = f"{PD2_API}/market/listing/{listing_id}"
    body = json.dumps({"accepted_offer_id": offer_id}).encode("utf-8")
    resp = _patch_json(url, body, headers={"Authorization": f"Bearer {token}"})
    return resp is not None


def reject_offer(offer_id: str, *, token: str | None = None) -> bool:
    """Reject an offer."""
    token = token or get_pd2_token()
    if not token:
        return False
    url = f"{PD2_API}/market/offer/{offer_id}"
    body = json.dumps({"rejected": True}).encode("utf-8")
    resp = _patch_json(url, body, headers={"Authorization": f"Bearer {token}"})
    return resp is not None


# ── Social / Chat API ──────────────────────────────────────────────────────

def create_conversation(participant_ids: list[str], *, token: str | None = None) -> dict[str, Any] | None:
    """Create or get a conversation with given participants."""
    token = token or get_pd2_token()
    if not token:
        return None
    body = json.dumps({"participant_ids": participant_ids}).encode("utf-8")
    return _post_json(
        f"{PD2_API}/social/conversation",
        body,
        headers={"Authorization": f"Bearer {token}"},
    )


def send_message(
    conversation_id: str,
    content: str,
    sender_id: str,
    *,
    token: str | None = None,
) -> dict[str, Any] | None:
    """Send a chat message."""
    token = token or get_pd2_token()
    if not token:
        return None
    body = json.dumps({
        "sender_id": sender_id,
        "conversation_id": conversation_id,
        "content": content,
        "reader_ids": [sender_id],
    }).encode("utf-8")
    return _post_json(
        f"{PD2_API}/social/message",
        body,
        headers={"Authorization": f"Bearer {token}"},
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 15) -> dict[str, Any] | None:
    hdrs = {
        "Accept": "application/json",
        "User-Agent": "PD2Sniper/1.0 (https://github.com/dinglestein/PD2-market-sniper)",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        logger.warning("HTTP %d from %s", e.code, url)
        return None
    except Exception as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


def _post_json(url: str, body: bytes, *, headers: dict[str, str] | None = None, timeout: int = 15) -> dict[str, Any] | None:
    hdrs = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "PD2Sniper/1.0",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning("HTTP %d from POST %s", e.code, url)
        return None
    except Exception as exc:
        logger.warning("POST %s failed: %s", url, exc)
        return None


def _patch_json(url: str, body: bytes, *, headers: dict[str, str] | None = None, timeout: int = 15) -> dict[str, Any] | None:
    hdrs = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "PD2Sniper/1.0",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning("HTTP %d from PATCH %s", e.code, url)
        return None
    except Exception as exc:
        logger.warning("PATCH %s failed: %s", url, exc)
        return None
