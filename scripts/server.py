#!/usr/bin/env python3
"""Lightweight HTTP server for the PD2 Sniper Dashboard.

Serves the dashboard HTML and provides API endpoints for scan and economy refresh.
Usage: python server.py [--port 8420]
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config import ASSETS_DIR, DASHBOARD_FILE
from history import StateStore

logger = logging.getLogger("pd2-dashboard")

# ── State ──────────────────────────────────────────────────────────────────

DASHBOARD_PORT = 8420
_scan_running = False
_scan_lock = threading.Lock()

SCRIPTS_DIR = Path(__file__).resolve().parent
SNIPER = sys.executable + " " + str(SCRIPTS_DIR / "sniper.py")


def _run_reset_background() -> None:
    """Reset all sniper state for a clean slate / new season."""
    try:
        logger.info("Resetting sniper state...")
        from config import (
            SEEN_FILE, OFFER_HISTORY_FILE, SCAN_RESULTS_FILE, STATE_FILE,
            SCREENSHOTS_DIR, ASSETS_DIR,
        )
        import shutil

        # Clear state files
        for f in [SEEN_FILE, OFFER_HISTORY_FILE, SCAN_RESULTS_FILE]:
            if f.exists():
                f.write_text("{}" if f.suffix == ".json" else "", encoding="utf-8")
                logger.info("Cleared %s", f.name)

        # Reset sniper_state.json to defaults
        if STATE_FILE.exists():
            STATE_FILE.write_text(json.dumps({
                "daily_filter_count": 0,
                "daily_reset_date": None,
                "rotation_index": 0,
                "filter_health": [],
                "recent_scans": [],
                "pending_confirmation": None,
                "last_economy_refresh": None,
            }, indent=2), encoding="utf-8")
            logger.info("Reset %s", STATE_FILE.name)

        # Clear screenshots
        if SCREENSHOTS_DIR.exists():
            for f in SCREENSHOTS_DIR.glob("*"):
                if f.is_file():
                    f.unlink()
            logger.info("Cleared screenshots")

        # Regenerate empty dashboard
        _refresh_dashboard()
        logger.info("Reset complete — clean slate")
    except Exception as exc:
        logger.error("Reset failed: %s", exc)


def _refresh_dashboard() -> None:
    """Regenerate dashboard.html from current state files."""
    try:
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "sniper.py"), "dashboard"],
            capture_output=True, text=True, timeout=30,
        )
        logger.info("Dashboard refreshed")
    except Exception as exc:
        logger.error("Dashboard refresh failed: %s", exc)


GATEWAY_URL = "http://127.0.0.1:18789/v1/chat/completions"


def _notify_agent(message: str) -> None:
    """Send scan results to the OpenClaw agent via the gateway HTTP API.

    Falls back to writing a notification file if the gateway is unreachable.
    """
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "model": "openclaw/default",
            "messages": [{"role": "user", "content": message}],
        }).encode("utf-8")

        req = urllib.request.Request(
            GATEWAY_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("Gateway notification sent (HTTP %d)", resp.status)
    except Exception as exc:
        logger.warning("Gateway notification failed (%s), writing file fallback", exc)
        try:
            notify_file = ASSETS_DIR / "_scan_notify.json"
            payload = {
                "pending": True,
                "message": message,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            notify_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc2:
            logger.warning("File notification also failed: %s", exc2)


def _run_scan_background() -> None:
    """Run a full operator scan in a background thread."""
    global _scan_running
    try:
        logger.info("Starting full scan...")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "sniper.py"),
             "operator-scan", "--max-price", "999",
             "--filters-per-cycle", "100", "--daily-limit", "200",
             "--max-pages", "50", "--top", "3"],
            capture_output=True, text=True, timeout=600,
            cwd=str(SCRIPTS_DIR),
        )
        if result.returncode == 0:
            logger.info("Scan completed successfully")
            deals_output = result.stdout.strip()
            if deals_output:
                _notify_agent(
                    "PD2 scan notification check: A market scan triggered from the dashboard just completed. "
                    "Read C:\\Users\\jding\\.agents\\skills\\pd2-market-sniper\\scan_results.json "
                    "and present the deals to the user. For each deal, show the item name, stats, "
                    "listed price, estimated value, and ask for an offer amount. "
                    "Do NOT reply HEARTBEAT_OK — present the deals now.\n\n" + deals_output
                )
        else:
            logger.error("Scan failed (exit %d): %s", result.returncode, result.stderr[:500])
    except Exception as exc:
        logger.error("Scan failed: %s", exc)
    finally:
        with _scan_lock:
            _scan_running = False


def _run_economy_refresh_background() -> None:
    """Force-refresh economy data in a background thread."""
    try:
        logger.info("Starting economy refresh...")
        result = subprocess.Popen(
            [sys.executable, str(SCRIPTS_DIR / "sniper.py"), "economy", "--force"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(SCRIPTS_DIR),
        )
        stdout, stderr = result.communicate(timeout=120)
        stdout = stdout.decode("utf-8", errors="replace")
        stderr = stderr.decode("utf-8", errors="replace")
        if result.returncode == 0:
            logger.info("Economy refresh completed: %s", stdout.strip())
            _refresh_dashboard()
        else:
            logger.error("Economy refresh failed (exit %d): %s", result.returncode, stderr[:500])
    except Exception as exc:
        logger.error("Economy refresh failed: %s", exc)


# ── HTTP Handler ───────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    """Serves dashboard assets and API endpoints."""

    def log_message(self, format, *args):
        logger.debug(format, *args)

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/dashboard" or path == "/dashboard.html":
            self._send_file(DASHBOARD_FILE, "text/html; charset=utf-8")
        elif path == "/api/status":
            state = StateStore()
            pending = state.get_pending_confirmation()
            with _scan_lock:
                running = _scan_running
            self._send_json({
                "status": "running",
                "scan_running": running,
                "pending_deal": pending.get("item_name") if pending else None,
            })
        else:
            # Serve screenshots and other assets relative to skill dir
            skill_dir = ASSETS_DIR.parent
            rel = path.lstrip("/")
            file_path = skill_dir / rel
            if file_path.exists() and file_path.is_file():
                ext = file_path.suffix.lower()
                ct_map = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".json": "application/json",
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".html": "text/html; charset=utf-8",
                }
                self._send_file(file_path, ct_map.get(ext, "application/octet-stream"))
            else:
                self.send_error(404)

    def do_POST(self) -> None:
        global _scan_running
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/scan":
            with _scan_lock:
                if _scan_running:
                    self._send_json({"ok": False, "error": "Scan already running"}, 409)
                    return
                _scan_running = True

            t = threading.Thread(target=_run_scan_background, daemon=True)
            t.start()
            self._send_json({"ok": True, "message": "Scan started"})

        elif path == "/api/economy-refresh":
            try:
                subprocess.Popen(
                    [sys.executable, str(SCRIPTS_DIR / "sniper.py"), "economy", "--force"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd=str(SCRIPTS_DIR),
                )
                self._send_json({"ok": True, "message": "Economy refresh started"})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)

        elif path == "/api/scan-stop":
            with _scan_lock:
                if not _scan_running:
                    self._send_json({"ok": False, "error": "No scan running"}, 409)
                    return
                _scan_running = False
            self._send_json({"ok": True, "message": "Scan stopped"})

        elif path == "/api/refresh-dashboard":
            _refresh_dashboard()
            self._send_json({"ok": True, "message": "Dashboard refreshed"})
        elif path == "/api/reset":
            t = threading.Thread(target=_run_reset_background, daemon=True)
            t.start()
            self._send_json({"ok": True, "message": "Reset started"})

        elif path == "/api/price-check":
            # Price check an item using PD2Trader API
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length else {}
            item_name = body.get("item_name", "")
            if not item_name:
                self._send_json({"error": "item_name required"}, 400)
                return
            from alerts import price_confidence
            result = price_confidence(item_name, body.get("listed_price", 0))
            self._send_json(result)

        elif path == "/api/offer-status":
            # Get incoming/outgoing offer status
            from offers import get_my_outgoing_offers, get_my_incoming_offers
            self._send_json({
                "outgoing": get_my_outgoing_offers(),
                "incoming": get_my_incoming_offers(),
            })

        elif path == "/api/market-search":
            # Direct market search via API
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length else {}
            from market_search import build_search_query, search_listings
            query = build_search_query(**body)
            result = search_listings(query)
            self._send_json(result or {"error": "search failed"})

        else:
            self.send_error(404)


# ── Main ───────────────────────────────────────────────────────────────────

def serve(port: int, open_browser: bool = True) -> None:
    """Start the dashboard HTTP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    _refresh_dashboard()

    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    logger.info("PD2 Dashboard server running at http://localhost:%d", port)

    # Run HTTP server in a daemon thread
    http_thread = threading.Thread(target=server.serve_forever, daemon=True)
    http_thread.start()

    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PD2 Sniper Dashboard Server")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT, help=f"Port to serve on (default: {DASHBOARD_PORT})")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()
    serve(args.port, open_browser=not args.no_browser)
