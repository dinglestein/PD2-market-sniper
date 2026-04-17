from __future__ import annotations

import asyncio
import json
import random
from typing import Any

from alerts import enrich_and_rank
from config import (
    CHROME_DEBUG_URL,
    DEFAULT_DAILY_FILTER_LIMIT,
    DEFAULT_FILTERS_PER_CYCLE,
    DEFAULT_MAX_PRICE_HR,
    DEFAULT_TIMEOUT_MS,
    DEFAULT_WAIT_AFTER_NAV_SECONDS,
    FILTERS,
    MARKET_URL,
    SCAN_DELAY_MAX_SECONDS,
    SCAN_DELAY_MIN_SECONDS,
    SCREENSHOTS_DIR,
)
from dashboard import write_dashboard
from economy import EconomyManager
from history import OfferHistory, SeenStore, StateStore, to_iso
from parsers import parse_api_response, parse_dom_listings


async def get_browser():
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(CHROME_DEBUG_URL)
    context = browser.contexts[0]
    return playwright, browser, context


class MarketScanner:
    def __init__(
        self,
        *,
        max_price_hr: float = DEFAULT_MAX_PRICE_HR,
        filters_per_cycle: int = DEFAULT_FILTERS_PER_CYCLE,
        daily_filter_limit: int = DEFAULT_DAILY_FILTER_LIMIT,
        force_economy_refresh: bool = False,
    ):
        self.max_price_hr = max_price_hr
        self.filters_per_cycle = filters_per_cycle
        self.daily_filter_limit = daily_filter_limit
        self.force_economy_refresh = force_economy_refresh
        self.state = StateStore()
        self.seen = SeenStore()
        self.offers = OfferHistory()
        self.economy = EconomyManager(self.state)

    async def scan(self, filter_id: str | None = None) -> dict[str, Any]:
        economy = await self.economy.ensure_fresh(force=self.force_economy_refresh)
        selected_filters = self._select_filters(filter_id)
        playwright, _browser, context = await get_browser()
        page = await context.new_page()
        try:
            results = []
            deals = []
            for current_filter_id in selected_filters:
                filter_name = FILTERS[current_filter_id]
                filter_result = await self._scan_filter(page, current_filter_id, filter_name, economy)
                results.append(filter_result)
                deals.extend(filter_result["deals"])
                await asyncio.sleep(random.uniform(SCAN_DELAY_MIN_SECONDS, SCAN_DELAY_MAX_SECONDS))
            ranked_deals = enrich_and_rank(deals)
            summary = {
                "timestamp": to_iso(),
                "filters_scanned": len(selected_filters),
                "deals_found": len(ranked_deals),
                "daily_filter_count": self.state.increment_daily_count(len(selected_filters)),
                "max_price_hr": self.max_price_hr,
            }
            output = {
                "summary": summary,
                "filters": results,
                "deals": ranked_deals,
                "review": [item for result in results for item in result.get("needs_review", [])],
                "state": self.state.data,
                "economy": {"refreshed_at": economy.get("refreshed_at")},
            }
            self.state.record_scan_summary({**summary, "deals": ranked_deals})
            self.state.save()
            write_dashboard(output, self.offers.stats(), self.state.filter_health(), economy)
            return output
        finally:
            await page.close()
            await playwright.stop()

    def _select_filters(self, filter_id: str | None) -> list[str]:
        if filter_id:
            return [filter_id]
        filter_ids = list(FILTERS.keys())
        remaining = max(0, self.daily_filter_limit - self.state.get_daily_count())
        if remaining <= 0:
            return []
        return self.state.next_rotation(filter_ids, min(self.filters_per_cycle, remaining))

    async def _scan_filter(self, page, filter_id: str, filter_name: str, economy: dict[str, Any]) -> dict[str, Any]:
        listing_url = f"{MARKET_URL}?filter={filter_id}"
        api_payloads: list[dict[str, Any]] = []

        async def handle_response(response):
            try:
                if response.request.resource_type not in {"xhr", "fetch"}:
                    return
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type.lower():
                    return
                if "market" not in response.url.lower() and "trade" not in response.url.lower() and "listing" not in response.url.lower():
                    return
                payload = await response.json()
                api_payloads.append({"url": response.url, "payload": payload})
            except Exception:
                return

        page.on("response", handle_response)
        try:
            await page.goto(listing_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
            await asyncio.sleep(DEFAULT_WAIT_AFTER_NAV_SECONDS)
            listings = []
            api_hits = []
            for payload in api_payloads:
                parsed = parse_api_response(payload["payload"], filter_id=filter_id, filter_name=filter_name, source_url=payload["url"])
                if parsed:
                    listings.extend(parsed)
                    api_hits.append(payload["url"])
            if not listings:
                listings = await parse_dom_listings(page, filter_id=filter_id, filter_name=filter_name, source_url=listing_url)
            deals = []
            review = []
            for item in listings:
                item["economy_value_hr"] = self.economy.value_for(item.get("item_name"))
                item["recent_offer_count"] = len(self.offers.recent_for_listing(item.get("listing_id"), item.get("listing_url")))
                if item.get("price_hr") is None:
                    review.append(item)
                    continue
                if item["price_hr"] <= self.max_price_hr and self.seen.is_new(item):
                    screenshot_path = SCREENSHOTS_DIR / f"deal-{filter_id}-{item.get('listing_id') or len(deals)}.png"
                    try:
                        await page.screenshot(path=str(screenshot_path), full_page=True)
                        item["screenshot"] = str(screenshot_path)
                    except Exception:
                        pass
                    self.seen.mark_seen(item)
                    deals.append(item)
            self.seen.save()
            self.state.record_filter_result(filter_id, filter_name, success=True, listings=len(listings), deals=len(deals))
            return {
                "filter_id": filter_id,
                "filter_name": filter_name,
                "url": listing_url,
                "listing_count": len(listings),
                "api_hits": api_hits,
                "deals": deals,
                "needs_review": review,
            }
        except Exception as exc:
            self.state.record_filter_result(filter_id, filter_name, success=False, listings=0, deals=0, error=str(exc))
            return {
                "filter_id": filter_id,
                "filter_name": filter_name,
                "url": listing_url,
                "listing_count": 0,
                "api_hits": [],
                "deals": [],
                "needs_review": [],
                "error": str(exc),
            }
        finally:
            try:
                page.remove_listener("response", handle_response)
            except Exception:
                pass
