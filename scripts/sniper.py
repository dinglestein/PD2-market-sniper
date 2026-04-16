#!/usr/bin/env python3
"""
PD2 Market Sniper - Scan saved filters for cheap items and auto-offer.
Connects to Chrome via remote debugging (port 9222).

Usage:
  python sniper.py scan [--filter-id ID] [--max-price HR] [--interval SECONDS]
  python sniper.py offer --listing-url URL [--amount HR]
  python sniper.py filters  # List all saved filters
"""
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
SCREENSHOTS = SKILL_DIR / "screenshots"
STATE_FILE = SKILL_DIR / "sniper_state.json"
SEEN_FILE = SKILL_DIR / "seen_items.json"

# Your saved filters (softcore ladder) — Season 13
FILTERS = {
    # --- New S13 filters ---
    "69e0c58f9fc33c4bc7fe0483": "tombsong +skill",
    "69e0ba2f9fc33c4bc7fe043c": "passive GC +GF",
    "69e0b9fd9fc33c4bc7fe043a": "passive glove +2-20p",
    "69e0b9df9fc33c4bc7fe0439": "passive glove +3-20",
    "69e0b9d49fc33c4bc7fe0438": "passive glove +3-30",
    "69e0b9999fc33c4bc7fe0434": "arachnid +20 FCR",
    "69e0b97a9fc33c4bc7fe0433": "valkyrie wing +3 OS",
    "69e0b96c9fc33c4bc7fe0430": "valkyrie wing +skill",
    "69e0b9459fc33c4bc7fe042f": "undead crown +1skill",
    "69e0b90a9fc33c4bc7fe042e": "tombsong +IAS",
    "69e0b8e09fc33c4bc7fe042d": "tombsong +40 pierce",
    "69e0b8ae9fc33c4bc7fe042c": "passive amulet +5",
    "69e0b8a49fc33c4bc7fe042b": "passive amulet +4",
    "69e0b89b9fc33c4bc7fe042a": "passive amulet +3",
    "69e0b5a89fc33c4bc7fe0423": "witchwild +4OS",
    "69e0b5499fc33c4bc7fe0422": "gravepalm +15 DS",
    "69e0b5289fc33c4bc7fe0421": "ebonbane +CB",
    "69e0b51a9fc33c4bc7fe0420": "ebonbane +DS",
    "69e0b4a69fc33c4bc7fe041e": "ebonbane +5os",
    "69e0b47f9fc33c4bc7fe041d": "highlords +ED",
    "69e0b3859fc33c4bc7fe041b": "war trav +frw",
    "69e0b27d9fc33c4bc7fe0419": "gore rider +20 ds",
    "69e0b22d9fc33c4bc7fe0417": "gface +3os",
    "69e0b1db9fc33c4bc7fe0416": "windforce +6os",
    "69e0b18e9fc33c4bc7fe0415": "passive frw GC",
    "69e0b1819fc33c4bc7fe0414": "passive lifer GC",
    "69e0b1629fc33c4bc7fe0413": "atmas +ED",
    "69e0b1509fc33c4bc7fe040e": "atmas +pierce",
    "69e0af2e9fc33c4bc7fe0402": "wraithskin +3os",
    # --- Carried over from S12 ---
    "6950f46ee7a71fc913434b2e": "jav lifer gc",
    "694ad153d295043717c07851": "lite +fhr gc",
    "69411fadbf10a6a498b09ad3": "highlords cbf pierce",
    "693ab400f2584d3e203bee44": "dooms finger +pierce",
    "6939ab117306724e1ce95a90": "bow amp",
    "693134635b1401db14af4642": "spear +amp",
    "693133fe5b1401db14af460e": "war pike +amp",
    "652d6e79813c6cf6f9f24327": "string +all res",
    "652d71d0813c6cf6f9f2436e": "veil +2sk",
    "652d72c2813c6cf6f9f24389": "tyreals",
    "652dfa94ef6e111f977af738": "veil +3os",
    "652e3474dd17e67bc4f98dd2": "BK dual leech",
    "652f714c1fcdfe27910c4199": "bk deathband +leech",
    "6530cb6410db0dc1c4bcda97": "steelrend +deadly",
    "6530cd7410db0dc1c4bcdaa1": "metalgrid +skill",
    "6530de0f10db0dc1c4bcdb14": "metalgrid +cbf",
    "6531f2671067d5a9b3b3d8b9": "atmas +skill",
    "6531f2751067d5a9b3b3d8ba": "atmas +cbf",
    "6531f7112ee1d8d90c9bfd49": "string +max",
    "65320da5fe8a8d3bcff60cdc": "rising sun +skill",
    "6535716ef2ccca08ffd63401": "nosferatu +30 ias",
    "6539c93c3df75bcdae8150f9": "CoA +skill 3os",
    "662315bda0c6f8ef4728877d": "headhunter +1 3os",
    "66253bc516f7f756fa0c2f18": "headhunters +1skill",
    "66259dfc35b8b359394e58c1": "metalgrid +IAS",
    "6848c66a4444294e327a1f49": "fcr dual leach ring",
    "684bb5e7a48bb1e3fd0c3983": "quad res booties",
    "684d78ee9a66c929a9c2d47c": "half freeze trires b",
    "684de0e2b51112230875a22c": "construct 30fcr",
    "6853c3fe872cdd8e946221b3": "spirit ward +3os",
}

def parse_price(price_str):
    """Parse price string like '420HR', '0.25 HR', '5 HR' into float."""
    price_str = price_str.strip().upper().replace(",", "").replace(" ", "")
    match = re.match(r"([\d.]+)\s*HR?", price_str)
    if match:
        return float(match.group(1))
    return None

def load_seen():
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return {}

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)

async def get_browser():
    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    return p, browser

async def scan_filter(page, filter_id, filter_name, max_price_hr=0.5):
    """Scan a single filter for items at or below max_price_hr. Returns list of found items."""
    url = f"https://www.projectdiablo2.com/market?filter={filter_id}"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(6)
    
    text = await page.inner_text("body")
    
    items = []
    
    # Parse listings from page text
    # Pattern: item stats block, then Price: XHR, then OFFER/BUY, then seller
    # The page has the item listing area before the filter sidebar
    
    # Find all "OFFER" buttons - each corresponds to a listing
    offer_buttons = page.locator('button.button.gold:has-text("OFFER")')
    count = await offer_buttons.count()
    
    for i in range(count):
        try:
            btn = offer_buttons.nth(i)
            # Get the parent listing container
            parent = btn.locator("xpath=ancestor::*[@class]").first
            
            # Get the listing text (everything visible in the listing container)
            # Walk up to find the right container
            listing_text = ""
            for level in range(1, 8):
                try:
                    ancestor = btn.locator(f"xpath=ancestor::*[{level}]").first
                    cls = await ancestor.get_attribute("class") or ""
                    if "panel" in cls or "item" in cls or "card" in cls:
                        listing_text = await ancestor.inner_text()
                        break
                except:
                    continue
            
            if not listing_text:
                listing_text = await btn.locator("xpath=ancestor::div[2]").first.inner_text()
            
            # Extract price from listing text
            price_match = re.search(r"Price:\s*([\d.,]+)\s*HR?", listing_text, re.IGNORECASE)
            if price_match:
                price = parse_price(price_match.group(1) + "HR")
            else:
                # Try to find price near the offer button
                price = None
            
            # Extract item name (usually the first bold/large text)
            lines = listing_text.strip().split("\n")
            item_name = lines[0].strip() if lines else "Unknown"
            
            # Extract seller
            seller = ""
            for line in lines:
                if "about" in line.lower() and ("ago" in line.lower() or "hour" in line.lower() or "min" in line.lower()):
                    # Seller is usually the line before time posted
                    continue
                if "softcore" in line.lower() and "ladder" in line.lower():
                    continue
            
            # Try to get the item link/href
            listing_url = url  # Default to filter URL
            
            item = {
                "filter": filter_name,
                "filter_id": filter_id,
                "item": item_name,
                "price": price,
                "seller": seller,
                "text_preview": listing_text[:200],
                "url": listing_url,
                "found_at": datetime.now().isoformat(),
            }
            items.append(item)
        except Exception as e:
            print(f"  Error parsing listing {i}: {e}")
    
    # Filter by max price
    cheap_items = [it for it in items if it["price"] is not None and it["price"] <= max_price_hr]
    no_price_items = [it for it in items if it["price"] is None]
    
    return cheap_items, no_price_items

async def make_offer(page, listing_index=0, amount_hr=0.25):
    """Click the OFFER button on a listing and submit a lowball offer."""
    try:
        # Find OFFER buttons (the listing ones, not search/filter ones)
        offer_buttons = page.locator('button.button.gold:has-text("OFFER")')
        btn = offer_buttons.nth(listing_index)
        
        if not await btn.is_visible():
            print("  OFFER button not visible")
            return False
        
        await btn.click()
        await asyncio.sleep(2)
        
        # Find the offer input (name="Offer")
        offer_input = page.locator('input[name="Offer"]')
        if await offer_input.count() > 0:
            await offer_input.first.fill(str(amount_hr))
            await asyncio.sleep(1)
            
            # Click SUBMIT
            submit_btn = page.locator('button:has-text("SUBMIT")')
            if await submit_btn.is_visible():
                await submit_btn.click()
                await asyncio.sleep(2)
                print(f"  Offer of {amount_hr}HR submitted!")
                return True
        
        print("  Could not complete offer flow")
        return False
    except Exception as e:
        print(f"  Offer error: {e}")
        return False

async def scan_all_filters(max_price_hr=0.5):
    """Scan all saved filters for cheap items."""
    p, browser = await get_browser()
    ctx = browser.contexts[0]
    page = await ctx.new_page()
    
    seen = load_seen()
    all_deals = []
    all_needs_review = []
    
    print(f"Scanning {len(FILTERS)} filters for items <= {max_price_hr} HR...\n")
    
    for fid, fname in FILTERS.items():
        try:
            cheap, no_price = await scan_filter(page, fid, fname, max_price_hr)
            
            for item in cheap:
                key = f"{fid}:{item['item']}:{item['price']}"
                if key not in seen:
                    seen[key] = datetime.now().isoformat()
                    all_deals.append(item)
                    print(f"  DEAL: {item['item']} @ {item['price']}HR (filter: {fname})")
                else:
                    print(f"  [seen] {item['item']} @ {item['price']}HR")
            
            for item in no_price:
                all_needs_review.append(item)
                
        except Exception as e:
            print(f"  Error scanning {fname}: {e}")
        
        await asyncio.sleep(2)  # Be polite
    
    save_seen(seen)
    await page.close()
    await p.stop()
    
    return all_deals, all_needs_review

def list_filters():
    """Print all saved filters."""
    print(f"You have {len(FILTERS)} saved filters:\n")
    for fid, fname in FILTERS.items():
        print(f"  {fname}")
    print(f"\nURL format: https://www.projectdiablo2.com/market?filter={{id}}")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python sniper.py [scan|offer|filters]")
        print("  scan [--max-price 0.5] [--filter-id ID]")
        print("  offer --amount 0.25")
        print("  filters")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "filters":
        list_filters()
    
    elif cmd == "scan":
        max_price = 0.5
        filter_id = None
        
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--max-price" and i + 1 < len(args):
                max_price = float(args[i + 1])
                i += 2
            elif args[i] == "--filter-id" and i + 1 < len(args):
                filter_id = args[i + 1]
                i += 2
            else:
                i += 1
        
        if filter_id:
            # Scan single filter
            p, browser = await get_browser()
            ctx = browser.contexts[0]
            page = await ctx.new_page()
            fname = FILTERS.get(filter_id, "Unknown")
            cheap, no_price = await scan_filter(page, filter_id, fname, max_price)
            print(f"\nFound {len(cheap)} items <= {max_price}HR")
            for item in cheap:
                print(f"  {item['item']} @ {item['price']}HR")
            if no_price:
                print(f"\n{len(no_price)} items with no detectable price (need review)")
            await page.close()
            await p.stop()
        else:
            deals, needs_review = await scan_all_filters(max_price)
            print(f"\n=== RESULTS ===")
            print(f"New deals found: {len(deals)}")
            print(f"Items needing price review: {len(needs_review)}")
            
            # Save results
            results = {
                "timestamp": datetime.now().isoformat(),
                "deals": deals,
                "needs_review": needs_review,
            }
            output = SKILL_DIR / "scan_results.json"
            with open(output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {output}")
    
    elif cmd == "offer":
        amount = 0.25
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--amount" and i + 1 < len(args):
                amount = float(args[i + 1])
                i += 2
            else:
                i += 1
        
        p, browser = await get_browser()
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        
        success = await make_offer(page, listing_index=0, amount_hr=amount)
        await page.close()
        await p.stop()
    
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    asyncio.run(main())
