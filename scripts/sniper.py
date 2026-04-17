#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from alerts import format_alert, format_operator_alert
from config import DEFAULT_FILTERS_PER_CYCLE, DEFAULT_MAX_PAGES, DEFAULT_MAX_PRICE_HR, FILTERS, SCAN_RESULTS_FILE
from dashboard import write_dashboard
from economy import EconomyManager
from history import OfferHistory, StateStore
from offers import submit_offer
from scanner import MarketScanner


def refresh_dashboard_from_state() -> None:
    state = StateStore()
    offer_history = OfferHistory().stats()
    economy = EconomyManager(state).load()
    scan_results = json.loads(SCAN_RESULTS_FILE.read_text(encoding="utf-8")) if SCAN_RESULTS_FILE.exists() else {"summary": {}, "deals": [], "state": state.data}
    write_dashboard(scan_results, offer_history, state.filter_health(), economy)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PD2 market sniper")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("filters", help="List saved filters")

    scan = sub.add_parser("scan", help="Scan filters for deals")
    scan.add_argument("--filter-id")
    scan.add_argument("--max-price", type=float, default=DEFAULT_MAX_PRICE_HR)
    scan.add_argument("--filters-per-cycle", type=int, default=DEFAULT_FILTERS_PER_CYCLE)
    scan.add_argument("--daily-limit", type=int, default=200)
    scan.add_argument("--force-economy-refresh", action="store_true")
    scan.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)

    offer = sub.add_parser("offer", help="Submit an offer to a listing")
    offer.add_argument("--listing-url", required=True)
    offer.add_argument("--amount", type=float, required=True)
    offer.add_argument("--item-json", help="Optional JSON blob from scan results")

    confirm = sub.add_parser("confirm", help="One-click confirm using a scan result index")
    confirm.add_argument("--amount", type=float, required=True)
    confirm.add_argument("--deal-index", type=int, default=0)
    confirm.add_argument("--results-file", default=str(SCAN_RESULTS_FILE))

    operator_scan = sub.add_parser("operator-scan", help="Scan and print operator-ready deal cards")
    operator_scan.add_argument("--filter-id")
    operator_scan.add_argument("--max-price", type=float, default=DEFAULT_MAX_PRICE_HR)
    operator_scan.add_argument("--filters-per-cycle", type=int, default=DEFAULT_FILTERS_PER_CYCLE)
    operator_scan.add_argument("--daily-limit", type=int, default=200)
    operator_scan.add_argument("--force-economy-refresh", action="store_true")
    operator_scan.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    operator_scan.add_argument("--top", type=int, default=3)

    pending = sub.add_parser("pending", help="Show the current pending confirmation deal")
    pending.add_argument("--json", action="store_true")

    reply_offer = sub.add_parser("reply-offer", help="Submit an offer amount against the pending deal")
    reply_offer.add_argument("amount", type=float)

    sub.add_parser("history", help="Show offer history stats")
    sub.add_parser("dashboard", help="Regenerate dashboard from current state")
    economy = sub.add_parser("economy", help="Refresh economy cache")
    economy.add_argument("--force", action="store_true")
    serve = sub.add_parser("serve", help="Start dashboard HTTP server")
    serve.add_argument("--port", type=int, default=8420, help="Port to serve on (default: 8420)")
    serve.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    return parser


async def cmd_scan(args) -> int:
    scanner = MarketScanner(
        max_price_hr=args.max_price,
        filters_per_cycle=args.filters_per_cycle,
        daily_filter_limit=args.daily_limit,
        force_economy_refresh=args.force_economy_refresh,
        max_pages=args.max_pages,
    )
    results = await scanner.scan(filter_id=args.filter_id)
    SCAN_RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    for deal in results.get("deals", []):
        print(format_alert(deal))
    print(json.dumps(results.get("summary", {}), indent=2))
    return 0


async def cmd_offer(args) -> int:
    item = json.loads(args.item_json) if args.item_json else None
    result = await submit_offer(listing_url=args.listing_url, amount_hr=args.amount, item=item)
    refresh_dashboard_from_state()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


async def cmd_operator_scan(args) -> int:
    state = StateStore()
    scanner = MarketScanner(
        max_price_hr=args.max_price,
        filters_per_cycle=args.filters_per_cycle,
        daily_filter_limit=args.daily_limit,
        force_economy_refresh=args.force_economy_refresh,
        max_pages=args.max_pages,
    )
    results = await scanner.scan(filter_id=args.filter_id)
    SCAN_RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    deals = results.get("deals", [])
    if not deals:
        state.set_pending_confirmation(None)
        print("No deals found.")
        print(json.dumps(results.get("summary", {}), indent=2))
        return 0
    top_deals = deals[: max(1, args.top)]
    state.set_pending_confirmation(top_deals[0])
    for idx, deal in enumerate(top_deals):
        print(format_operator_alert(deal, deal_index=idx))
        print("\n---\n")
    print(json.dumps(results.get("summary", {}), indent=2))
    return 0


async def cmd_confirm(args) -> int:
    path = Path(args.results_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    deals = data.get("deals", [])
    if not deals:
        raise SystemExit("No deals in scan results.")
    deal = deals[args.deal_index]
    result = await submit_offer(listing_url=deal["listing_url"], amount_hr=args.amount, item=deal)
    if result.get("ok"):
        StateStore().set_pending_confirmation(None)
    refresh_dashboard_from_state()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_pending(args) -> int:
    pending = StateStore().get_pending_confirmation()
    if not pending:
        print("No pending deal.")
        return 1
    if args.json:
        print(json.dumps(pending, indent=2, ensure_ascii=False))
    else:
        print(format_operator_alert(pending, deal_index=0))
    return 0


async def cmd_reply_offer(args) -> int:
    state = StateStore()
    pending = state.get_pending_confirmation()
    if not pending:
        raise SystemExit("No pending deal to submit against.")
    result = await submit_offer(listing_url=pending["listing_url"], amount_hr=args.amount, item=pending)
    if result.get("ok"):
        state.set_pending_confirmation(None)
    refresh_dashboard_from_state()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_filters() -> int:
    for filter_id, name in FILTERS.items():
        print(f"{filter_id}  {name}")
    return 0


def cmd_history() -> int:
    print(json.dumps(OfferHistory().stats(), indent=2, ensure_ascii=False))
    return 0


def cmd_dashboard() -> int:
    refresh_dashboard_from_state()
    print("Dashboard written")
    return 0


async def cmd_economy(args) -> int:
    payload = await EconomyManager(StateStore()).refresh(force=args.force)
    print(json.dumps({"refreshed_at": payload.get("refreshed_at"), "value_count": len(payload.get("values", {}))}, indent=2))
    return 0


async def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "filters":
        return cmd_filters()
    if args.command == "scan":
        return await cmd_scan(args)
    if args.command == "offer":
        return await cmd_offer(args)
    if args.command == "confirm":
        return await cmd_confirm(args)
    if args.command == "operator-scan":
        return await cmd_operator_scan(args)
    if args.command == "pending":
        return cmd_pending(args)
    if args.command == "reply-offer":
        return await cmd_reply_offer(args)
    if args.command == "history":
        return cmd_history()
    if args.command == "dashboard":
        return cmd_dashboard()
    if args.command == "economy":
        return await cmd_economy(args)
    if args.command == "serve":
        from server import serve
        serve(args.port, open_browser=not args.no_browser)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    # 'serve' has its own event loop, bypass asyncio.run
    if args.command == "serve":
        from server import serve
        serve(args.port, open_browser=not args.no_browser)
    else:
        raise SystemExit(asyncio.run(main()))
