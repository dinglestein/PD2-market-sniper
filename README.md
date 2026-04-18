# PD2 Market Sniper 🎯

Project Diablo 2 marketplace scanner and deal hunter for softcore ladder.

Scans saved PD2 market filters, ranks deals using live price data from PD2Trader, captures screenshots and direct listing links, and submits offers through chat — you just say the amount.

Account used in testing: `d1ngl3`

## What It Does

- Scans saved market filters with randomized delays and conservative cadence
- Finds listings under a configurable HR threshold
- **Fetches live economy data from PD2Trader API** — median prices, 7-day trends, sample counts
- Ranks deals with price confidence scoring (high/medium/low based on listing volume)
- Captures screenshots of found listings
- Submits offers via REST API (browser fallback) — no manual clicking needed
- Presents deal cards in chat, you reply with an amount like `0.4`
- Tracks offer history, seen items, scan rotation, filter health
- Generates an HTML dashboard with search, economy sync, scan controls, and server status
- Notifies the AI assistant when scans complete for interactive deal review

## Architecture

### Core Modules

| File | Purpose |
|------|---------|
| `scripts/sniper.py` | CLI entry point and command routing |
| `scripts/scanner.py` | Scan orchestration, browser control, result collection |
| `scripts/pd2_api.py` | **REST API client** — PD2Trader prices + PD2 market/offers/chat |
| `scripts/market_search.py` | **Direct market search** via API (no browser needed) |
| `scripts/economy.py` | Economy data via PD2Trader API (no Playwright!) |
| `scripts/offers.py` | Offer submission (API first, browser fallback) |
| `scripts/alerts.py` | Deal scoring, operator alerts, price confidence |
| `scripts/parsers.py` | DOM/API listing parsing |
| `scripts/history.py` | Seen items, offer history, pending deal state, filter health |
| `scripts/dashboard.py` | HTML dashboard generation |
| `scripts/server.py` | Local HTTP server (port 8420) for dashboard + API |
| `scripts/config.py` | Shared config and filter list |

### Data Sources

- **PD2Trader API** (`pd2trader.com`) — median prices, batch lookups, 7-day trends, corruption prices, sample counts. No auth required.
- **PD2 Market API** (`api.projectdiablo2.com`) — market listings, offer submission, incoming/outgoing offers, chat. Requires JWT auth token.
- **Browser (Playwright/CDP)** — fallback for offer submission and scanning when API auth isn't available. Chrome on port 9222.

### Dashboard Server

A local HTTP server on port 8420 serves the dashboard and provides API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML |
| `/api/status` | GET | Server status, scan state |
| `/api/scan` | POST | Start background scan |
| `/api/economy-refresh` | POST | Refresh economy data |
| `/api/refresh-dashboard` | POST | Regenerate dashboard HTML |
| `/api/reset` | POST | Clear all state (new season) |
| `/api/price-check` | POST | Check item price confidence |
| `/api/market-search` | POST | Direct market search via API |
| `/api/offer-status` | GET | Incoming/outgoing offers |

## Commands

### Operator Workflow (Recommended)

The full interactive flow — scan, present deals, user picks price:

```bash
# 1. Run operator scan
python scripts/sniper.py operator-scan --max-price 999 --filters-per-cycle 100 --daily-limit 200 --max-pages 50 --top 3

# 2. View pending deal
python scripts/sniper.py pending

# 3. Submit offer amount
python scripts/sniper.py reply-offer 0.4
```

### Dashboard Server

```bash
python scripts/sniper.py serve
# Opens http://localhost:8420
```

### Standard Scan

```bash
python scripts/sniper.py scan --max-price 0.5 --filters-per-cycle 12 --daily-limit 200 --max-pages 1
```

### Economy Refresh (No Browser Needed!)

```bash
python scripts/sniper.py economy --force
```

Fetches prices from PD2Trader API in seconds — no Chrome/Playwright required.

### Other Commands

```bash
python scripts/sniper.py filters          # List saved filters
python scripts/sniper.py history          # Offer history stats
python scripts/sniper.py dashboard        # Regenerate dashboard HTML
python scripts/sniper.py offer --listing-url "..." --amount 0.3
python scripts/sniper.py confirm --deal-index 0 --amount 0.3
```

## Live-Tested Findings

- **PD2 market pages** are primarily server-rendered HTML; DOM parser is the real source of truth for browser-based scanning
- **PD2Trader API** provides reliable median prices with proper User-Agent header
- **PD2 REST API** (`api.projectdiablo2.com`) supports MongoDB-style query filters for direct market search (same as pd2-trade desktop app)
- Chrome remote debugging works reliably for both scanning and offer submission
- Full live offer submission tested successfully
- Operator workflow (`operator-scan → user replies amount → reply-offer`) is battle-tested

## Safety Protections

This tool is deliberately conservative — aggressive scanning could get an account noticed.

- **Filter rotation** instead of scanning everything every cycle
- **Randomized delays** between filter scans and pagination
- **Daily scan cap** to limit volume
- **Seen-item tracking** so the same listing doesn't resurface constantly
- **Manual offer amounts** — no auto-bidding, user decides every price

Still use judgment:
- Don't run very tight loops
- Don't spam repeated offers to the same seller/listing
- Prefer small rotations and human-like spacing
- Treat this as assistive browsing, not mass automation

## State Files

| File | Purpose |
|------|---------|
| `scan_results.json` | Latest scan output |
| `seen_items.json` | Dedup cache with 36-hour expiry |
| `offer_history.json` | Offer submission log |
| `sniper_state.json` | Scan rotation, daily counts, filter health, pending deal |
| `assets/all_economy.json` | Cached economy values from PD2Trader |
| `assets/dashboard.html` | Generated dashboard |
| `screenshots/` | Deal and offer screenshots |

## Price Confidence Scoring

When presenting deals, the sniper checks each item against PD2Trader data:

- **High confidence** — 20+ recent listings, stable data
- **Medium confidence** — 5-20 listings, moderate data
- **Low confidence** — fewer than 5 listings, price may be unreliable
- **Trend analysis** — rising/falling/stable based on 7-day price change

This helps you decide whether a deal is actually good or if the market data is too thin to trust.

## Prerequisites

### For Economy Data & Price Checking (No Browser)
Just Python — the PD2Trader API works without any browser.

### For Scanning & Offer Submission
Chrome with remote debugging, logged into PD2:

```powershell
Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=C:\Users\jding\AppData\Local\Google\Chrome\User Data"
```

### For Direct API Access (Optional)
Save your PD2 JWT token to `.pd2_token` in the project root for REST API offer submission and market search without browser.

## Acknowledgments

Price data powered by **[PD2Trader](https://pd2trader.com)** — learned from the [pd2-trade](https://github.com/errolgr/pd2-trade) desktop app's API integration patterns for market queries, price fetching, and offer management.

## Notes

See `SKILL.md` for the skill-facing operating instructions.
