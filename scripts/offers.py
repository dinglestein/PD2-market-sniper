from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from config import CHROME_DEBUG_URL, DEFAULT_TIMEOUT_MS, MARKET_URL, SCREENSHOTS_DIR
from history import OfferHistory


async def get_browser():
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(CHROME_DEBUG_URL)
    context = browser.contexts[0]
    return playwright, browser, context


async def submit_offer(*, listing_url: str, amount_hr: float, item: dict[str, Any] | None = None, screenshot_name: str | None = None) -> dict[str, Any]:
    playwright, _browser, context = await get_browser()
    page = await context.new_page()
    history = OfferHistory()
    item = item or {"listing_url": listing_url}
    try:
        await page.goto(listing_url or MARKET_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        await asyncio.sleep(2)
        offer_button = page.locator("button.button.gold:has-text('OFFER'), button:has-text('OFFER')").first
        await offer_button.click(timeout=DEFAULT_TIMEOUT_MS)
        await asyncio.sleep(1)
        offer_input = page.locator("input[name='Offer'], input[placeholder*='Offer'], input[type='number']").first
        await offer_input.fill(str(amount_hr), timeout=DEFAULT_TIMEOUT_MS)
        submit_button = page.locator("button:has-text('SUBMIT')").first
        await submit_button.click(timeout=DEFAULT_TIMEOUT_MS)
        await asyncio.sleep(2)
        screenshot_path = SCREENSHOTS_DIR / (screenshot_name or f"offer-{item.get('listing_id') or 'listing'}.png")
        await page.screenshot(path=str(screenshot_path), full_page=True)
        entry = history.record_offer(item=item, amount_hr=amount_hr, status="submitted", note=f"screenshot={screenshot_path.name}")
        return {"ok": True, "offer": entry, "screenshot": str(screenshot_path)}
    except Exception as exc:
        entry = history.record_offer(item=item, amount_hr=amount_hr, status="failed", note=str(exc))
        return {"ok": False, "error": str(exc), "offer": entry}
    finally:
        await page.close()
        await playwright.stop()
