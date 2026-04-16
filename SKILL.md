---
name: pd2-market-sniper
description: >
  Automated item sniper for Project Diablo 2 market. Scans saved market filters for cheap items,
  alerts on matching items and asks user what to offer before sending.
  Use when the user asks to scan the PD2 market, snipe items, check filters, make offers,
  or monitor the marketplace. Targets softcore ladder. Triggers on phrases like "check market",
  "snipe items", "scan filters", "PD2 market", "make offers", "any cheap items".
---

# PD2 Market Sniper

Automated trading assistant for Project Diablo 2 marketplace (softcore ladder).
Account: d1ngl3 on projectdiablo2.com

## Prerequisites

Chrome must be running with remote debugging:

```powershell
Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=C:\Users\jding\AppData\Local\Google\Chrome\User Data"
```

## Commands

### List Saved Filters
```bash
python scripts/sniper.py filters
```

### Scan a Single Filter
```bash
python scripts/sniper.py scan --filter-id 6945027864537e558cdc2199 --max-price 0.5
```

### Scan All Filters
```bash
python scripts/sniper.py scan --max-price 0.5
```
Scans all 59 saved filters for items at or below the max price (in HR).

### Make an Offer
```bash
python scripts/sniper.py offer --amount 0.25
```
Clicks OFFER on the first visible listing and submits a lowball offer.

## How It Works

1. **Scan:** Navigates to each saved filter URL, waits for listings to load
2. **Parse:** Extracts item name, price (in HR), and seller from each listing
3. **Filter:** Keeps only items at or below max_price_hr threshold
4. **Dedup:** Tracks seen items in `seen_items.json` to avoid repeat alerts
5. **Alert:** Returns deal items and items that need price review
6. **Offer:** Can auto-click OFFER and submit a lowball amount

## Currency Reference

Live economy pages (scrape these for current values before making offers):
- Currency: https://pd2.tools/economy/currency
- Runes: https://pd2.tools/economy/runes
- Ubers: https://pd2.tools/economy/ubers
- Maps: https://pd2.tools/economy/maps

All items priced in HR (High Rune) equivalent. Key rune values: Vex=0.5, Gul=0.25, Ist=0.15, Mal=0.1, Um=0.05, Pul=0.03, Lem=0.01

Use `scripts/scrape_economy.py` to refresh all values.
Cached values stored in `assets/all_economy.json`.

## Price Thresholds

Default max price: **0.5 HR** (adjustable via --max-price)
For big-ticket items, the user will provide price guidance per item.

## Saved Filters (59 total)

Includes filters for:
- **Amazon:** jav lifer gc, bow amp, spear +amp, war pike +amp, tombsong variants (+skill, +IAS, +40 pierce), valkyrie wing variants, dooms finger +pierce, passive amulet +3/+4/+5, passive glove variants, passive GC variants (lifer, frw, +GF)
- **Assassin:** lite +fhr gc, claw lower res
- **Barbarian:** arachnid +20 FCR, string variants, BK variants, steelrend +deadly, gore rider +20 ds, metalgrid variants, CoA +skill 3os, nosferatu +30 ias, headhunter variants, war trav +frw
- **Necromancer:** wraithskin +3os, veil +2sk, veil +3os, ebonbane variants (+CB, +DS, +5os), undead crown +1skill, tombstone variants
- **Paladin:** atmas variants, rising sun +skill, tyreals
- **Druid:** highlords cbf pierce, highlords +ED, spirit ward +3os, ebonbane variants
- **Sorceress:** quad res booties, construct 30fcr
- **Other:** fcr dual leach ring, half freeze trires b, witchwild +4OS, gravepalm +15 DS, windforce +6os, gface +3os

All filter IDs are hardcoded in `scripts/sniper.py` and loaded from the user's saved filters page.

### Season 13 Changes
**Removed (25):** shadow FHR/FRW/LIFE, martial variants, dungos variants, ASTREON, WW blade, arachs +30fcr, infernostride, steel carapace, claw amp, claw lower res, lower res proc, eth ed deadly glove, sick maek/mleach javglov, 2-30 pierce jav glov, 5os widow multi, atmas +ias, warcry goldfind GC, steelrend -target d, string +frw

**Added (29):** tombsong variants (3), valkyrie wing variants (2), passive amulet +3/+4/+5, passive glove variants (3), passive GC variants (3), arachnid +20 FCR, ebonbane variants (3), highlords +ED, atmas +ED, atmas +pierce, witchwild +4OS, gravepalm +15 DS, war trav +frw, gore rider +20 ds, gface +3os, windforce +6os, undead crown +1skill, wraithskin +3os

## Offer Flow

1. Navigate to a filter with results
2. Script clicks the **OFFER** button on a listing
3. Fills in the HR amount (default 0.25)
4. Clicks **SUBMIT**

## Files

- `scripts/sniper.py` — Main scanner + offer script
- `scripts/explore_*.py` — Debug/exploration scripts
- `seen_items.json` — Dedup tracker for seen items
- `scan_results.json` — Last scan results
- `screenshots/` — Debug screenshots

## Season 13 Note

Ladder resets April 24, 2026. 29 new filters added for S13, 25 old filters removed. Heavy focus on Amazon (passive/tombsong builds) and new S13 items like ebonbane, wraithskin, valkyrie wing, witchwild. Market will be sparse until players start trading — schedule regular scans starting after reset.

## Dependencies

- Python 3.8+
- playwright (`pip install playwright`)
- Chrome with remote debugging on port 9222
- d1ngl3 account logged into projectdiablo2.com
