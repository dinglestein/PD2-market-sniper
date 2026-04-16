import asyncio
from playwright.async_api import async_playwright

async def check_market():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        # Main market page - no filter
        await page.goto('https://www.projectdiablo2.com/market', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(8)
        
        text = await page.inner_text('body')
        first_part = text[:3000]
        
        if 'NO ITEMS' in text or 'SEARCH TO SEE' in text:
            print("Empty market / needs search")
        else:
            print(f"Market has content")
            print(first_part)
        
        # Try searching broadly
        # Click in search or try loading without filter
        await page.screenshot(path=r'C:\Users\jding\.agents\skills\pd2-market-sniper\screenshots\main_market.png')
        await page.close()

asyncio.run(check_market())
