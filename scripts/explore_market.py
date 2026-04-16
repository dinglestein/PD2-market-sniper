import asyncio
import json
from playwright.async_api import async_playwright

async def explore():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        print("=== Loading PD2 Market ===")
        await page.goto('https://www.projectdiablo2.com/market', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(6)
        
        # Check login status
        text = await page.inner_text('body')
        print(f"\n=== Page Text (first 3000 chars) ===\n{text[:3000]}")
        
        # Find all select/dropdown elements
        selects = await page.query_selector_all('select')
        print(f"\n=== Dropdowns ({len(selects)}) ===")
        for s in selects:
            name = await s.get_attribute('name') or await s.get_attribute('id') or '?'
            opts = await s.query_selector_all('option')
            opt_texts = [(await o.inner_text()) for o in opts[:10]]
            print(f"  {name}: {opt_texts}")
        
        # Find all links
        links = await page.query_selector_all('a')
        print(f"\n=== Links ({len(links)}) ===")
        for l in links[:20]:
            href = await l.get_attribute('href') or ''
            txt = (await l.inner_text()).strip()[:50]
            if txt:
                print(f"  {txt} -> {href}")
        
        # Look for filter-related elements
        filters = await page.query_selector_all('[class*=filter], [id*=filter], [data-filter]')
        print(f"\n=== Filter Elements ({len(filters)}) ===")
        for f in filters[:10]:
            cls = await f.get_attribute('class') or ''
            eid = await f.get_attribute('id') or ''
            txt = (await f.inner_text()).strip()[:100]
            print(f"  [{cls}] [{eid}] {txt}")
        
        # Look for "My Filters" or saved filter elements
        # Screenshot
        await page.screenshot(path=r'C:\Users\jding\.agents\skills\pd2-market-sniper\screenshots\market_main.png')
        print("\nScreenshot saved.")
        
        await page.close()

asyncio.run(explore())
