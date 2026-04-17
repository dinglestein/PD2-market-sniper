# PD2 Market Sniper 🎯

PD2 marketplace scanner for softcore ladder. It rotates saved filters on a conservative cadence, ranks cheap listings, captures screenshots and direct links, and lets the user choose the exact offer amount before submission.

## Highlights

- Alert-then-offer flow, no auto-pricing
- API-first listing capture with DOM fallback
- Safe scan pacing with jitter, rotation, and daily cap
- Seen-item expiry and offer history tracking
- Daily economy refresh from pd2.tools
- Filter health tracking and HTML dashboard

## Quick Start

```bash
python scripts/sniper.py scan --max-price 0.5 --filters-per-cycle 12 --daily-limit 200
python scripts/sniper.py confirm --deal-index 0 --amount 0.3
python scripts/sniper.py history
```

See `SKILL.md` for the full workflow.
