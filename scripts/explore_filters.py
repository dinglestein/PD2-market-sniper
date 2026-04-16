import asyncio
from playwright.async_api import async_playwright

async def explore_filters():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        # Go to filters page
        print("=== Loading PD2 Market Filters ===")
        await page.goto('https://www.projectdiablo2.com/market/filters', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(5)
        
        text = await page.inner_text('body')
        print(f"\n=== Page Text ===\n{text[:5000]}")
        
        # Get HTML of filter area
        html = await page.content()
        # Save full HTML for analysis
        with open(r'C:\Users\jding\.agents\skills\pd2-market-sniper\screenshots\filters_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("\nFull HTML saved.")
        
        # Look for filter selects
        selects = await page.query_selector_all('select')
        print(f"\n=== Dropdowns ({len(selects)}) ===")
        for s in selects:
            name = await s.get_attribute('name') or await s.get_attribute('id') or '?'
            opts = await s.query_selector_all('option')
            opt_texts = [(await o.get_attribute('value'), await o.inner_text()) for o in opts[:15]]
            print(f"  {name}: {opt_texts}")
        
        # Look for buttons
        buttons = await page.query_selector_all('button')
        print(f"\n=== Buttons ({len(buttons)}) ===")
        for b in buttons:
            txt = (await b.inner_text()).strip()[:80]
            cls = await b.get_attribute('class') or ''
            if txt:
                print(f"  [{cls[:40]}] {txt}")
        
        await page.screenshot(path=r'C:\Users\jding\.agents\skills\pd2-market-sniper\screenshots\filters_page.png')
        print("Screenshot saved.")
        await page.close()

asyncio.run(explore_filters())
