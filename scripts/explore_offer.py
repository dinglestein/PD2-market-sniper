import asyncio
from playwright.async_api import async_playwright

async def explore_offer():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        # Load filter
        await page.goto('https://www.projectdiablo2.com/market?filter=6945027864537e558cdc2199', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(8)
        
        # Click OFFER button
        offer_btn = page.locator('button.button.gold:has-text("OFFER")').first
        if await offer_btn.is_visible():
            await offer_btn.click()
            print("Clicked OFFER button")
            await asyncio.sleep(3)
            
            # Get the offer dialog/modal content
            text = await page.inner_text('body')
            print(f"\n=== Page after OFFER click (last 3000 chars) ===\n{text[-3000:]}")
            
            # Look for input fields
            inputs = await page.query_selector_all('input, textarea, select')
            print(f"\n=== Input fields ({len(inputs)}) ===")
            for inp in inputs:
                name = await inp.get_attribute('name') or await inp.get_attribute('placeholder') or await inp.get_attribute('type') or '?'
                val = await inp.input_value()
                print(f"  [{name}] value={val}")
            
            # Look for new buttons after modal
            buttons = await page.query_selector_all('button:visible')
            print(f"\n=== Visible buttons ({len(buttons)}) ===")
            for b in buttons:
                txt = (await b.inner_text()).strip()[:80]
                if txt:
                    print(f"  {txt}")
            
            await page.screenshot(path=r'C:\Users\jding\.agents\skills\pd2-market-sniper\screenshots\offer_dialog.png')
            print("Screenshot saved.")
        else:
            print("No OFFER button found")
        
        await page.close()

asyncio.run(explore_offer())
