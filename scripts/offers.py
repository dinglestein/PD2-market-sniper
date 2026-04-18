from __future__ import annotations

import json
import logging
from typing import Any

from config import CHROME_DEBUG_URL, DEFAULT_TIMEOUT_MS, MARKET_URL, SCREENSHOTS_DIR
from history import OfferHistory

logger = logging.getLogger(__name__)


def _extract_listing_id(listing_url: str) -> str | None:
    """Extract listing hash from a PD2 market URL."""
    # URLs like: https://www.projectdiablo2.com/market/item/ABC123
    parts = listing_url.rstrip("/").split("/")
    for i, part in enumerate(parts):
        if part == "item" and i + 1 < len(parts):
            return parts[i + 1]
    return None


async def submit_offer(
    *,
    listing_url: str,
    amount_hr: float,
    item: dict[str, Any] | None = None,
    screenshot_name: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Submit an offer on a market listing.

    Tries the PD2 REST API first (fast, no browser needed).
    Falls back to browser automation via Playwright if API fails.
    """
    from pd2_api import get_pd2_token, submit_market_offer

    history = OfferHistory()
    item = item or {"listing_url": listing_url}
    listing_id = item.get("listing_id") or _extract_listing_id(listing_url)
    offer_text = note or f"{amount_hr} HR"

    # Try REST API first
    token = get_pd2_token()
    if token and listing_id:
        try:
            result = submit_market_offer(
                listing_id,
                offer_text=offer_text,
                hr_offer=amount_hr,
                token=token,
            )
            if result:
                entry = history.record_offer(
                    item=item,
                    amount_hr=amount_hr,
                    status="submitted",
                    note=f"via REST API, listing_id={listing_id}",
                )
                return {"ok": True, "offer": entry, "method": "api"}
        except Exception as exc:
            logger.warning("REST API offer failed, falling back to browser: %s", exc)

    # Fallback to browser automation
    return await _submit_offer_browser(
        listing_url=listing_url,
        amount_hr=amount_hr,
        item=item,
        screenshot_name=screenshot_name,
    )


async def _submit_offer_browser(
    *,
    listing_url: str,
    amount_hr: float,
    item: dict[str, Any],
    screenshot_name: str | None = None,
) -> dict[str, Any]:
    """Submit offer via browser automation (Playwright fallback)."""
    import asyncio
    from playwright.async_api import async_playwright

    history = OfferHistory()
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(CHROME_DEBUG_URL)
    context = browser.contexts[0]
    page = await context.new_page()
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
        entry = history.record_offer(
            item=item,
            amount_hr=amount_hr,
            status="submitted",
            note=f"screenshot={screenshot_path.name}, method=browser",
        )
        return {"ok": True, "offer": entry, "screenshot": str(screenshot_path), "method": "browser"}
    except Exception as exc:
        entry = history.record_offer(item=item, amount_hr=amount_hr, status="failed", note=str(exc))
        return {"ok": False, "error": str(exc), "offer": entry}
    finally:
        await page.close()
        await playwright.stop()


def check_offer_status(offer_id: str) -> dict[str, Any] | None:
    """Check status of a submitted offer via REST API."""
    from pd2_api import get_outgoing_offers, get_pd2_token
    token = get_pd2_token()
    if not token:
        return None
    # This is a simplified check — in practice you'd query the specific offer
    return None


def get_my_outgoing_offers() -> list[dict[str, Any]]:
    """Get all outgoing offers for the authenticated user."""
    from pd2_api import get_outgoing_offers, get_pd2_token
    token = get_pd2_token()
    if not token:
        return []
    return get_outgoing_offers(user_id="", token=token)


def get_my_incoming_offers() -> list[dict[str, Any]]:
    """Get all incoming offers for the authenticated user."""
    from pd2_api import get_incoming_offers, get_pd2_token
    token = get_pd2_token()
    if not token:
        return []
    return get_incoming_offers(user_id="", token=token)
