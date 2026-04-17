---
name: pd2-market-sniper
description: >
  Automated item sniper for Project Diablo 2 market. Scans saved market filters for cheap items,
  ranks deals, captures screenshots + direct links, and waits for the user to choose offer amounts
  before submitting through the website. Use when the user asks to scan the PD2 market, snipe items,
  check filters, make offers, or monitor the marketplace. Targets softcore ladder. Triggers on phrases
  like "check market", "snipe items", "scan filters", "PD2 market", "make offers", "any cheap items".
---

# PD2 Market Sniper

Automated trading assistant for Project Diablo 2 marketplace (softcore ladder).
Account: d1ngl3 on projectdiablo2.com

## Prerequisites

Chrome must be running with remote debugging and logged into the d1ngl3 PD2 account:

```powershell
Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=C:\Users\jding\AppData\Local\Google\Chrome\User Data"
```

## Main Workflows

### 1) Safe Scan Cycle
```bash
python scripts/sniper.py scan --max-price 0.5 --filters-per-cycle 12 --daily-limit 200 --max-pages 1
```

What it does:
- Rotates through only part of the saved filter list each cycle (default 12 filters)
- Enforces conservative pacing with 2.0-3.5s randomized delays between filters
- Supports bounded pagination with `--max-pages` (default 1 page)
- Adds randomized delay between page turns during multi-page scans
- Caps daily checks (default 200) via `sniper_state.json`
- Intercepts market XHR/fetch JSON when available, with DOM fallback if the API shape changes
- Expires old seen items after 36h so relists can surface again
- Auto-refreshes pd2.tools economy data daily
- Produces structured `scan_results.json`
- Writes `assets/dashboard.html`

### 2) Scan a Specific Filter
```bash
python scripts/sniper.py scan --filter-id 69e0c58f9fc33c4bc7fe0483 --max-price 0.5 --max-pages 3
```

### 3) Alert-Then-Offer Flow
1. Run an operator scan.
2. Send the top deal card to the user.
3. Wait for the user to reply with just an amount like `0.4`.
4. Submit that amount against the pending deal.

Operator scan (best for chat workflow):
```bash
python scripts/sniper.py operator-scan --max-price 0.5 --filters-per-cycle 12 --daily-limit 200 --max-pages 1 --top 3
```
This prints compact operator-ready deal cards and stores the top result as the current pending confirmation target.

Show the pending deal again:
```bash
python scripts/sniper.py pending
```

Submit a user reply amount against the pending deal:
```bash
python scripts/sniper.py reply-offer 0.3
```

Direct offer by URL:
```bash
python scripts/sniper.py offer --listing-url "https://www.projectdiablo2.com/market/listing/abc123..." --amount 0.3
```

One-click confirm using the last scan result:
```bash
python scripts/sniper.py confirm --deal-index 0 --amount 0.3
```

The sniper does **not** auto-price. It alerts, ranks, screenshots, and waits for the user to choose the number.

## Other Commands

List saved filters:
```bash
python scripts/sniper.py filters
```

Show offer history stats:
```bash
python scripts/sniper.py history
```

Show the current pending confirmation deal as JSON:
```bash
python scripts/sniper.py pending --json
```

Refresh economy cache:
```bash
python scripts/sniper.py economy --force
```

Regenerate dashboard from saved data:
```bash
python scripts/sniper.py dashboard
```

## Files and Data

- `scripts/sniper.py` - CLI entry point
- `scripts/scanner.py` - scan orchestration, pacing, API interception, deal collection
- `scripts/offers.py` - offer submission flow
- `scripts/alerts.py` - scoring and alert formatting
- `scripts/economy.py` - pd2.tools refresh and lookup
- `scripts/history.py` - seen item expiry, offer history, scan state, filter health
- `scripts/dashboard.py` - HTML dashboard generation
- `scripts/parsers.py` - API/DOM listing parsers
- `scripts/config.py` - shared config and filter list
- `seen_items.json` - dedup tracker with timestamps
- `offer_history.json` - offer log and status history
- `sniper_state.json` - cadence counters, rotation state, filter health, recent scans
- `scan_results.json` - latest structured scan output
- `assets/all_economy.json` - cached economy values
- `assets/dashboard.html` - scan dashboard
- `screenshots/` - deal and offer screenshots

## Scan Result Shape

Each scan returns structured JSON with:
- `summary`: timing, filter count, daily count, deal count
- `filters`: per-filter results, API endpoints hit, errors if any
- `deals`: ranked deals with score, direct link, screenshot path, seller, price, and economy context
- `review`: listings that need manual review because no HR price was parsed
- `state`: recent scan history and filter-health data

## Filter Health

The sniper tracks whether filters return listings over time:
- Filters with no hits for 7+ days are marked `slow`
- Slow filters are still kept in rotation
- Nothing is auto-removed

## Safe Usage Notes

- Conservative cadence is deliberate to reduce ban risk
- Keep cycles limited instead of hammering all 59 filters at once
- Use `--max-pages 1` for normal sniper behavior, increase pages only for deliberate deep scans
- Avoid spamming the same listing, use `offer_history.json` as a sanity check
- Season 13 ladder resets April 24, 2026

## Saved Filters

All existing saved filter IDs are preserved in `scripts/config.py`.
