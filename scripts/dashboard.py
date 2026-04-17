from __future__ import annotations

import html
import json
from typing import Any

from config import DASHBOARD_FILE


def _json(obj: Any) -> str:
    return html.escape(json.dumps(obj, ensure_ascii=False))


def render_dashboard(scan_results: dict[str, Any], offer_stats: dict[str, Any], filter_health: list[dict[str, Any]], economy: dict[str, Any]) -> str:
    recent_scans = scan_results.get("state", {}).get("recent_scans", [])[-20:]
    deals = scan_results.get("deals", [])[:50]
    economy_values = list((economy.get("values") or {}).items())[:50]
    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>PD2 Sniper Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #111; color: #eee; }}
    h1, h2 {{ color: #f5c451; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .card {{ background: #1c1c1c; border: 1px solid #333; padding: 16px; border-radius: 10px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td, th {{ border-bottom: 1px solid #333; padding: 6px; text-align: left; vertical-align: top; }}
    code {{ white-space: pre-wrap; display: block; }}
    a {{ color: #8fc7ff; }}
  </style>
</head>
<body>
  <h1>PD2 Market Sniper Dashboard</h1>
  <div class=\"grid\">
    <div class=\"card\"><h2>Last Scan</h2><code>{_json(scan_results.get('summary', {}))}</code></div>
    <div class=\"card\"><h2>Offer Stats</h2><code>{_json(offer_stats)}</code></div>
    <div class=\"card\"><h2>Economy Refresh</h2><code>{html.escape(str(economy.get('refreshed_at')))}</code></div>
  </div>

  <div class=\"grid\">
    <div class=\"card\">
      <h2>Recent Deals</h2>
      <table><tr><th>Score</th><th>Item</th><th>Price</th><th>Seller</th></tr>
      {''.join(f"<tr><td>{deal.get('score')}</td><td><a href='{html.escape(str(deal.get('listing_url')))}'>{html.escape(str(deal.get('item_name')))}</a></td><td>{deal.get('price_hr')}</td><td>{html.escape(str(deal.get('seller_name')))}</td></tr>" for deal in deals)}
      </table>
    </div>
    <div class=\"card\">
      <h2>Recent Scans</h2>
      <table><tr><th>When</th><th>Filters</th><th>Deals</th></tr>
      {''.join(f"<tr><td>{html.escape(str(scan.get('timestamp')))}</td><td>{scan.get('filters_scanned')}</td><td>{scan.get('deals_found')}</td></tr>" for scan in recent_scans)}
      </table>
    </div>
  </div>

  <div class=\"grid\">
    <div class=\"card\">
      <h2>Filter Health</h2>
      <table><tr><th>Filter</th><th>Status</th><th>Scans</th><th>Days Since Hit</th></tr>
      {''.join(f"<tr><td>{html.escape(str(item.get('filter_name')))}</td><td>{item.get('status')}</td><td>{item.get('scan_count')}</td><td>{item.get('days_since_hit')}</td></tr>" for item in filter_health[:80])}
      </table>
    </div>
    <div class=\"card\">
      <h2>Economy Values</h2>
      <table><tr><th>Item</th><th>HR</th></tr>
      {''.join(f"<tr><td>{html.escape(name)}</td><td>{value}</td></tr>" for name, value in economy_values)}
      </table>
    </div>
  </div>
</body>
</html>
"""


def write_dashboard(scan_results: dict[str, Any], offer_stats: dict[str, Any], filter_health: list[dict[str, Any]], economy: dict[str, Any]) -> None:
    DASHBOARD_FILE.write_text(render_dashboard(scan_results, offer_stats, filter_health, economy), encoding="utf-8")
