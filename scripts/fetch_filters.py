#!/usr/bin/env python3
"""Fetch all saved filter IDs and names from projectdiablo2.com market page."""
import asyncio
import json
import re
from playwright.async_api import async_playwright


async def main():
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = await ctx.new_page()

    # Track API responses
    api_data = []

    async def handle_response(response):
        url = response.url
        if "saved" in url.lower() or "filter" in url.lower():
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    data = await response.json()
                    api_data.append({"url": url, "data": data})
                    print(f"  [API] {url} -> {str(data)[:200]}")
            except Exception:
                pass

    page.on("response", handle_response)

    print("Loading market page...")
    await page.goto("https://www.projectdiablo2.com/market", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(3)

    # Try clicking FILTERS tab
    try:
        filters_tab = page.locator("text=FILTERS")
        if await filters_tab.count() > 0:
            await filters_tab.first.click()
            await asyncio.sleep(5)
            print("Clicked FILTERS tab")
    except Exception as e:
        print(f"Error clicking filters tab: {e}")

    # Get page text to see what's visible
    text = await page.inner_text("body")
    # Extract the MY FILTERS section
    if "MY FILTERS" in text:
        idx = text.index("MY FILTERS")
        section = text[idx:idx+5000]
        print(f"\nMY FILTERS section:\n{section}")
    else:
        print("\nNo MY FILTERS section found")

    # Check for filter-related network requests
    print(f"\nAPI responses captured: {len(api_data)}")
    for item in api_data:
        print(f"  URL: {item['url']}")
        print(f"  Data: {json.dumps(item['data'], indent=2)[:1000]}")
        print()

    # Check localStorage
    local_data = await page.evaluate("""() => {
        const keys = Object.keys(localStorage);
        const filterKeys = keys.filter(k => k.toLowerCase().includes('filter') || k.toLowerCase().includes('saved'));
        const result = {};
        for (const k of filterKeys) {
            result[k] = localStorage.getItem(k).substring(0, 500);
        }
        return result;
    }""")
    print(f"\nLocalStorage filter keys: {list(local_data.keys())}")
    for k, v in local_data.items():
        print(f"  {k}: {v[:300]}")

    # Try to find filter links in the page
    filter_links = await page.eval_on_selector_all("a[href*='filter=']", """els => els.map(el => ({
        text: el.textContent.trim().substring(0, 80),
        href: el.getAttribute('href')
    }))""")
    print(f"\nFilter links found: {len(filter_links)}")
    for fl in filter_links:
        print(f"  {fl['text']} -> {fl['href']}")

    # Also check for any elements with filter data
    filter_elements = await page.evaluate("""() => {
        const results = [];
        // Look for any elements that might contain saved filters
        const allElements = document.querySelectorAll('[data-id], [data-filter], .filter-name, .saved-filter');
        for (const el of allElements) {
            const text = el.textContent.trim().substring(0, 100);
            const dataId = el.getAttribute('data-id') || '';
            const dataFilter = el.getAttribute('data-filter') || '';
            if (text && (dataId || dataFilter)) {
                results.push({text, dataId, dataFilter});
            }
        }
        return results;
    }""")
    print(f"\nFilter elements with data attributes: {len(filter_elements)}")
    for fe in filter_elements[:30]:
        print(f"  {fe}")

    # Get all 24-char hex IDs from page source
    html = await page.content()
    hex_ids = re.findall(r'["\']([0-9a-f]{24})["\']', html)
    unique_ids = list(set(hex_ids))
    print(f"\n24-char hex IDs in page: {len(unique_ids)}")
    for hid in unique_ids[:50]:
        print(f"  {hid}")

    # Try to intercept fetch/XHR for saved filters API
    # Let's try a direct API call
    print("\n\nTrying direct API calls...")
    for endpoint in [
        "/api/market/saved-filters",
        "/api/market/filters/saved",
        "/api/user/filters",
        "/api/saved-filters",
    ]:
        try:
            resp = await page.goto(f"https://www.projectdiablo2.com{endpoint}", wait_until="domcontentloaded", timeout=10000)
            status = resp.status if resp else "no response"
            body = await page.inner_text("body") if resp else ""
            print(f"  {endpoint}: {status} -> {body[:200]}")
        except Exception as e:
            print(f"  {endpoint}: {e}")

    await page.close()
    await p.stop()


asyncio.run(main())
