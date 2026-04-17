from __future__ import annotations

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_DIR / "assets"
SCREENSHOTS_DIR = SKILL_DIR / "screenshots"
LOGS_DIR = SKILL_DIR / "logs"

SEEN_FILE = SKILL_DIR / "seen_items.json"
OFFER_HISTORY_FILE = SKILL_DIR / "offer_history.json"
SCAN_RESULTS_FILE = SKILL_DIR / "scan_results.json"
STATE_FILE = SKILL_DIR / "sniper_state.json"
ECONOMY_FILE = ASSETS_DIR / "all_economy.json"
DASHBOARD_FILE = ASSETS_DIR / "dashboard.html"

SITE_ROOT = "https://www.projectdiablo2.com"
MARKET_URL = f"{SITE_ROOT}/market"
PD2_TOOLS_ECONOMY_URLS = {
    "currency": "https://pd2.tools/economy/currency",
    "runes": "https://pd2.tools/economy/runes",
    "ubers": "https://pd2.tools/economy/ubers",
    "maps": "https://pd2.tools/economy/maps",
}

SCAN_DELAY_MIN_SECONDS = 2.0
SCAN_DELAY_MAX_SECONDS = 3.5
DEFAULT_FILTERS_PER_CYCLE = 12
DEFAULT_DAILY_FILTER_LIMIT = 200
SEEN_EXPIRY_HOURS = 36
ECONOMY_REFRESH_HOURS = 24
FILTER_EMPTY_WARNING_DAYS = 7
RECENT_SCAN_HISTORY_LIMIT = 50
RECENT_DEAL_HISTORY_LIMIT = 100
RECENT_OFFER_HISTORY_LIMIT = 200

DEFAULT_MAX_PRICE_HR = 0.5
DEFAULT_OFFER_AMOUNT_HR = 0.25
DEFAULT_TIMEOUT_MS = 30000
DEFAULT_WAIT_AFTER_NAV_SECONDS = 5.0
CHROME_DEBUG_URL = "http://localhost:9222"

FILTERS = {
    "69e0c58f9fc33c4bc7fe0483": "tombsong +skill",
    "69e0ba2f9fc33c4bc7fe043c": "passive GC +GF",
    "69e0b9fd9fc33c4bc7fe043a": "passive glove +2-20p",
    "69e0b9df9fc33c4bc7fe0439": "passive glove +3-20",
    "69e0b9d49fc33c4bc7fe0438": "passive glove +3-30",
    "69e0b9999fc33c4bc7fe0434": "arachnid +20 FCR",
    "69e0b97a9fc33c4bc7fe0433": "valkyrie wing +3 OS",
    "69e0b96c9fc33c4bc7fe0430": "valkyrie wing +skill",
    "69e0b9459fc33c4bc7fe042f": "undead crown +1skill",
    "69e0b90a9fc33c4bc7fe042e": "tombsong +IAS",
    "69e0b8e09fc33c4bc7fe042d": "tombsong +40 pierce",
    "69e0b8ae9fc33c4bc7fe042c": "passive amulet +5",
    "69e0b8a49fc33c4bc7fe042b": "passive amulet +4",
    "69e0b89b9fc33c4bc7fe042a": "passive amulet +3",
    "69e0b5a89fc33c4bc7fe0423": "witchwild +4OS",
    "69e0b5499fc33c4bc7fe0422": "gravepalm +15 DS",
    "69e0b5289fc33c4bc7fe0421": "ebonbane +CB",
    "69e0b51a9fc33c4bc7fe0420": "ebonbane +DS",
    "69e0b4a69fc33c4bc7fe041e": "ebonbane +5os",
    "69e0b47f9fc33c4bc7fe041d": "highlords +ED",
    "69e0b3859fc33c4bc7fe041b": "war trav +frw",
    "69e0b27d9fc33c4bc7fe0419": "gore rider +20 ds",
    "69e0b22d9fc33c4bc7fe0417": "gface +3os",
    "69e0b1db9fc33c4bc7fe0416": "windforce +6os",
    "69e0b18e9fc33c4bc7fe0415": "passive frw GC",
    "69e0b1819fc33c4bc7fe0414": "passive lifer GC",
    "69e0b1629fc33c4bc7fe0413": "atmas +ED",
    "69e0b1509fc33c4bc7fe040e": "atmas +pierce",
    "69e0af2e9fc33c4bc7fe0402": "wraithskin +3os",
    "6950f46ee7a71fc913434b2e": "jav lifer gc",
    "694ad153d295043717c07851": "lite +fhr gc",
    "69411fadbf10a6a498b09ad3": "highlords cbf pierce",
    "693ab400f2584d3e203bee44": "dooms finger +pierce",
    "6939ab117306724e1ce95a90": "bow amp",
    "693134635b1401db14af4642": "spear +amp",
    "693133fe5b1401db14af460e": "war pike +amp",
    "652d6e79813c6cf6f9f24327": "string +all res",
    "652d71d0813c6cf6f9f2436e": "veil +2sk",
    "652d72c2813c6cf6f9f24389": "tyreals",
    "652dfa94ef6e111f977af738": "veil +3os",
    "652e3474dd17e67bc4f98dd2": "BK dual leech",
    "652f714c1fcdfe27910c4199": "bk deathband +leech",
    "6530cb6410db0dc1c4bcda97": "steelrend +deadly",
    "6530cd7410db0dc1c4bcdaa1": "metalgrid +skill",
    "6530de0f10db0dc1c4bcdb14": "metalgrid +cbf",
    "6531f2671067d5a9b3b3d8b9": "atmas +skill",
    "6531f2751067d5a9b3b3d8ba": "atmas +cbf",
    "6531f7112ee1d8d90c9bfd49": "string +max",
    "65320da5fe8a8d3bcff60cdc": "rising sun +skill",
    "6535716ef2ccca08ffd63401": "nosferatu +30 ias",
    "6539c93c3df75bcdae8150f9": "CoA +skill 3os",
    "662315bda0c6f8ef4728877d": "headhunter +1 3os",
    "66253bc516f7f756fa0c2f18": "headhunters +1skill",
    "66259dfc35b8b359394e58c1": "metalgrid +IAS",
    "6848c66a4444294e327a1f49": "fcr dual leach ring",
    "684bb5e7a48bb1e3fd0c3983": "quad res booties",
    "684d78ee9a66c929a9c2d47c": "half freeze trires b",
    "684de0e2b51112230875a22c": "construct 30fcr",
    "6853c3fe872cdd8e946221b3": "spirit ward +3os",
}

for directory in (ASSETS_DIR, SCREENSHOTS_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
