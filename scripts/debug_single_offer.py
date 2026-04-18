#!/usr/bin/env python3
"""Debug: try a single WSS offer to see what happens."""
import asyncio
from playwright.async_api import async_playwright

CHROME_DEBUG_URL = "http://localhost:9222"
TARGET_URL = "https://www.projectdiablo2.com/market/listing/69d5d19d32db2411b6582643"


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CHROME_DEBUG_URL)
    ctx = browser.contexts[0]
    page = await ctx.new_page()

    print("Navigating to listing...")
    await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    print(f"Page URL: {page.url}")

    # Find and click OFFER
    offer_btn = page.locator("button:has-text('OFFER')").first
    btn_count = await offer_btn.count()
    print(f"OFFER buttons found: {btn_count}")

    if btn_count > 0:
        await offer_btn.click(timeout=10000)
        print("Clicked OFFER, waiting for modal...")
        await asyncio.sleep(2)

        # List all visible inputs
        inputs = await page.query_selector_all("input:visible, select:visible, textarea:visible")
        print(f"Visible inputs: {len(inputs)}")
        for inp in inputs:
            attrs = await inp.evaluate("el => ({type: el.type, name: el.name, placeholder: el.placeholder, id: el.id, tag: el.tagName})")
            print(f"  {attrs}")

        # Try filling
        if inputs:
            # Type into currency field to reveal the quantity input
            currency_input = page.locator('input[placeholder="Offer"]').first
            c_count = await currency_input.count()
            print(f"Currency input count: {c_count}")
            if c_count > 0:
                await currency_input.fill("wss")
                print("Filled currency: wss")
                await asyncio.sleep(1)  # Wait for dynamic field to appear

            amount_input = page.locator('input[placeholder="#"]').first
            a_count = await amount_input.count()
            print(f"Amount input count: {a_count}")
            if a_count > 0:
                await amount_input.fill("10", force=True)
                print("Filled amount: 10")
            else:
                print("# field not visible - may need different approach")
                # Dump ALL inputs again
                all_inputs = await page.query_selector_all("input")
                for inp in all_inputs:
                    attrs = await inp.evaluate("el => ({type: el.type, name: el.name, placeholder: el.placeholder, id: el.id, visible: el.offsetParent !== null})")
                    print(f"  {attrs}")

            # Find submit
            submit_btn = page.locator("button:has-text('SUBMIT')").first
            s_count = await submit_btn.count()
            print(f"SUBMIT buttons: {s_count}")
            if s_count > 0:
                await submit_btn.click(timeout=10000)
                print("Clicked SUBMIT!")
                await asyncio.sleep(3)
                print("Offer submitted (hopefully)")
            else:
                print("No SUBMIT button found!")
                # Dump all buttons
                buttons = await page.query_selector_all("button:visible")
                for b in buttons:
                    txt = await b.inner_text()
                    print(f"  Button: '{txt}'")
    else:
        print("No OFFER button found - listing may be sold or different layout")
        content = await page.inner_text("body")
        print(f"Page text preview: {content[:500]}")

    await page.close()
    await pw.stop()
    print("Done.")


asyncio.run(main())
