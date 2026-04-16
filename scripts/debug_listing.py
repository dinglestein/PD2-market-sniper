import asyncio
from playwright.async_api import async_playwright

async def debug_listing():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        await page.goto('https://www.projectdiablo2.com/market?filter=6945027864537e558cdc2199', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(8)
        
        # Get the HTML structure around OFFER buttons
        offer_btns = page.locator('button.button.gold:has-text("OFFER")')
        count = await offer_btns.count()
        print(f"Found {count} OFFER buttons")
        
        # For each OFFER button, get its parent containers and their classes
        for i in range(min(count, 3)):
            btn = offer_btns.nth(i)
            print(f"\n--- Listing {i} ---")
            for level in range(1, 10):
                try:
                    ancestor = btn.locator(f"xpath=ancestor::*[{level}]").first
                    tag = await ancestor.evaluate("el => el.tagName")
                    cls = await ancestor.get_attribute("class") or ""
                    if len(cls) > 80:
                        cls = cls[:80] + "..."
                    text = (await ancestor.inner_text()).strip()[:150].replace("\n", " | ")
                    print(f"  Level {level}: <{tag} class=\"{cls}\"> text: {text}")
                except:
                    pass
        
        await page.close()

asyncio.run(debug_listing())
