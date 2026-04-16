# PD2 Market Sniper 🎯

Automated item sniper for the [Project Diablo 2](https://projectdiablo2.com) marketplace. Scans saved market filters for underpriced items, deduplicates results, and can auto-submit lowball offers.

**Server:** Softcore Ladder  
**Account:** d1ngl3

## Features

- Scans all saved market filters for items below a configurable HR price threshold
- Deduplicates with `seen_items.json` so you only get alerted once per item
- Can auto-submit offers on listings via Chrome automation
- Economy scraper for live currency/rune values

## Prerequisites

- Python 3.8+
- [Playwright](https://playwright.dev/): `pip install playwright`
- Chrome running with remote debugging:

```powershell
Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=C:\Users\jding\AppData\Local\Google\Chrome\User Data"
```

- d1ngl3 account logged into projectdiablo2.com in that Chrome profile

## Usage

```bash
# List all saved filters
python scripts/sniper.py filters

# Scan a single filter
python scripts/sniper.py scan --filter-id 6945027864537e558cdc2199 --max-price 0.5

# Scan all 59 filters for items ≤ 0.5 HR
python scripts/sniper.py scan --max-price 0.5

# Submit a 0.25 HR offer on the first visible listing
python scripts/sniper.py offer --amount 0.25
```

## Saved Filters

59 filters covering a range of build-critical items — crafts, rares, uniques, runewords, and set items. Filter IDs are hardcoded in `scripts/sniper.py`.

See [SKILL.md](SKILL.md) for the full categorized list.

## Economy Reference

Live economy data is cached in `assets/all_economy.json`. Refresh with:

```bash
python scripts/scrape_economy.py
```

| Source | URL |
|--------|-----|
| Currency | https://pd2.tools/economy/currency |
| Runes | https://pd2.tools/economy/runes |
| Ubers | https://pd2.tools/economy/ubers |
| Maps | https://pd2.tools/economy/maps |

Key rune values (HR equivalents): Vex=0.5, Gul=0.25, Ist=0.15, Mal=0.1, Um=0.05, Pul=0.03, Lem=0.01

## Project Structure

```
├── SKILL.md              # OpenClaw skill definition
├── scripts/
│   ├── sniper.py         # Main scanner + offer script
│   ├── fetch_filters.py  # Pull saved filter IDs from the site
│   ├── scrape_economy.py # Economy data scraper
│   └── explore_*.py      # Debug/exploration scripts
├── seen_items.json       # Dedup tracker
├── scan_results.json     # Last scan output
├── assets/
│   └── all_economy.json  # Cached economy values
└── screenshots/          # Debug screenshots
```

## How It Works

1. **Scan** — Navigates Chrome to each saved filter URL, waits for listings to load
2. **Parse** — Extracts item name, price (HR), and seller from each listing
3. **Filter** — Keeps only items at or below the `--max-price` threshold
4. **Dedup** — Tracks seen items to avoid repeat alerts across scans
5. **Alert** — Returns deal items and items needing price review
6. **Offer** — Optionally clicks OFFER on a listing and submits a lowball amount

## Disclaimer

This is a personal tool for use with the Project Diablo 2 community marketplace. Use responsibly and don't be a dick with offers.

---

*Season 13 ready — ladder resets April 24, 2026*
