import asyncio
import json
from playwright.async_api import async_playwright

async def scrape_all():
    urls = {
        "currency": "https://pd2.tools/economy/currency",
        "runes": "https://pd2.tools/economy/runes",
        "ubers": "https://pd2.tools/economy/ubers",
        "maps": "https://pd2.tools/economy/maps",
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        all_data = {}
        
        for name, url in urls.items():
            print(f"Scraping {name}...")
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(5)
            text = await page.inner_text('body')
            all_data[name] = {"url": url, "text": text}
            print(text[:2000])
            print("---")
        
        await page.close()
        
        with open(r'C:\Users\jding\.agents\skills\pd2-market-sniper\assets\all_economy.json', 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print("Saved to all_economy.json")

asyncio.run(scrape_all())
