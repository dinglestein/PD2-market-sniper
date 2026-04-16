import asyncio
import json
from playwright.async_api import async_playwright

async def get_currency():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        await page.goto('https://pd2.tools/economy/currency', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(5)
        
        text = await page.inner_text('body')
        print(text[:5000])
        
        # Save
        with open(r'C:\Users\jding\.agents\skills\pd2-market-sniper\assets\currency_values.json', 'w') as f:
            json.dump({"raw_text": text[:5000], "fetched": "2026-04-16"}, f, indent=2)
        
        await page.close()

asyncio.run(get_currency())
