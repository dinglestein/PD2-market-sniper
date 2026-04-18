"""Market search via PD2 REST API.

Direct search against api.projectdiablo2.com/market/listing
using MongoDB-style query filters — same as pd2-trade desktop app.
No browser/Playwright needed for search.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any

from pd2_api import PD2_API, get_pd2_token, _get_json

logger = logging.getLogger(__name__)


def build_search_query(
    *,
    search_text: str | None = None,
    base_code: str | None = None,
    type_code: str | None = None,
    quality: str | None = None,
    corrupted: bool | None = None,
    ethereal: bool | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_socket: int | None = None,
    max_socket: int | None = None,
    min_level: int | None = None,
    max_level: int | None = None,
    modifiers: list[dict[str, Any]] | None = None,
    is_ladder: bool = True,
    is_hardcore: bool = False,
    limit: int = 20,
    offset: int = 0,
    sort: dict[str, int] | None = None,
    search_archived: bool = False,
) -> dict[str, Any]:
    """Build a market search query in the PD2 API format.

    Args:
        search_text: Regex on item name
        base_code: Specific base item code
        type_code: Item type code (e.g. "scha" for Amazon spears)
        quality: "Unique", "Set", "Rare", etc.
        corrupted: Filter corrupted state
        ethereal: Filter ethereal state
        min_price/max_price: HR price range
        min_socket/max_socket: Socket count range
        min_level/max_level: Level requirement range
        modifiers: List of {name, min?, max?} modifier filters
        is_ladder: Ladder vs non-ladder
        is_hardcore: Hardcore vs softcore
        limit: Results per page
        offset: Pagination offset
        sort: Sort order (default: bumped_at descending)
        search_archived: Include archived listings
    """
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    days_back = 14 if search_archived else 3
    date_threshold = (now - timedelta(days=days_back)).isoformat() + "Z"

    query: dict[str, Any] = {
        "$resolve": {"user": {"in_game_account": True}},
        "type": "item",
        "$limit": limit,
        "$skip": offset,
        "accepted_offer_id": None,
        "updated_at": {"$gte": date_threshold},
        "$sort": sort or {"bumped_at": -1},
        "is_hardcore": is_hardcore,
        "is_ladder": is_ladder,
    }

    if search_text:
        query["item.name"] = {"$regex": search_text, "$options": "i"}

    if base_code:
        query["item.base_code"] = base_code

    if type_code:
        if type_code.startswith("{") or type_code.startswith("["):
            query["item.base.type_code"] = json.loads(type_code)
        else:
            query["item.base.type_code"] = type_code

    if quality:
        query["item.quality.name"] = quality

    if corrupted is not None:
        query["item.corrupted"] = corrupted

    if ethereal is not None:
        query["item.is_ethereal"] = ethereal

    hr_constraints: dict[str, Any] = {}
    if min_price is not None:
        hr_constraints["$gte"] = min_price
    if max_price is not None:
        hr_constraints["$lte"] = max_price
    if hr_constraints:
        query["hr_price"] = hr_constraints

    socket_constraints: dict[str, Any] = {}
    if min_socket is not None:
        socket_constraints["$gte"] = min_socket
    if max_socket is not None:
        socket_constraints["$lte"] = max_socket
    if socket_constraints:
        query["item.socket_count"] = socket_constraints

    level_constraints: dict[str, Any] = {}
    if min_level is not None:
        level_constraints["$gte"] = min_level
    if max_level is not None:
        level_constraints["$lte"] = max_level
    if level_constraints:
        query["item.requirements.level"] = level_constraints

    if modifiers:
        if len(modifiers) == 1:
            mod = modifiers[0]
            elem_match: dict[str, Any] = {"name": mod["name"]}
            val_constraints: dict[str, Any] = {}
            if "min" in mod:
                val_constraints["$gte"] = mod["min"]
            if "max" in mod:
                val_constraints["$lte"] = mod["max"]
            if val_constraints:
                elem_match["values.0"] = val_constraints
            query["item.modifiers"] = {"$elemMatch": elem_match}
        else:
            mod_queries = []
            for mod in modifiers:
                em: dict[str, Any] = {"name": mod["name"]}
                vc: dict[str, Any] = {}
                if "min" in mod:
                    vc["$gte"] = mod["min"]
                if "max" in mod:
                    vc["$lte"] = mod["max"]
                if vc:
                    em["values.0"] = vc
                mod_queries.append({"$elemMatch": em})
            query["item.modifiers"] = {"$all": mod_queries}

    return query


def search_listings(query: dict[str, Any]) -> dict[str, Any] | None:
    """Execute a market search query against the PD2 API.

    Returns the raw API response with total, limit, skip, data.
    """
    token = get_pd2_token()
    if not token:
        logger.warning("No PD2 auth token — cannot search market via API")
        return None

    # Serialize nested objects as JSON strings in query params
    params = []
    for key, value in query.items():
        if isinstance(value, (dict, list)):
            params.append((key, json.dumps(value)))
        elif isinstance(value, bool):
            params.append((key, "true" if value else "false"))
        else:
            params.append((key, str(value)))

    qs = urllib.parse.urlencode(params)
    url = f"{PD2_API}/market/listing?{qs}"
    return _get_json(url, headers={"Authorization": f"Bearer {token}"})


def search_by_name(
    item_name: str,
    *,
    max_price: float | None = None,
    is_ladder: bool = True,
    is_hardcore: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Quick search for items by name with optional max price filter."""
    query = build_search_query(
        search_text=item_name,
        max_price=max_price,
        is_ladder=is_ladder,
        is_hardcore=is_hardcore,
        limit=limit,
    )
    result = search_listings(query)
    if result and "data" in result:
        return result["data"]
    return []


def search_deals(
    *,
    base_code: str | None = None,
    type_code: str | None = None,
    max_price_hr: float = 0.5,
    modifiers: list[dict[str, Any]] | None = None,
    is_ladder: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search for deals under a given HR price.

    Returns listings sorted by price ascending (cheapest first).
    """
    query = build_search_query(
        base_code=base_code,
        type_code=type_code,
        max_price=max_price_hr,
        modifiers=modifiers,
        is_ladder=is_ladder,
        limit=limit,
        sort={"hr_price": 1},  # cheapest first
    )
    result = search_listings(query)
    if result and "data" in result:
        return result["data"]
    return []
