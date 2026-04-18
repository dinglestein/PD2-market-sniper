from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from config import ECONOMY_FILE, ECONOMY_REFRESH_HOURS
from history import StateStore, parse_iso, to_iso, utc_now
from pd2_api import (
    PD2TRADER_API,
    fetch_batch_prices,
    fetch_item_price_by_name,
    _get_json,
)

logger = logging.getLogger(__name__)

# Base codes for currency, runes, and ubers (from pd2-trade mappings)
RUNE_BASE_CODES = {
    "El Rune": "r01", "Eld Rune": "r02", "Tir Rune": "r03", "Nef Rune": "r04",
    "Eth Rune": "r05", "Ith Rune": "r06", "Tal Rune": "r07", "Ral Rune": "r08",
    "Ort Rune": "r09", "Thul Rune": "r10", "Amn Rune": "r11", "Sol Rune": "r12",
    "Shael Rune": "r13", "Dol Rune": "r14", "Hel Rune": "r15", "Io Rune": "r16",
    "Lum Rune": "r17", "Ko Rune": "r18", "Fal Rune": "r19", "Lem Rune": "r20",
    "Pul Rune": "r21", "Um Rune": "r22", "Mal Rune": "r23", "Ist Rune": "r24",
    "Gul Rune": "r25", "Vex Rune": "r26", "Ohm Rune": "r27", "Lo Rune": "r28",
    "Sur Rune": "r29", "Ber Rune": "r30", "Jah Rune": "r31", "Cham Rune": "r32",
    "Zod Rune": "r33",
}

CURRENCY_BASE_CODES = {
    "Standard of Heroes": "soh",
    "Worldstone Shard": "ws1",
    "Larzuk's Puzzlepiece": "lpp",
    "Larzuk's Puzzlebox": "lpb",
    "Twisted Essence of Suffering": "tes",
    "Charged Essence of Hatred": "ceh",
    "Burning Essence of Terror": "bet",
    "Festering Essence of Destruction": "fed",
    "Demonic Cube": "dc1",
    "Catalyst Shard": "cs1",
}

UBER_BASE_CODES = {
    "Talisman of Transgression": "tot",
    "Demonic Insignia": "din",
    "Flesh of Malic": "fom",
    "Black Soulstone": "bs1",
    "Splinter of the Void": "sov",
    "Hellfire Ashes": "hfa",
    "Prime Evil Soul": "pes",
    "Pure Demonic Essence": "pde",
    "Sigil of Korlic": "sok",
    "Sigil of Madawc": "som",
    "Sigil of Talic": "sot",
    "Tainted Worldstone Shard": "tws",
    "Trang-Oul's Jawbone": "toj",
}

# Fixed fallback prices for low runes (they don't change much)
FIXED_LOW_RUNE_PRICES = {
    "El Rune": 0.001, "Eld Rune": 0.001, "Tir Rune": 0.001, "Nef Rune": 0.001,
    "Eth Rune": 0.001, "Ith Rune": 0.001, "Tal Rune": 0.001, "Ral Rune": 0.001,
    "Ort Rune": 0.001, "Thul Rune": 0.001, "Amn Rune": 0.001, "Sol Rune": 0.001,
    "Shael Rune": 0.001, "Dol Rune": 0.001, "Hel Rune": 0.001, "Io Rune": 0.001,
    "Lum Rune": 0.001, "Ko Rune": 0.001, "Fal Rune": 0.001, "Lem Rune": 0.002,
    "Pul Rune": 0.005, "Um Rune": 0.01, "Mal Rune": 0.015, "Ist Rune": 0.02,
    "Gul Rune": 0.025, "Vex Rune": 0.03,
}

# Minimum listings to trust API price (fall back to fixed if fewer)
MIN_LISTINGS = 10

# Items that are always considered "low" and use fixed prices
LOW_RUNE_NAMES = set(FIXED_LOW_RUNE_PRICES.keys())


class EconomyManager:
    def __init__(self, state: StateStore | None = None):
        self.state = state or StateStore()

    def load(self) -> dict[str, Any]:
        if not ECONOMY_FILE.exists():
            return {"refreshed_at": None, "sources": {}, "values": {}}
        try:
            return json.loads(ECONOMY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"refreshed_at": None, "sources": {}, "values": {}}

    async def refresh(self, force: bool = False) -> dict[str, Any]:
        """Refresh economy data from PD2Trader API.

        No Playwright needed — pure HTTP requests.
        """
        current = self.load()
        last_refresh = parse_iso(current.get("refreshed_at")) if current else None
        if not force and last_refresh and utc_now() - last_refresh < timedelta(hours=ECONOMY_REFRESH_HOURS):
            return current

        try:
            sources: dict[str, Any] = {}
            combined_values: dict[str, float] = {}

            # Fetch runes
            rune_values = self._fetch_rune_prices()
            sources["runes"] = {"source": "pd2trader", "value_count": len(rune_values)}
            combined_values.update(rune_values)
            logger.info("Economy runes: %d values", len(rune_values))

            # Fetch currency
            currency_values = self._fetch_category_prices(CURRENCY_BASE_CODES, "currency")
            sources["currency"] = {"source": "pd2trader", "value_count": len(currency_values)}
            combined_values.update(currency_values)
            logger.info("Economy currency: %d values", len(currency_values))

            # Fetch ubers
            uber_values = self._fetch_category_prices(UBER_BASE_CODES, "ubers")
            sources["ubers"] = {"source": "pd2trader", "value_count": len(uber_values)}
            combined_values.update(uber_values)
            logger.info("Economy ubers: %d values", len(uber_values))

            payload = {
                "refreshed_at": to_iso(),
                "sources": sources,
                "values": combined_values,
            }
            ECONOMY_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            self.state.set_economy_refresh()
            self.state.save()
            return payload
        except Exception as exc:
            logger.error("Economy refresh failed: %s — using cached data", exc)
            return self.load()

    async def ensure_fresh(self, force: bool = False) -> dict[str, Any]:
        return await self.refresh(force=force)

    def value_for(self, name: str | None) -> float | None:
        if not name:
            return None
        data = self.load()
        values = data.get("values", {})
        if name in values:
            return values[name]
        # Fuzzy match
        normalized = name.lower()
        for key, value in values.items():
            if key.lower() == normalized or key.lower() in normalized or normalized in key.lower():
                return value
        return None

    def _fetch_rune_prices(self) -> dict[str, float]:
        """Fetch rune prices from PD2Trader API with fixed fallback for low runes."""
        values: dict[str, float] = {}

        # Always use fixed prices for low runes
        values.update(FIXED_LOW_RUNE_PRICES)

        # Fetch high rune prices from API (Ohm through Zod)
        high_rune_codes = {}
        for name, code in RUNE_BASE_CODES.items():
            if name not in LOW_RUNE_NAMES:
                high_rune_codes[name] = code

        if high_rune_codes:
            batch = fetch_batch_prices(list(high_rune_codes.values()))
            for name, code in high_rune_codes.items():
                price_data = batch.get(code)
                if price_data:
                    median = price_data.get("medianPrice", 0)
                    count = price_data.get("sampleCount", 0)
                    if median > 0 and count >= MIN_LISTINGS:
                        values[name] = round(median, 4)
                    else:
                        # Use last known or median even with low samples
                        if median > 0:
                            values[name] = round(median, 4)

        return values

    def _fetch_category_prices(self, name_to_code: dict[str, str], category: str) -> dict[str, float]:
        """Fetch prices for a category (currency/ubers) from PD2Trader API."""
        values: dict[str, float] = {}
        if not name_to_code:
            return values

        batch = fetch_batch_prices(list(name_to_code.values()))
        for name, code in name_to_code.items():
            price_data = batch.get(code)
            if price_data:
                median = price_data.get("medianPrice", 0)
                if median > 0:
                    values[name] = round(median, 4)

        return values
