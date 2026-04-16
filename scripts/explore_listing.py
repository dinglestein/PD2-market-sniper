import asyncio
import json
from playwright.async_api import async_playwright

async def explore_listing():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        # Load a filter to see listings
        print("=== Loading filter: arachs +30fcr ===")
        await page.goto('https://www.projectdiablo2.com/market?filter=6945027864537e558cdc2199', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(8)
        
        text = await page.inner_text('body')
        print(f"\n=== Page Text (first 5000 chars) ===\n{text[:5000]}")
        
        # Find item cards/listings
        cards = await page.query_selector_all('[class*=item], [class*=card], [class*=listing], [class*=entry]')
        print(f"\n=== Item-like elements: {len(cards)} ===")
        
        # Look for price elements
        prices = await page.query_selector_all('[class*=price], [class*=buyout], [class*=offer]')
        print(f"=== Price elements: {len(prices)} ===")
        
        # Look for action buttons
        actions = await page.query_selector_all('button')
        print(f"\n=== Buttons ({len(actions)}) ===")
        for b in actions:
            txt = (await b.inner_text()).strip()[:80]
            cls = await b.get_attribute('class') or ''
            if txt:
                print(f"  [{cls[:50]}] {txt}")
        
        await page.screenshot(path=r'C:\Users\jding\.agents\skills\pd2-market-sniper\screenshots\filter_results.png')
        print("Screenshot saved.")
        await page.close()

asyncio.run(explore_listing())
