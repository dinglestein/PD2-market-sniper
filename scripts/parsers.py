from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from config import MARKET_URL, SITE_ROOT

PRICE_HR_RE = re.compile(r"([\d.]+)\s*HR", re.IGNORECASE)
PRICE_BARE_RE = re.compile(r"Price:\s*([\d.]+)", re.IGNORECASE)
PRICE_WSS_RE = re.compile(r"([\d.]+)\s*/\s*\d+\s*wss", re.IGNORECASE)
ID_RE = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_price_to_hr(value: Any) -> float | None:
    """Extract HR price from various formats.
    
    Handles:
    - "2 HR" or "0.5hr" -> 2.0 / 0.5
    - "Price: 2" or "Price: 0.25" -> bare number after Price:
    - "0.25 / 12 wss" -> 0.25 (HR portion of mixed currency)
    - Plain number "1.5" or 2 -> returned directly
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    # Explicit "HR" suffix
    match = PRICE_HR_RE.search(text)
    if match:
        return float(match.group(1))
    # "Price: X" pattern (common in DOM text)
    match = PRICE_BARE_RE.search(text)
    if match:
        return float(match.group(1))
    # "X / N wss" mixed currency (HR is the first number)
    match = PRICE_WSS_RE.search(text)
    if match:
        return float(match.group(1))
    # Plain number
    stripped = text.replace(".", "", 1)
    if stripped.isdigit():
        return float(text)
    return None


def _coalesce(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, "", []):
            return mapping[key]
    return None


def normalize_listing(raw: dict[str, Any], *, filter_id: str, filter_name: str, source_url: str | None = None) -> dict[str, Any] | None:
    item_name = _coalesce(raw, ("item_name", "itemName", "name", "title", "baseName", "item"))
    price_hr = parse_price_to_hr(_coalesce(raw, ("price_hr", "priceHr", "price", "offer", "listingPrice")))
    seller_name = _coalesce(raw, ("seller_name", "sellerName", "seller", "account", "username", "displayName"))
    listing_id = _coalesce(raw, ("listing_id", "listingId", "id", "tradeId", "_id"))
    if listing_id is not None:
        listing_id = str(listing_id)
    listing_url = _coalesce(raw, ("listing_url", "listingUrl", "url", "href", "link"))
    if listing_url and isinstance(listing_url, str):
        listing_url = urljoin(SITE_ROOT, listing_url)
    elif listing_id and ID_RE.match(listing_id):
        listing_url = f"{MARKET_URL}/listing/{listing_id}"
    else:
        listing_url = source_url or MARKET_URL
    stats = _coalesce(raw, ("stats", "attributes", "mods", "itemStats", "properties"))
    corruption = _coalesce(raw, ("corruption", "corruptions", "slam", "corruptedMods"))
    posted_at = _coalesce(raw, ("posted_at", "postedAt", "createdAt", "updatedAt", "time_posted", "listedAt"))
    text_preview = _coalesce(raw, ("text_preview", "description", "summary", "tooltip", "body"))
    if not item_name and not price_hr and not seller_name:
        return None
    return {
        "filter_id": filter_id,
        "filter_name": filter_name,
        "item_name": str(item_name or "Unknown item"),
        "price_hr": price_hr,
        "seller_name": str(seller_name or "Unknown seller"),
        "listing_id": listing_id,
        "listing_url": listing_url,
        "posted_at": posted_at,
        "stats": stats if isinstance(stats, list) else ([stats] if stats else []),
        "corruption": corruption if isinstance(corruption, list) else ([corruption] if corruption else []),
        "text_preview": text_preview,
        "raw": raw,
        "captured_at": utc_now_iso(),
    }


def _walk_candidates(node: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(node, dict):
        values = list(node.values())
        if any(isinstance(v, (dict, list)) for v in values):
            if any(key in node for key in ("price", "listingPrice", "itemName", "seller", "sellerName", "name", "title")):
                candidates.append(node)
            for value in values:
                candidates.extend(_walk_candidates(value))
        else:
            if any(key in node for key in ("price", "listingPrice", "itemName", "seller", "sellerName", "name", "title")):
                candidates.append(node)
    elif isinstance(node, list):
        for value in node:
            candidates.extend(_walk_candidates(value))
    return candidates


def parse_api_response(payload: Any, *, filter_id: str, filter_name: str, source_url: str | None = None) -> list[dict[str, Any]]:
    listings = []
    seen_keys = set()
    for candidate in _walk_candidates(payload):
        listing = normalize_listing(candidate, filter_id=filter_id, filter_name=filter_name, source_url=source_url)
        if not listing:
            continue
        key = json.dumps([listing.get("listing_id"), listing.get("item_name"), listing.get("seller_name"), listing.get("price_hr")], sort_keys=True)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        listings.append(listing)
    return listings


async def parse_dom_listings(page, *, filter_id: str, filter_name: str, source_url: str) -> list[dict[str, Any]]:
    """Parse listings from DOM using the OFFER button as anchor.
    
    DOM structure (PD2 market): div.panel.listing contains the full card.
    Seller link pattern: a[href^='/@username'].
    """
    offer_buttons = page.locator("button.button.gold:has-text('OFFER'), button:has-text('OFFER')")
    count = await offer_buttons.count()
    results = []
    for index in range(count):
        try:
            button = offer_buttons.nth(index)
            # Target the .panel.listing container (precise, not too wide)
            container = button.locator("xpath=ancestor::div[contains(@class, 'panel') and contains(@class, 'listing')][1]")
            if await container.count() == 0:
                container = button.locator("xpath=ancestor::div[3]")
            text = await container.inner_text(timeout=3000)
            if not text:
                continue
        except Exception:
            continue

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Extract price (first line matching pattern)
        price_hr = None
        for line in lines:
            price_hr = parse_price_to_hr(line)
            if price_hr is not None:
                break

        # Extract item name: prefer "Rare/Magic/Set/Unique <Base> <Type>" line
        item_name = lines[0] if lines else f"Listing {index + 1}"
        for line in lines:
            if any(prefix in line for prefix in ("Rare ", "Magic ", "Set ", "Unique ", "Crafted ", "Ethereal ")):
                item_name = line
                break

        # Extract seller from /@username link (most reliable)
        seller_name = "Unknown seller"
        try:
            seller_links = container.locator("a[href^='/@']")
            if await seller_links.count() > 0:
                href = await seller_links.first.get_attribute("href", timeout=1000)
                if href:
                    seller_name = href.lstrip("/@")
        except Exception:
            pass
        # Text fallback
        if seller_name == "Unknown seller":
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                if "ladder" in line.lower() or "softcore" in line.lower():
                    continue
                if line.startswith("(") or line.startswith("["):
                    continue
                if re.match(r"^\d+\s+(second|minute|hour|day)s?\s+ago$", line, re.IGNORECASE):
                    continue
                if re.match(r"^(price|offer|buy|stash)$", line, re.IGNORECASE):
                    continue
                if not re.match(r"^[\d#]", line) and len(line) < 30 and "price" not in line.lower():
                    seller_name = line
                    break

        # Extract time posted
        posted_at = None
        for line in lines:
            time_match = re.match(r"(\d+)\s+(second|minute|hour|day)s?\s+ago", line, re.IGNORECASE)
            if time_match:
                posted_at = line
                break

        # Extract stats (lines between item header and Price/OFFER)
        stats = []
        in_stats = False
        for line in lines:
            if line.lower().startswith("price:") or line in ("OFFER", "BUY"):
                break
            if "corrupted" in line.lower() and len(line) < 20:
                continue
            if any(prefix in line for prefix in ("Rare ", "Magic ", "Set ", "Unique ", "Crafted ", "Ethereal ")):
                in_stats = True
                continue
            if line.startswith("Defense"):
                in_stats = True
                continue
            if in_stats and line:
                # Skip requirement lines (not actual mods)
                if line.startswith("Required"):
                    continue
                stats.append(line)

        # Extract corruption flag
        corruption = []
        for line in lines:
            if "corrupted" in line.lower() and "not" not in line.lower():
                corruption.append("Corrupted")
                break

        # Find listing URL from within the container
        listing_url = source_url
        try:
            item_links = container.locator("a[href*='listing']")
            if await item_links.count() > 0:
                href = await item_links.first.get_attribute("href", timeout=1000)
                if href:
                    listing_url = urljoin(SITE_ROOT, href)
        except Exception:
            pass

        listing = normalize_listing(
            {
                "item_name": item_name,
                "price_hr": price_hr,
                "seller_name": seller_name,
                "listing_url": listing_url,
                "posted_at": posted_at,
                "stats": stats,
                "corruption": corruption,
                "description": text[:500],
            },
            filter_id=filter_id,
            filter_name=filter_name,
            source_url=source_url,
        )
        if listing:
            results.append(listing)
    return results
