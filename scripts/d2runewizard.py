import asyncio
from playwright.async_api import async_playwright

async def check_items():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        items = [
            ("Brand", "https://d2runewizard.com/diablo-2-runewords/Brand"),
            ("Undead Crown", "https://d2runewizard.com/diablo-2-unique-items/Undead-Crown"),
            ("TombSong Quiver", "https://d2runewizard.com/diablo-2-crafting-recipes/TombSong"),
        ]
        
        for name, url in items:
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(3)
                text = await page.inner_text('body')
                print(f"\n=== {name} ===")
                print(text[:1500])
            except Exception as e:
                print(f"\n=== {name} === Error: {e}")
        
        await page.close()

asyncio.run(check_items())
