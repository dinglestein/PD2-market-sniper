# PD2 Market Sniper 🎯

Project Diablo 2 marketplace scanner for softcore ladder.

This skill scans saved PD2 market filters on a conservative cadence, ranks deals, captures screenshots and direct listing links, and waits for the user to choose the exact offer amount before submitting through the website.

Account used in testing: `d1ngl3`

## What It Does

- Scans saved market filters without hammering the site
- Finds listings under a configurable HR threshold
- Ranks deals and formats them into operator-ready alert cards
- Captures screenshots of found listings
- Stores a pending deal so a simple reply like `0.4 HR` can map to a submission
- Submits offers through the live PD2 site using the logged-in browser session
- Tracks offer history, seen items, scan rotation, filter health, and economy refreshes
- Generates an HTML dashboard for recent activity

## Live-Tested Findings

These findings came from real testing against the live PD2 market, not just code assumptions:

- **PD2 market is primarily server-rendered HTML**, not a rich XHR/JSON listing API in normal page loads
- Because of that, the **DOM parser is the real source of truth** for listing extraction
- Chrome remote debugging with the logged-in PD2 account worked reliably for both scanning and offer submission
- A full live offer submission was tested successfully
- The practical operator workflow, `operator-scan -> user replies with amount -> reply-offer`, is working

## Important Safety / Risk Notes

This tool is deliberately conservative because aggressive scanning could get an account or IP noticed.

Current protections:
- filter rotation instead of scanning the entire saved list every cycle
- randomized delay between filter scans
- randomized delay between pagination page turns
- daily scan cap
- seen-item tracking so the same listing does not keep surfacing constantly
- manual user-controlled offer amount, no auto-bidding

Still use judgment:
- do not run very tight loops
- do not spam repeated offers to the same seller/listing
- prefer small rotations and human-like spacing
- treat this as assistive browsing, not mass automation

## Architecture

Main files:

- `scripts/sniper.py` - CLI entry point
- `scripts/scanner.py` - scan orchestration, cadence, browser control, result collection
- `scripts/parsers.py` - DOM/API listing parsing
- `scripts/offers.py` - offer submission flow
- `scripts/alerts.py` - scoring and operator alert formatting
- `scripts/economy.py` - pd2.tools refresh and value lookup
- `scripts/history.py` - seen items, offer history, pending deal state, filter health, scan state
- `scripts/dashboard.py` - HTML dashboard generation
- `scripts/config.py` - shared config and filter list

Pagination support:

- scans page 1 by default
- supports bounded multi-page traversal with `--max-pages N`
- deduplicates repeated listings across pages
- stops early if later pages repeat or go empty
- intended for conservative deep scans, not full aggressive crawls

State / generated files:

- `scan_results.json` - latest scan output
- `seen_items.json` - dedup cache with expiry
- `offer_history.json` - offer log
- `sniper_state.json` - scan rotation, daily counts, recent scans, pending deal
- `assets/all_economy.json` - cached economy values
- `assets/dashboard.html` - generated dashboard
- `screenshots/` - captured deal and offer screenshots

## Commands

### Standard Scan

```bash
python scripts/sniper.py scan --max-price 0.5 --filters-per-cycle 12 --daily-limit 200 --max-pages 1
```

### Scan a Specific Filter

```bash
python scripts/sniper.py scan --filter-id 69e0c58f9fc33c4bc7fe0483 --max-price 0.5
```

### Operator Workflow

This is the preferred real-world flow.

1. Run an operator scan
2. Send the top deal card to the user
3. Wait for the user to reply with just an amount, for example `0.4 HR`
4. Submit that amount against the stored pending deal

Operator scan:

```bash
python scripts/sniper.py operator-scan --max-price 0.5 --filters-per-cycle 12 --daily-limit 200 --max-pages 1 --top 3
```

Show the current pending deal:

```bash
python scripts/sniper.py pending
python scripts/sniper.py pending --json
```

Submit the user reply amount against the pending deal:

```bash
python scripts/sniper.py reply-offer 0.4
```

### Direct Offer by URL

```bash
python scripts/sniper.py offer --listing-url "https://www.projectdiablo2.com/market/listing/..." --amount 0.3
```

### Confirm from the Last Scan Results

```bash
python scripts/sniper.py confirm --deal-index 0 --amount 0.3
```

### Other Commands

```bash
python scripts/sniper.py filters
python scripts/sniper.py history
python scripts/sniper.py economy --force
python scripts/sniper.py dashboard
```

## Practical Workflow Example

A real operator card looks like this:

```text
Deal #0
Item: Rare Vampirebone Gloves
Price: 2.0 HR
Seller: tsetso91
Filter: passive glove +2-20p
Score: -6.0
Link: https://www.projectdiablo2.com/market/listing/69c672474cbbe44d1073af77
Posted: 1 day ago
Corruption: Corrupted
Stats:
- 20% Increased Attack Speed
- 10% Chance to Pierce
- +66 to Attack Rating
- +1 to Minimum Fire Damage
- 98% Enhanced Defense
- Repairs 1 Durability in 0.05 Seconds
Reply with just an HR amount like `0.4` and I can submit the offer.
```

The user can then simply reply:

```text
0.3 HR
```

That maps cleanly to:

```bash
python scripts/sniper.py reply-offer 0.3
```

## Live-Tested Offer Submission

A real offer submission was completed successfully during testing:

- item: `Rare Vampirebone Gloves`
- listing price: `2.0 HR`
- seller: `tsetso91`
- submitted offer: `0.3 HR`
- listing: `https://www.projectdiablo2.com/market/listing/69c672474cbbe44d1073af77`

Because that live offer was already sent, later practical-workflow testing intentionally stopped short of sending duplicate offers to the same seller/listing.

## Scoring Notes

Deal scoring is heuristic and intended for triage, not automatic pricing.

Inputs include:
- price vs economy value when available
- corruption/stat keywords
- listing freshness
- recent offer count on the same listing

The user still decides all final offer amounts.

## Filter Health

The sniper tracks whether filters are producing results over time:

- filters with no hits for 7+ days are marked `slow`
- slow filters remain in rotation
- nothing is auto-removed

This is intended as visibility only, especially because some desired corruptions are rare and should remain tracked.

## Known Limitations

- Listing extraction is DOM-driven because live market pages did not expose the expected JSON listing API during testing
- Screenshot capture is page-level, not tightly cropped to a single listing card
- Economy matching is approximate and may not cover niche or corruption-sensitive item values
- Offer outcome tracking is limited to submission-side logging unless additional acceptance/rejection checks are added later

## Recommended Next Steps

- add generic ad hoc search support for live market queries like `Type: Bow`
- schedule conservative recurring scans
- wire the operator alert output directly into messaging surfaces
- improve cropped listing screenshots
- refine value heuristics with user-supplied corruption/value knowledge
- add better post-offer status tracking

## Prerequisites

Chrome must be running with remote debugging and logged into PD2:

```powershell
Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=C:\Users\jding\AppData\Local\Google\Chrome\User Data"
```

## Notes

See `SKILL.md` for the skill-facing operating instructions.
