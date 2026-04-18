#!/usr/bin/env python3
"""Quick script to inspect the offer form on a PD2 listing."""
import asyncio
import json
from playwright.async_api import async_playwright

TARGET_URL = "https://www.projectdiablo2.com/market/listing/69d5d19d32db2411b6582643"

async def check():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = await ctx.new_page()
    await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    # Click OFFER button
    btn = page.locator("button:has-text('OFFER')").first
    await btn.click(timeout=10000)
    await asyncio.sleep(2)

    # Find all form inputs
    inputs = await page.query_selector_all("input, select, textarea")
    for inp in inputs:
        attrs = await inp.evaluate("el => ({type: el.type, name: el.name, placeholder: el.placeholder, id: el.id, value: el.value})")
        print(json.dumps(attrs))

    # Also get surrounding form/modal HTML
    modals = await page.query_selector_all("[class*=modal], [class*=offer], form")
    for m in modals:
        html = await m.inner_html()
        print(f"--- element ---\n{html[:2000]}")

    await page.close()
    await pw.stop()

asyncio.run(check())
