#!/usr/bin/env python3
"""Batch offer: submit 10 WSS on all deals from last scan."""
import asyncio
import json
import sys
from pathlib import Path

from config import CHROME_DEBUG_URL, DEFAULT_TIMEOUT_MS, SCREENSHOTS_DIR
from history import OfferHistory

SCAN_RESULTS = Path(__file__).parent.parent / "scan_results.json"

OFFER_CURRENCY = "wss"
OFFER_AMOUNT = 10


async def get_browser():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CHROME_DEBUG_URL)
    ctx = browser.contexts[0]
    return pw, browser, ctx


async def submit_wss_offer(page, *, listing_url: str, currency: str, amount: int, item: dict, screenshot_name: str) -> dict:
    history = OfferHistory()
    try:
        await page.goto(listing_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        await asyncio.sleep(2)

        # Click OFFER button
        offer_btn = page.locator("button:has-text('OFFER')").first
        await offer_btn.click(timeout=DEFAULT_TIMEOUT_MS)
        await asyncio.sleep(1.5)

        # Fill currency text field (placeholder "Offer") to reveal quantity input
        currency_input = page.locator('input[placeholder="Offer"]').first
        await currency_input.fill(currency, timeout=DEFAULT_TIMEOUT_MS)
        await asyncio.sleep(1)

        # Fill amount field (placeholder "#") - now visible after currency selection
        amount_input = page.locator('input[placeholder="#"]').first
        await amount_input.fill(str(amount), force=True, timeout=DEFAULT_TIMEOUT_MS)
        await asyncio.sleep(0.5)

        # Click SUBMIT
        submit_btn = page.locator("button:has-text('SUBMIT')").first
        await submit_btn.click(timeout=DEFAULT_TIMEOUT_MS)
        await asyncio.sleep(2.5)

        # Screenshot
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_path = SCREENSHOTS_DIR / screenshot_name
        await page.screenshot(path=str(screenshot_path), full_page=True)

        entry = history.record_offer(item=item, amount_hr=amount, status="submitted", note=f"currency={currency}, amount={amount}, screenshot={screenshot_path.name}")
        return {"ok": True, "offer": entry, "screenshot": str(screenshot_path)}
    except Exception as exc:
        entry = history.record_offer(item=item, amount_hr=amount, status="failed", note=f"currency={currency}, error={exc}")
        return {"ok": False, "error": str(exc), "offer": entry}


async def main():
    data = json.loads(SCAN_RESULTS.read_text(encoding="utf-8"))
    deals = data.get("deals", [])
    if not deals:
        print("No deals found in scan results.")
        return

    print(f"Submitting {OFFER_AMOUNT} {OFFER_CURRENCY.upper()} on {len(deals)} deals...\n")

    pw, browser, ctx = await get_browser()
    page = await ctx.new_page()
    history = OfferHistory()
    results = []

    for i, deal in enumerate(deals):
        name = deal.get("item_name", "Unknown")
        seller = deal.get("seller_name", "?")
        asking = deal.get("price_hr", "?")
        url = deal.get("listing_url", "")
        lid = deal.get("listing_id") or f"idx{i}"
        screenshot_name = f"batch-offer-{lid}.png"

        print(f"[{i+1}/{len(deals)}] {name} ({asking} HR) by {seller}...")
        result = await submit_wss_offer(
            page,
            listing_url=url,
            currency=OFFER_CURRENCY,
            amount=OFFER_AMOUNT,
            item=deal,
            screenshot_name=screenshot_name,
        )
        if result["ok"]:
            print(f"  OK Submitted")
        else:
            print(f"  FAIL: {result.get('error', 'unknown')}")
        results.append({"deal_index": i, "item_name": name, **result})

        # Delay between offers to avoid rate limiting
        if i < len(deals) - 1:
            await asyncio.sleep(3)

    await page.close()
    await pw.stop()

    print(f"\n=== SUMMARY ===")
    ok = sum(1 for r in results if r["ok"])
    fail = sum(1 for r in results if not r["ok"])
    print(f"Submitted: {ok} | Failed: {fail} | Total: {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
