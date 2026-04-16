import asyncio
from playwright.async_api import async_playwright

async def search_items():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        # Try PD2 tools item database
        await page.goto('https://pd2.tools/items', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(5)
        text = await page.inner_text('body')
        print(text[:5000])
        
        await page.close()

asyncio.run(search_items())
