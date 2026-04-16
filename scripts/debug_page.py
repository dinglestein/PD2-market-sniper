import asyncio
from playwright.async_api import async_playwright

async def check_page():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        # Try with a simpler filter that might have results
        await page.goto('https://www.projectdiablo2.com/market?filter=65271a289ce496e3a8a3194a', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(10)
        
        text = await page.inner_text('body')
        # Look for key indicators
        if 'SEARCH TO SEE RESULTS' in text:
            print("Page says 'SEARCH TO SEE RESULTS' - no items loaded")
        elif 'NO RESULTS' in text.upper() or '0 ITEMS' in text.upper():
            print("No results found for this filter")
        elif 'OFFER' in text or 'BUY' in text:
            print(f"Items found! Page has OFFER/BUY buttons")
            # Count them
            offer_btns = page.locator('button')
            btn_count = await offer_btns.count()
            for j in range(min(btn_count, 20)):
                txt = (await offer_btns.nth(j).inner_text()).strip()
                if txt:
                    print(f"  Button: {txt}")
        
        print(f"\nFirst 2000 chars:\n{text[:2000]}")
        await page.screenshot(path=r'C:\Users\jding\.agents\skills\pd2-market-sniper\screenshots\debug_page.png')
        await page.close()

asyncio.run(check_page())
