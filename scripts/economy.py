from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import timedelta
from typing import Any

from config import CHROME_DEBUG_URL, ECONOMY_FILE, ECONOMY_REFRESH_HOURS, PD2_TOOLS_ECONOMY_URLS
from history import StateStore, parse_iso, to_iso, utc_now

logger = logging.getLogger(__name__)

ROW_RE = re.compile(r"(?P<name>[A-Za-z0-9'\-+:,()/ ]+?)\s+WIKI\s+(?P<price>[\d.]+)\s*HR", re.IGNORECASE | re.MULTILINE)
ALT_ROW_RE = re.compile(r"(?P<name>[A-Za-z0-9'\-+:,()/ ]+?)\s+(?P<price>[\d.]+)\s*HR", re.IGNORECASE | re.MULTILINE)


class EconomyManager:
    def __init__(self, state: StateStore | None = None):
        self.state = state or StateStore()

    def load(self) -> dict[str, Any]:
        if not ECONOMY_FILE.exists():
            return {"refreshed_at": None, "sources": {}, "values": {}}
        try:
            return json.loads(ECONOMY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"refreshed_at": None, "sources": {}, "values": {}}

    def parse_values(self, text: str) -> dict[str, float]:
        values: dict[str, float] = {}
        for pattern in (ROW_RE, ALT_ROW_RE):
            for match in pattern.finditer(text):
                name = " ".join(match.group("name").split())
                try:
                    values[name] = float(match.group("price"))
                except ValueError:
                    continue
        return values

    async def _fetch_page(self, page, url: str) -> str:
        """Fetch a page using Playwright (avoids 403 from pd2.tools)."""
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        return await page.inner_text("body")

    async def refresh(self, force: bool = False) -> dict[str, Any]:
        current = self.load()
        last_refresh = parse_iso(current.get("refreshed_at")) if current else None
        if not force and last_refresh and utc_now() - last_refresh < timedelta(hours=ECONOMY_REFRESH_HOURS):
            return current
        try:
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(CHROME_DEBUG_URL)
            context = browser.contexts[0]
            page = await context.new_page()
            try:
                sources: dict[str, Any] = {}
                combined_values: dict[str, float] = {}
                for category, url in PD2_TOOLS_ECONOMY_URLS.items():
                    try:
                        text = await self._fetch_page(page, url)
                        parsed = self.parse_values(text)
                        sources[category] = {"url": url, "values": parsed, "value_count": len(parsed)}
                        combined_values.update(parsed)
                        logger.info("Economy %s: %d values from %s", category, len(parsed), url)
                    except Exception as exc:
                        logger.warning("Failed to fetch economy/%s: %s", category, exc)
                        sources[category] = {"url": url, "error": str(exc), "values": {}}
                payload = {
                    "refreshed_at": to_iso(),
                    "sources": sources,
                    "values": combined_values,
                }
                ECONOMY_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                self.state.set_economy_refresh()
                self.state.save()
                return payload
            finally:
                await page.close()
                await playwright.stop()
        except Exception as exc:
            logger.error("Economy refresh failed: %s — using cached data", exc)
            return self.load()

    async def ensure_fresh(self, force: bool = False) -> dict[str, Any]:
        return await self.refresh(force=force)

    def value_for(self, name: str | None) -> float | None:
        if not name:
            return None
        data = self.load()
        values = data.get("values", {})
        if name in values:
            return values[name]
        normalized = name.lower()
        for key, value in values.items():
            if key.lower() == normalized or key.lower() in normalized or normalized in key.lower():
                return value
        return None
