import asyncio
from playwright.async_api import async_playwright

async def lookup():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        # Check the PD2 wiki for items with +summon skills
        await page.goto('https://pd2.tools', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)
        text = await page.inner_text('body')
        print(text[:3000])
        
        await page.close()

asyncio.run(lookup())
