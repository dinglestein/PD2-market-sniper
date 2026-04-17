from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from config import DASHBOARD_FILE


def _json(obj: Any) -> str:
    return html.escape(json.dumps(obj, ensure_ascii=False, indent=2))


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _fmt_ts(value: Any) -> str:
    return _esc(value) if value else "-"


def _rel_path(path_str: str | None) -> str | None:
    if not path_str:
        return None
    try:
        path = Path(path_str)
        assets_dir = DASHBOARD_FILE.parent
        return Path(path).resolve().relative_to(assets_dir.resolve()).as_posix()
    except Exception:
        try:
            path = Path(path_str)
            assets_dir = DASHBOARD_FILE.parent
            return Path("..") / path.relative_to(assets_dir.parent)
        except Exception:
            return None


def _screenshot_img(path_str: str | None, alt: str) -> str:
    rel = _rel_path(path_str)
    if not rel:
        return '<div class="shot shot-empty">No screenshot</div>'
    return f'<a class="shot-link" href="{_esc(rel)}" target="_blank" rel="noreferrer"><img class="shot" src="{_esc(rel)}" alt="{_esc(alt)}" /></a>'


def _badge(label: str, value: Any, kind: str = "default") -> str:
    return f'<span class="badge badge-{_esc(kind)}"><span class="badge-label">{_esc(label)}</span><span class="badge-value">{_esc(value)}</span></span>'


def _render_deal_card(deal: dict[str, Any]) -> str:
    stats = deal.get("stats") or []
    corruption = deal.get("corruption") or []
    meta = [
        _badge("Score", deal.get("score", "-"), "score"),
        _badge("Price", f"{deal.get('price_hr')} HR" if deal.get("price_hr") is not None else "?", "price"),
        _badge("Seller", deal.get("seller_name") or "?", "seller"),
    ]
    if deal.get("page"):
        meta.append(_badge("Page", deal.get("page"), "page"))
    if deal.get("posted_at"):
        meta.append(_badge("Posted", deal.get("posted_at"), "time"))
    if deal.get("recent_offer_count"):
        meta.append(_badge("Recent offers", deal.get("recent_offer_count"), "warn"))

    chips = "".join(meta)
    stats_html = "".join(f"<li>{_esc(stat)}</li>" for stat in stats[:8]) or "<li>No parsed stats</li>"
    corr_html = "".join(f'<span class="chip chip-corrupt">{_esc(c)}</span>' for c in corruption)

    return f"""
    <article class="deal-card">
      <div class="deal-media">
        {_screenshot_img(deal.get('screenshot'), deal.get('item_name') or 'deal screenshot')}
      </div>
      <div class="deal-body">
        <div class="deal-head">
          <div>
            <h3>{_esc(deal.get('item_name') or 'Unknown item')}</h3>
            <div class="deal-sub">{_esc(deal.get('filter_name') or 'Unknown filter')}</div>
          </div>
          <a class="deal-link" href="{_esc(deal.get('listing_url') or '#')}" target="_blank" rel="noreferrer">Open listing ↗</a>
        </div>
        <div class="badges">{chips}</div>
        <div class="chips">{corr_html}</div>
        <details>
          <summary>Stats</summary>
          <ul class="stats-list">{stats_html}</ul>
        </details>
      </div>
    </article>
    """


def _render_offer_rows(offers: list[dict[str, Any]]) -> str:
    if not offers:
        return '<tr><td colspan="6" class="muted">No offers yet</td></tr>'
    rows = []
    for offer in reversed(offers[-20:]):
        rows.append(
            f"<tr>"
            f"<td>{_fmt_ts(offer.get('timestamp'))}</td>"
            f"<td>{_esc(offer.get('status'))}</td>"
            f"<td>{_esc(offer.get('item_name'))}</td>"
            f"<td>{_esc(offer.get('seller_name'))}</td>"
            f"<td>{_esc(offer.get('amount_hr'))} HR</td>"
            f"<td><a href='{_esc(offer.get('listing_url') or '#')}' target='_blank' rel='noreferrer'>listing</a></td>"
            f"</tr>"
        )
    return ''.join(rows)


def _render_scan_rows(recent_scans: list[dict[str, Any]]) -> str:
    if not recent_scans:
        return '<tr><td colspan="5" class="muted">No scans yet</td></tr>'
    rows = []
    for scan in reversed(recent_scans[-20:]):
        rows.append(
            f"<tr>"
            f"<td>{_fmt_ts(scan.get('timestamp'))}</td>"
            f"<td>{_esc(scan.get('filters_scanned'))}</td>"
            f"<td>{_esc(scan.get('deals_found'))}</td>"
            f"<td>{_esc(scan.get('daily_filter_count'))}</td>"
            f"<td>{_esc(scan.get('max_price_hr'))}</td>"
            f"</tr>"
        )
    return ''.join(rows)


def _render_filter_rows(filter_health: list[dict[str, Any]]) -> str:
    if not filter_health:
        return '<tr><td colspan="6" class="muted">No filter health data yet</td></tr>'
    rows = []
    for item in filter_health[:80]:
        status = item.get("status") or "unknown"
        rows.append(
            f"<tr>"
            f"<td>{_esc(item.get('filter_name'))}</td>"
            f"<td><span class='status status-{_esc(status)}'>{_esc(status)}</span></td>"
            f"<td>{_esc(item.get('scan_count'))}</td>"
            f"<td>{_esc(item.get('deal_count'))}</td>"
            f"<td>{_esc(item.get('days_since_hit'))}</td>"
            f"<td>{_fmt_ts(item.get('last_scan_at'))}</td>"
            f"</tr>"
        )
    return ''.join(rows)


def _render_economy_rows(economy_values: list[tuple[str, Any]]) -> str:
    if not economy_values:
        return '<tr><td colspan="2" class="muted">No economy values loaded</td></tr>'
    return ''.join(f"<tr><td>{_esc(name)}</td><td>{_esc(value)}</td></tr>" for name, value in economy_values)


def render_dashboard(scan_results: dict[str, Any], offer_stats: dict[str, Any], filter_health: list[dict[str, Any]], economy: dict[str, Any]) -> str:
    state = scan_results.get("state", {})
    summary = scan_results.get("summary", {})
    deals = scan_results.get("deals", [])[:24]
    recent_scans = state.get("recent_scans", [])
    economy_values = list((economy.get("values") or {}).items())[:50]
    pending = state.get("pending_confirmation")
    offer_recent = offer_stats.get("recent", [])

    pending_html = _render_deal_card(pending) if pending else '<div class="empty-state">No pending deal right now.</div>'
    deal_cards = ''.join(_render_deal_card(deal) for deal in deals) or '<div class="empty-state">No deals in the current scan results.</div>'

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PD2 Sniper Dashboard</title>
  <style>
    :root {{
      --bg: #0b0d10;
      --panel: #14181f;
      --panel-2: #1a2029;
      --line: #283241;
      --text: #ecf1f7;
      --muted: #9fb0c4;
      --gold: #f5c451;
      --accent: #7dd3fc;
      --green: #69db7c;
      --red: #ff8787;
      --amber: #ffd166;
      --shadow: 0 10px 30px rgba(0,0,0,0.25);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: linear-gradient(180deg, #0b0d10 0%, #11161d 100%);
      color: var(--text);
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 1500px; margin: 0 auto; padding: 24px; }}
    .hero {{ display: flex; justify-content: space-between; gap: 20px; align-items: end; margin-bottom: 24px; }}
    .hero h1 {{ margin: 0 0 8px; font-size: 32px; color: var(--gold); }}
    .hero p {{ margin: 0; color: var(--muted); }}
    .meta-bar {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .badge {{ display: inline-flex; gap: 8px; align-items: center; background: var(--panel); border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; box-shadow: var(--shadow); }}
    .badge-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
    .badge-value {{ font-weight: 700; }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .stat-card, .panel {{ background: rgba(20,24,31,.96); border: 1px solid var(--line); border-radius: 18px; box-shadow: var(--shadow); }}
    .stat-card {{ padding: 18px; }}
    .stat-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }}
    .stat-value {{ font-size: 28px; font-weight: 800; }}
    .stat-sub {{ margin-top: 8px; color: var(--muted); font-size: 13px; }}
    .section {{ margin-bottom: 24px; }}
    .section-header {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }}
    .section-header h2 {{ margin: 0; color: var(--gold); font-size: 22px; }}
    .section-note {{ color: var(--muted); font-size: 13px; }}
    .panel {{ padding: 18px; overflow: hidden; }}
    .deal-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }}
    .deal-card {{ display: grid; grid-template-columns: 220px 1fr; gap: 16px; background: var(--panel-2); border: 1px solid var(--line); border-radius: 16px; overflow: hidden; }}
    .deal-media {{ background: #0f1318; display: flex; align-items: center; justify-content: center; min-height: 200px; }}
    .shot-link, .shot {{ width: 100%; height: 100%; display: block; }}
    .shot {{ object-fit: cover; }}
    .shot-empty {{ color: var(--muted); font-size: 14px; padding: 24px; text-align: center; }}
    .deal-body {{ padding: 16px; display: flex; flex-direction: column; gap: 12px; }}
    .deal-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
    .deal-head h3 {{ margin: 0 0 4px; font-size: 22px; }}
    .deal-sub {{ color: var(--muted); font-size: 13px; }}
    .deal-link {{ white-space: nowrap; font-weight: 700; }}
    .badges, .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{ display: inline-flex; padding: 6px 10px; border-radius: 999px; font-size: 12px; border: 1px solid var(--line); background: #10151c; color: var(--muted); }}
    .chip-corrupt {{ color: var(--amber); border-color: rgba(255, 209, 102, .35); background: rgba(255, 209, 102, .08); }}
    .badge-score .badge-value {{ color: var(--gold); }}
    .badge-price .badge-value {{ color: var(--green); }}
    .badge-warn .badge-value {{ color: var(--amber); }}
    details summary {{ cursor: pointer; color: var(--accent); font-weight: 600; }}
    .stats-list {{ margin: 10px 0 0; padding-left: 18px; color: var(--muted); }}
    .two-col {{ display: grid; grid-template-columns: 1.2fr .8fr; gap: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,.06); text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
    .status {{ display: inline-block; padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .status-healthy {{ background: rgba(105,219,124,.12); color: var(--green); }}
    .status-slow {{ background: rgba(255,135,135,.12); color: var(--red); }}
    .muted, .empty-state {{ color: var(--muted); }}
    .empty-state {{ padding: 18px; border: 1px dashed var(--line); border-radius: 14px; background: rgba(255,255,255,.02); }}
    code.json {{ white-space: pre-wrap; display: block; margin: 0; color: #d9e2ef; background: #0f1318; border: 1px solid var(--line); border-radius: 14px; padding: 14px; }}
    @media (max-width: 980px) {{
      .deal-card {{ grid-template-columns: 1fr; }}
      .two-col {{ grid-template-columns: 1fr; }}
      .hero {{ flex-direction: column; align-items: start; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div>
        <h1>PD2 Market Sniper Dashboard</h1>
        <p>Live scan state, offers, pending confirmations, and clickable deal cards.</p>
      </div>
      <div class="meta-bar">
        {_badge('Last scan', summary.get('timestamp') or '-', 'time')}
        {_badge('Filters scanned', summary.get('filters_scanned') or 0, 'page')}
        {_badge('Deals found', summary.get('deals_found') or 0, 'score')}
        {_badge('Economy refresh', economy.get('refreshed_at') or '-', 'time')}
      </div>
    </section>

    <section class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Pending confirmation</div>
        <div class="stat-value">{_esc('Yes' if pending else 'No')}</div>
        <div class="stat-sub">{_esc((pending or {}).get('item_name') or 'No pending deal stored')}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Offer history</div>
        <div class="stat-value">{_esc(offer_stats.get('total', 0))}</div>
        <div class="stat-sub">{_esc(offer_stats.get('status_counts', {}))}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Daily filter count</div>
        <div class="stat-value">{_esc(summary.get('daily_filter_count', 0))}</div>
        <div class="stat-sub">Max price threshold: {_esc(summary.get('max_price_hr'))} HR</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Current results</div>
        <div class="stat-value">{_esc(len(deals))}</div>
        <div class="stat-sub">Deals currently rendered as cards</div>
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <h2>Pending Deal</h2>
        <div class="section-note">This is the listing `reply-offer` will target.</div>
      </div>
      <div class="panel">{pending_html}</div>
    </section>

    <section class="section">
      <div class="section-header">
        <h2>Current Deal Cards</h2>
        <div class="section-note">Clickable cards with screenshots, links, page numbers, and stats.</div>
      </div>
      <div class="deal-grid">{deal_cards}</div>
    </section>

    <section class="section two-col">
      <div class="panel">
        <div class="section-header"><h2>Recent Offers</h2><div class="section-note">Latest tracked submissions</div></div>
        <table>
          <tr><th>When</th><th>Status</th><th>Item</th><th>Seller</th><th>Offer</th><th>Link</th></tr>
          {_render_offer_rows(offer_recent)}
        </table>
      </div>
      <div class="panel">
        <div class="section-header"><h2>Last Scan Summary</h2><div class="section-note">Raw scan metadata</div></div>
        <code class="json">{_json(summary)}</code>
      </div>
    </section>

    <section class="section two-col">
      <div class="panel">
        <div class="section-header"><h2>Recent Scans</h2><div class="section-note">Historical scan activity</div></div>
        <table>
          <tr><th>When</th><th>Filters</th><th>Deals</th><th>Daily Count</th><th>Max HR</th></tr>
          {_render_scan_rows(recent_scans)}
        </table>
      </div>
      <div class="panel">
        <div class="section-header"><h2>Filter Health</h2><div class="section-note">Slow filters stay in rotation</div></div>
        <table>
          <tr><th>Filter</th><th>Status</th><th>Scans</th><th>Deals</th><th>Days Since Hit</th><th>Last Scan</th></tr>
          {_render_filter_rows(filter_health)}
        </table>
      </div>
    </section>

    <section class="section">
      <div class="panel">
        <div class="section-header"><h2>Economy Values</h2><div class="section-note">Top cached values from pd2.tools</div></div>
        <table>
          <tr><th>Item</th><th>HR</th></tr>
          {_render_economy_rows(economy_values)}
        </table>
      </div>
    </section>
  </div>
</body>
</html>
"""


def write_dashboard(scan_results: dict[str, Any], offer_stats: dict[str, Any], filter_health: list[dict[str, Any]], economy: dict[str, Any]) -> None:
    DASHBOARD_FILE.write_text(render_dashboard(scan_results, offer_stats, filter_health, economy), encoding="utf-8")
