from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from config import DASHBOARD_FILE, ECONOMY_REFRESH_HOURS


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


def _deal_search_text(deal: dict[str, Any]) -> str:
    parts = [
        deal.get("item_name"),
        deal.get("filter_name"),
        deal.get("seller_name"),
        deal.get("listing_url"),
        deal.get("posted_at"),
        " ".join(str(v) for v in deal.get("stats") or []),
        " ".join(str(v) for v in deal.get("corruption") or []),
    ]
    return " | ".join(str(p or "") for p in parts).lower()


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

    search_text = _esc(_deal_search_text(deal))
    return f"""
    <article class="deal-card" data-search="{search_text}">
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
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 14px; }}
    .search-input {{
      width: min(560px, 100%);
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #0f1318;
      color: var(--text);
      padding: 12px 14px;
      font-size: 14px;
      outline: none;
      box-shadow: var(--shadow);
    }}
    .search-input:focus {{ border-color: var(--accent); }}
    .search-hint {{ color: var(--muted); font-size: 13px; }}
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
    .hidden {{ display: none !important; }}
    .btn-refresh {{ display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 12px; border: 1px solid var(--line); background: #0f1318; color: var(--accent); font-size: 13px; font-weight: 600; cursor: pointer; transition: all .15s; }}
    .btn-refresh:hover {{ border-color: var(--accent); background: rgba(125,211,252,.06); }}
    .btn-refresh:active {{ transform: scale(.96); }}
    .btn-refresh.loading {{ opacity: .5; pointer-events: none; }}
    .btn-refresh .spinner {{ display: none; width: 14px; height: 14px; border: 2px solid rgba(125,211,252,.3); border-top-color: var(--accent); border-radius: 50%; animation: spin .6s linear infinite; }}
    .btn-refresh.loading .spinner {{ display: inline-block; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .btn-scan {{
      position: relative;
      display: inline-flex; align-items: center; gap: 8px;
      padding: 14px 28px;
      border-radius: 16px;
      border: 2px solid transparent;
      background-clip: padding-box;
      background: #0f1318;
      color: var(--gold);
      font-size: 16px;
      font-weight: 800;
      letter-spacing: .02em;
      cursor: pointer;
      transition: all .2s;
      box-shadow: 0 0 20px rgba(245,196,81,.15);
    }}
    .btn-scan:hover {{ background: rgba(245,196,81,.08); transform: translateY(-1px); box-shadow: 0 0 30px rgba(245,196,81,.25); }}
    .btn-scan:active {{ transform: scale(.97); }}
    .btn-scan.loading {{ opacity: .5; pointer-events: none; }}
    .btn-scan.loading .spinner {{ display: inline-block; }}
    .btn-scan .spinner {{ display: none; width: 18px; height: 18px; border: 3px solid rgba(245,196,81,.3); border-top-color: var(--gold); border-radius: 50%; animation: spin .6s linear infinite; }}
    .btn-scan::before {{
      content: '';
      position: absolute;
      inset: -3px;
      border-radius: 18px;
      background: conic-gradient(from var(--glow-angle, 0deg), var(--gold), #ff8787, var(--accent), #69db7c, var(--gold));
      z-index: -1;
      animation: glow-spin 3s linear infinite;
      opacity: .7;
      transition: opacity .2s;
    }}
    .btn-scan:hover::before {{ opacity: 1; }}
    .btn-scan::after {{
      content: '';
      position: absolute;
      inset: -3px;
      border-radius: 18px;
      background: conic-gradient(from var(--glow-angle, 0deg), var(--gold), #ff8787, var(--accent), #69db7c, var(--gold));
      z-index: -1;
      animation: glow-spin 3s linear infinite;
      filter: blur(12px);
      opacity: .4;
      transition: opacity .2s;
    }}
    .btn-scan:hover::after {{ opacity: .7; }}
    @property --glow-angle {{ syntax: '<angle>'; inherits: false; initial-value: 0deg; }}
    @keyframes glow-spin {{ to {{ --glow-angle: 360deg; }} }}
    .toast {{ position: fixed; bottom: 24px; right: 24px; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px 20px; color: var(--text); font-size: 14px; box-shadow: var(--shadow); z-index: 9999; transform: translateY(100px); opacity: 0; transition: all .3s ease; }}
    .toast.show {{ transform: translateY(0); opacity: 1; }}
    .toast.success {{ border-color: rgba(105,219,124,.4); }}
    .toast.error {{ border-color: rgba(255,135,135,.4); }}
    code.json {{ white-space: pre-wrap; display: block; margin: 0; color: #d9e2ef; background: #0f1318; border: 1px solid var(--line); border-radius: 14px; padding: 14px; }}
    .server-bar {{ display: flex; align-items: center; gap: 12px; margin-bottom: 18px; padding: 10px 16px; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; }}
    .server-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
    .server-dot.online {{ background: var(--green); box-shadow: 0 0 8px rgba(105,219,124,.5); animation: pulse-green 2s ease-in-out infinite; }}
    .server-dot.offline {{ background: var(--red); box-shadow: 0 0 6px rgba(255,135,135,.3); }}
    .server-label {{ font-size: 13px; font-weight: 600; }}
    .server-label.online {{ color: var(--green); }}
    .server-label.offline {{ color: var(--red); }}
    .server-url {{ font-size: 12px; color: var(--muted); }}
    .server-url a {{ color: var(--accent); font-weight: 600; }}
    .btn-start-server {{ margin-left: auto; padding: 8px 16px; border-radius: 10px; border: 1px solid var(--line); background: #0f1318; color: var(--gold); font-size: 13px; font-weight: 700; cursor: pointer; transition: all .15s; }}
    .btn-start-server:hover {{ border-color: var(--gold); background: rgba(245,196,81,.08); }}
    .btn-start-server:active {{ transform: scale(.96); }}
    .btn-reset {{ padding: 8px 14px; border-radius: 10px; border: 1px solid rgba(255,135,135,.3); background: rgba(255,135,135,.06); color: var(--red); font-size: 12px; font-weight: 700; cursor: pointer; transition: all .15s; letter-spacing: .02em; }}
    .btn-reset:hover {{ border-color: var(--red); background: rgba(255,135,135,.12); }}
    .btn-reset:active {{ transform: scale(.96); }}
    .reset-confirm {{ position: fixed; inset: 0; background: rgba(0,0,0,.7); display: flex; align-items: center; justify-content: center; z-index: 10000; }}
    .reset-confirm-box {{ background: var(--panel); border: 1px solid var(--red); border-radius: 18px; padding: 28px; max-width: 420px; text-align: center; box-shadow: 0 20px 60px rgba(0,0,0,.5); }}
    .reset-confirm-box h3 {{ margin: 0 0 12px; color: var(--red); font-size: 20px; }}
    .reset-confirm-box p {{ color: var(--muted); font-size: 14px; margin: 0 0 20px; line-height: 1.5; }}
    .reset-confirm-box .btn-row {{ display: flex; gap: 12px; justify-content: center; }}
    .reset-confirm-box .btn-cancel {{ padding: 10px 20px; border-radius: 10px; border: 1px solid var(--line); background: transparent; color: var(--muted); font-size: 14px; cursor: pointer; }}
    .reset-confirm-box .btn-cancel:hover {{ border-color: var(--text); color: var(--text); }}
    .reset-confirm-box .btn-danger {{ padding: 10px 20px; border-radius: 10px; border: 1px solid var(--red); background: rgba(255,135,135,.15); color: var(--red); font-size: 14px; font-weight: 700; cursor: pointer; }}
    .reset-confirm-box .btn-danger:hover {{ background: rgba(255,135,135,.25); }}
    @keyframes pulse-green {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .6; }} }}
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
        <button id="scanNow" class="btn-scan" title="Run a full scan of all PD2 market filters">
          <span class="spinner"></span>
          <span id="scanNowLabel">🔍 Scan Now</span>
        </button>
        <button id="resetBtn" class="btn-reset" title="Clear all scan history, offers, seen items, and screenshots for a fresh start">🗑️ Reset</button>
      </div>
    </section>

    <div id="serverBar" class="server-bar">
      <span id="serverDot" class="server-dot offline"></span>
      <span id="serverLabel" class="server-label offline">Server offline</span>
      <span id="serverUrl" class="server-url" style="display:none">Live at <a href="http://localhost:8420" target="_blank">localhost:8420</a></span>
      <button id="startServer" class="btn-start-server" title="Start the dashboard server (python sniper.py serve)">⚡ Start Server</button>
    </div>

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
      <div class="toolbar">
        <input id="dealSearch" class="search-input" type="search" placeholder="Search deals by item, seller, filter, stats, corruption..." />
        <div id="dealSearchCount" class="search-hint">Showing {len(deals)} of {len(deals)} deals</div>
      </div>
      <div id="dealGrid" class="deal-grid">{deal_cards}</div>
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
        <div class="section-header">
          <div style="display:flex;align-items:center;gap:12px">
            <h2>Economy Values</h2>
            <button id="econRefresh" class="btn-refresh" title="Refresh economy values from pd2.tools (requires Chrome CDP)">
              <span class="spinner"></span>
              <span id="econRefreshLabel">🔄 Sync</span>
            </button>
          </div>
          <div class="section-note">Cached values from pd2.tools · Auto-refreshes every {_esc(ECONOMY_REFRESH_HOURS)}h during scans</div>
        </div>
        <table>
          <tr><th>Item</th><th>HR</th></tr>
          {_render_economy_rows(economy_values)}
        </table>
      </div>
    </section>
  </div>
  <script>
    (() => {{
      // Deal search
      const input = document.getElementById('dealSearch');
      const count = document.getElementById('dealSearchCount');
      const cards = Array.from(document.querySelectorAll('#dealGrid .deal-card'));
      if (input && count && cards.length) {{
        const update = () => {{
          const query = input.value.trim().toLowerCase();
          let visible = 0;
          for (const card of cards) {{
            const haystack = (card.dataset.search || '').toLowerCase();
            const match = !query || haystack.includes(query);
            card.classList.toggle('hidden', !match);
            if (match) visible += 1;
          }}
          count.textContent = `Showing ${{visible}} of ${{cards.length}} deals`;
        }};
        input.addEventListener('input', update);
        update();
      }}

      // Toast helper
      function showToast(msg, type = 'success', duration = 3000) {{
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();
        const t = document.createElement('div');
        t.className = `toast ${{type}}`;
        t.textContent = msg;
        document.body.appendChild(t);
        requestAnimationFrame(() => requestAnimationFrame(() => t.classList.add('show')));
        setTimeout(() => {{
          t.classList.remove('show');
          setTimeout(() => t.remove(), 300);
        }}, duration);
      }}

      // Server status check
      const serverDot = document.getElementById('serverDot');
      const serverLabel = document.getElementById('serverLabel');
      const serverUrl = document.getElementById('serverUrl');
      const startBtn = document.getElementById('startServer');
      let serverOnline = false;

      async function checkServer() {{
        try {{
          const resp = await fetch('/api/status', {{ signal: AbortSignal.timeout(2000) }});
          if (resp.ok) {{
            serverOnline = true;
            serverDot.className = 'server-dot online';
            serverLabel.className = 'server-label online';
            serverLabel.textContent = '✅ Server online';
            serverUrl.style.display = '';
            if (startBtn) startBtn.style.display = 'none';
            return true;
          }}
        }} catch {{}}
        serverOnline = false;
        serverDot.className = 'server-dot offline';
        serverLabel.className = 'server-label offline';
        serverLabel.textContent = 'Server offline';
        serverUrl.style.display = 'none';
        if (startBtn) startBtn.style.display = '';
        return false;
      }}

      // Check on load and every 30s
      checkServer();
      setInterval(checkServer, 30000);

      // Start Server button
      if (startBtn) {{
        startBtn.addEventListener('click', async () => {{
          startBtn.textContent = 'Starting...';
          startBtn.style.pointerEvents = 'none';
          try {{
            // Try opening the serve URL which triggers the server launch
            // This only works if the page is served through OpenClaw or similar
            // Otherwise copy the command
            const cmd = 'python scripts/sniper.py serve';
            try {{
              await navigator.clipboard.writeText(cmd);
              showToast('📋 Run this in a terminal: ' + cmd, 'success', 6000);
            }} catch {{
              showToast('⚡ Run in terminal: python sniper.py serve --port 8420', 'success', 6000);
            }}
            // Poll for server coming online
            startBtn.textContent = 'Waiting...';
            let attempts = 0;
            const poll = setInterval(async () => {{
              attempts++;
              const online = await checkServer();
              if (online) {{
                clearInterval(poll);
                showToast('✅ Server is live! Switching to live dashboard...', 'success', 3000);
                setTimeout(() => window.location.href = 'http://localhost:8420', 2000);
              }} else if (attempts > 30) {{
                clearInterval(poll);
                startBtn.textContent = '⚡ Start Server';
                startBtn.style.pointerEvents = '';
                showToast('⏰ Timed out waiting for server', 'error', 4000);
              }}
            }}, 2000);
          }} catch {{
            startBtn.textContent = '⚡ Start Server';
            startBtn.style.pointerEvents = '';
          }}
        }});
      }}

      // Scan Now button
      const scanBtn = document.getElementById('scanNow');
      const scanLabel = document.getElementById('scanNowLabel');
      if (scanBtn) {{
        scanBtn.addEventListener('click', async () => {{
          scanBtn.classList.add('loading');
          scanLabel.textContent = 'Scanning...';
          try {{
            const resp = await fetch('/api/scan', {{ method: 'POST' }});
            const data = await resp.json();
            if (resp.ok && data.ok) {{
              showToast('🔍 Scan started — dashboard will auto-refresh', 'success', 4000);
              // Poll for completion
              const poll = setInterval(async () => {{
                try {{
                  const s = await (await fetch('/api/status')).json();
                  if (!s.scan_running) {{
                    clearInterval(poll);
                    showToast('✅ Scan complete! ' + (s.pending_deal ? 'Deal: ' + s.pending_deal : 'No new deals'), 'success', 5000);
                    location.reload();
                  }}
                }} catch {{}}
              }}, 5000);
            }} else {{
              showToast(data.error || 'Scan already in progress', 'error', 4000);
            }}
          }} catch (e) {{
            const cmd = 'python scripts/sniper.py operator-scan --max-price 999 --filters-per-cycle 100 --daily-limit 200 --max-pages 50 --top 3';
            try {{
              await navigator.clipboard.writeText(cmd);
              showToast('📋 Server not running — command copied! Paste to Sir Claw', 'success', 5000);
            }} catch {{
              showToast('❌ Server not reachable. Run: python sniper.py serve', 'error', 8000);
            }}
          }} finally {{
            scanBtn.classList.remove('loading');
            scanLabel.textContent = '🔍 Scan Now';
          }}
        }});
      }}

      // Economy refresh button
      const btn = document.getElementById('econRefresh');
      const btnLabel = document.getElementById('econRefreshLabel');
      if (btn) {{
        btn.addEventListener('click', async () => {{
          btn.classList.add('loading');
          btnLabel.textContent = 'Syncing...';
          try {{
            const resp = await fetch('/api/economy-refresh', {{ method: 'POST' }});
            const data = await resp.json();
            if (resp.ok && data.ok) {{
              showToast('🔄 Economy values refreshed!', 'success');
              setTimeout(() => location.reload(), 1500);
            }} else {{
              throw new Error(data.error || 'Failed');
            }}
          }} catch {{
            const cmd = 'python scripts/sniper.py economy --force && python scripts/sniper.py dashboard';
            try {{
              await navigator.clipboard.writeText(cmd);
              showToast('📋 Server not running — command copied! Paste to Sir Claw', 'success', 5000);
            }} catch {{
              showToast('❌ Server not reachable. Run: python sniper.py serve', 'error', 8000);
            }}
          }} finally {{
            btn.classList.remove('loading');
            btnLabel.textContent = '🔄 Sync';
          }}
        }});
      }}
      // Reset button
      const resetBtn = document.getElementById('resetBtn');
      if (resetBtn) {{
        resetBtn.addEventListener('click', () => {{
          // Show confirmation modal
          const overlay = document.createElement('div');
          overlay.className = 'reset-confirm';
          overlay.innerHTML = `
            <div class="reset-confirm-box">
              <h3>⚠️ Reset All Data?</h3>
              <p>This will clear:\n• All scan history and results\n• Seen items tracker\n• Offer history\n• Filter health data\n• All screenshots\n\nEconomy values are kept. This cannot be undone.</p>
              <div class="btn-row">
                <button id="resetCancel" class="btn-cancel">Cancel</button>
                <button id="resetConfirm" class="btn-danger">Reset Everything</button>
              </div>
            </div>
          `;
          document.body.appendChild(overlay);

          document.getElementById('resetCancel').addEventListener('click', () => overlay.remove());
          overlay.addEventListener('click', (e) => {{ if (e.target === overlay) overlay.remove(); }});

          document.getElementById('resetConfirm').addEventListener('click', async () => {{
            overlay.remove();
            resetBtn.textContent = 'Resetting...';
            resetBtn.style.pointerEvents = 'none';
            try {{
              const resp = await fetch('/api/reset', {{ method: 'POST' }});
              const data = await resp.json();
              if (resp.ok && data.ok) {{
                showToast('🗑️ All data cleared — refreshing...', 'success', 3000);
                setTimeout(() => location.reload(), 2000);
              }} else {{
                throw new Error(data.error || 'Failed');
              }}
            }} catch {{
              showToast('❌ Server not running — run: python sniper.py serve', 'error', 5000);
              resetBtn.textContent = '🗑️ Reset';
              resetBtn.style.pointerEvents = '';
            }}
          }});
        }});
      }}
    }})();
  </script>
</body>
</html>
"""


def write_dashboard(scan_results: dict[str, Any], offer_stats: dict[str, Any], filter_health: list[dict[str, Any]], economy: dict[str, Any]) -> None:
    DASHBOARD_FILE.write_text(render_dashboard(scan_results, offer_stats, filter_health, economy), encoding="utf-8")
