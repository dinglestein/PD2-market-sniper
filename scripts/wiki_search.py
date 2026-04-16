import asyncio
from playwright.async_api import async_playwright

async def search_wiki():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        # Navigate to PD2 wiki and search for items
        await page.goto('https://www.projectdiablo2.com/wiki/index.php?title=Brand', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)
        text = await page.inner_text('body')
        print("=== Brand Runeword ===")
        print(text[:3000])
        
        await page.close()

asyncio.run(search_wiki())
