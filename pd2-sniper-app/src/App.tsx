import { useState, useEffect, useCallback, useRef } from "react";
import "./App.css";

const API = "http://localhost:8420";

interface ServerStatus {
  status: string;
  scan_running: boolean;
  pending_deal: string | null;
}

interface DealCard {
  item_name: string;
  price_hr: number;
  seller_name: string;
  filter_name: string;
  score: number;
  listing_url: string;
  stats?: string[];
  corruption?: string[];
  economy_value_hr?: number;
  screenshot?: string;
}

interface EconomyValue {
  refreshed_at: string;
  values: Record<string, number>;
}

type Tab = "deals" | "economy" | "offers" | "settings";

export default function App() {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [deals, setDeals] = useState<DealCard[]>([]);
  const [economy, setEconomy] = useState<EconomyValue | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("deals");
  const [offerAmounts, setOfferAmounts] = useState<Record<number, string>>({});
  const [selectedDeal, setSelectedDeal] = useState<number | null>(null);
  const [serverStarting, setServerStarting] = useState(true);
  const scanPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll server status
  useEffect(() => {
    let attempts = 0;
    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/status`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          if (data.scan_running) setLoading(true);
          setServerStarting(false);
        }
      } catch {
        setStatus(null);
        attempts++;
        if (attempts > 30) setServerStarting(false);
      }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  const loadDeals = useCallback(async () => {
    try {
      // Refresh dashboard first
      await fetch(`${API}/api/refresh-dashboard`, { method: "POST" });

      // Try loading scan results via multiple paths
      for (const path of ["/assets/scan_results.json", "/scan_results.json"]) {
        try {
          const res = await fetch(`${API}${path}`);
          if (res.ok) {
            const data = await res.json();
            if (data.deals && data.deals.length > 0) {
              setDeals(data.deals);
              return;
            }
          }
        } catch { /* next path */ }
      }
    } catch { /* ignore */ }
  }, []);

  const loadEconomy = useCallback(async () => {
    try {
      for (const path of ["/assets/all_economy.json", "/all_economy.json"]) {
        try {
          const res = await fetch(`${API}${path}`);
          if (res.ok) {
            const data = await res.json();
            if (data.values && Object.keys(data.values).length > 0) {
              setEconomy(data);
              return;
            }
          }
        } catch { /* next path */ }
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (status) {
      loadDeals();
      loadEconomy();
    }
  }, [status, loadDeals, loadEconomy]);

  useEffect(() => {
    return () => {
      if (scanPollRef.current) clearInterval(scanPollRef.current);
    };
  }, []);

  const handleScan = async () => {
    if (loading) {
      try { await fetch(`${API}/api/scan-stop`, { method: "POST" }); } catch { /* */ }
      setLoading(false);
      if (scanPollRef.current) { clearInterval(scanPollRef.current); scanPollRef.current = null; }
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/scan`, { method: "POST" });
      const data = await res.json();
      if (!data.ok) { setError(data.error || "Scan failed"); setLoading(false); return; }
      scanPollRef.current = setInterval(async () => {
        try {
          const s = await (await fetch(`${API}/api/status`)).json();
          if (!s.scan_running) {
            if (scanPollRef.current) clearInterval(scanPollRef.current);
            scanPollRef.current = null;
            setLoading(false);
            await loadDeals();
          }
        } catch { /* */ }
      }, 3000);
    } catch (exc: any) { setError(exc.message); setLoading(false); }
  };

  const handleEconomyRefresh = async () => {
    try {
      await fetch(`${API}/api/economy-refresh`, { method: "POST" });
      // Poll for updated data
      let tries = 0;
      const poll = setInterval(async () => {
        tries++;
        for (const path of ["/assets/all_economy.json", "/all_economy.json"]) {
          try {
            const res = await fetch(`${API}${path}`);
            if (res.ok) {
              const data = await res.json();
              if (data.values && Object.keys(data.values).length > 0) {
                setEconomy(data);
                clearInterval(poll);
                return;
              }
            }
          } catch { /* */ }
        }
        if (tries > 30) clearInterval(poll);
      }, 2000);
    } catch { /* */ }
  };

  const handleReset = async () => {
    if (!window.confirm("Reset all data for a clean slate? This keeps economy values.")) return;
    await fetch(`${API}/api/reset`, { method: "POST" });
    setDeals([]);
    setSelectedDeal(null);
  };

  const handlePriceCheck = async (itemName: string) => {
    try {
      const res = await fetch(`${API}/api/price-check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_name: itemName, listed_price: 0 }),
      });
      if (res.ok) return await res.json();
    } catch { /* */ }
    return null;
  };

  const filteredDeals = deals.filter((d) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      d.item_name?.toLowerCase().includes(q) ||
      d.seller_name?.toLowerCase().includes(q) ||
      d.filter_name?.toLowerCase().includes(q) ||
      d.stats?.some((s) => s.toLowerCase().includes(q))
    );
  });

  const econEntries = economy
    ? Object.entries(economy.values).sort(([, a], [, b]) => (b as number) - (a as number))
    : [];

  const killServer = async () => {
    if (!confirm("Stop the Python server? The app will go offline until restarted.")) return;
    try {
      await fetch(`${API}/api/shutdown`, { method: "POST" });
    } catch { /* server already gone */ }
    setStatus(null);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1 className="logo">🎯 PD2 Market Sniper</h1>
          <span className={`status-dot ${status ? "online" : serverStarting ? "starting" : "offline"}`} />
          <span className="status-text">
            {serverStarting ? "Starting Server..." : status ? "Server Online" : "Server Offline"}
          </span>
          {status && !serverStarting && (
            <button className="btn btn-xs" onClick={killServer} title="Stop server" style={{ marginLeft: 6 }}>✕</button>
          )}
        </div>
        <div className="header-actions">
          <button className={`btn ${loading ? "btn-stop" : "btn-gold"}`} onClick={handleScan} disabled={!status && !loading}>
            {loading ? <><span className="spinner-red" /> ⏹ Stop</> : "🔍 Scan Now"}
          </button>
          <button className="btn btn-secondary" onClick={handleEconomyRefresh} disabled={!status}>🔄 Econ</button>
          <button className="btn btn-danger" onClick={handleReset}>🗑️</button>
        </div>
      </header>

      {error && (
        <div className="error-bar">
          {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <nav className="tabs">
        {(["deals", "economy", "offers", "settings"] as Tab[]).map((tab) => (
          <button key={tab} className={`tab ${activeTab === tab && "active"}`} onClick={() => setActiveTab(tab)}>
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
            {tab === "deals" && deals.length > 0 && <span className="badge">{deals.length}</span>}
            {tab === "economy" && economy && <span className="badge">{Object.keys(economy.values).length}</span>}
          </button>
        ))}
      </nav>

      <main className="content">
        {!status && !serverStarting && (
          <div className="center-state">
            <div className="empty-icon">🔌</div>
            <p>Server Offline</p>
            <p className="hint">Make sure Python is installed and sniper.py is accessible</p>
          </div>
        )}

        {serverStarting && !status && (
          <div className="center-state">
            <div className="empty-icon">⏳</div>
            <p>Starting Python backend...</p>
          </div>
        )}

        {status && activeTab === "deals" && (
          <>
            <div className="search-bar">
              <input type="text" placeholder="Search deals by name, seller, stat..." value={search} onChange={(e) => setSearch(e.target.value)} />
              {search && <span className="result-count">{filteredDeals.length} results</span>}
            </div>
            {filteredDeals.length === 0 ? (
              <div className="center-state">
                <div className="empty-icon">🎯</div>
                <p>No deals found yet</p>
                <p className="hint">Click "Scan Now" to search the market</p>
              </div>
            ) : (
              <div className="deal-grid">
                {filteredDeals.map((deal, i) => (
                  <DealCardView key={i} deal={deal} expanded={selectedDeal === i}
                    onExpand={() => setSelectedDeal(selectedDeal === i ? null : i)}
                    offerAmount={offerAmounts[i] || ""}
                    onOfferChange={(val) => setOfferAmounts({ ...offerAmounts, [i]: val })}
                    onPriceCheck={handlePriceCheck} />
                ))}
              </div>
            )}
          </>
        )}

        {status && activeTab === "economy" && (
          <div className="economy-panel">
            <div className="economy-header">
              <h2>Economy Values</h2>
              {economy?.refreshed_at && (
                <span className="refreshed">Last refreshed: {new Date(economy.refreshed_at).toLocaleString()}</span>
              )}
            </div>
            {!economy || econEntries.length === 0 ? (
              <div className="center-state">
                <div className="empty-icon">📊</div>
                <p>No economy data loaded</p>
                <p className="hint">Click "🔄 Econ" in the header to fetch prices from PD2Trader</p>
              </div>
            ) : (
              <div className="economy-grid">
                {econEntries.map(([name, price]) => (
                  <div key={name} className="econ-row">
                    <span className="econ-name">{name}</span>
                    <span className="econ-price">{(price as number).toFixed(4)} HR</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {status && activeTab === "offers" && <OffersTab />}

        {activeTab === "settings" && <SettingsTab />}
      </main>
    </div>
  );
}

// ── Offers Tab ────────────────────────────────────────────────────────────

function OffersTab() {
  const [offers, setOffers] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const loadOffers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/offer-status`);
      if (res.ok) setOffers(await res.json());
    } catch { /* */ }
    setLoading(false);
  };

  return (
    <div className="settings-panel">
      <h2>Trade Offers</h2>
      <p className="hint" style={{ marginBottom: 16 }}>
        View incoming and outgoing offers. Requires PD2 auth token in Settings.
      </p>
      <button className="btn btn-gold" onClick={loadOffers} disabled={loading}>
        {loading ? "Loading..." : "🔄 Check Offers"}
      </button>
      {offers && (
        <div style={{ marginTop: 16 }}>
          <h3>Outgoing ({offers.outgoing?.length || 0})</h3>
          <h3>Incoming ({offers.incoming?.length || 0})</h3>
          <pre className="code-block">{JSON.stringify(offers, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

// ── Hotkey System ─────────────────────────────────────────────────────────

type HotkeyAction = "scan" | "economy" | "dashboard";

const HOTKEYS_KEY = "pd2-sniper-hotkeys";
const DEFAULT_HOTKEYS: Record<HotkeyAction, string> = {
  scan: "Ctrl+Shift+S",
  economy: "Ctrl+Shift+E",
  dashboard: "Ctrl+Shift+D",
};

function loadHotkeys(): Record<HotkeyAction, string> {
  try {
    const saved = localStorage.getItem(HOTKEYS_KEY);
    if (saved) return { ...DEFAULT_HOTKEYS, ...JSON.parse(saved) };
  } catch {}
  return { ...DEFAULT_HOTKEYS };
}

function saveHotkeys(keys: Record<HotkeyAction, string>) {
  localStorage.setItem(HOTKEYS_KEY, JSON.stringify(keys));
}

function HotkeyRow({ action, label, defaultKeys, onTrigger: _onTrigger }: {
  action: HotkeyAction; label: string; defaultKeys: string;
  onTrigger: (action: HotkeyAction) => void;
}) {
  const [hotkeys, setHotkeys] = useState(loadHotkeys);
  const [recording, setRecording] = useState(false);
  const kbdRef = useRef<HTMLDivElement>(null);

  const currentKeys = hotkeys[action] || defaultKeys;

  const startRecording = () => {
    setRecording(true);
    // Focus the kbd element so it receives key events
    setTimeout(() => kbdRef.current?.focus(), 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!recording) return;
    e.preventDefault();
    e.stopPropagation();

    // Build combo from modifier state + the actual key pressed
    const parts: string[] = [];
    if (e.ctrlKey || e.metaKey) parts.push("Ctrl");
    if (e.altKey) parts.push("Alt");
    if (e.shiftKey) parts.push("Shift");

    // Ignore bare modifier key presses (Ctrl alone, Shift alone, etc)
    const isModifier = ["Control", "Alt", "Shift", "Meta"].includes(e.key);
    if (isModifier) return; // Wait for the actual key

    // Add the main key
    const mainKey = e.key.length === 1 ? e.key.toUpperCase() : e.key;
    parts.push(mainKey);

    // Must have at least one modifier + one key
    if (parts.length < 2) return;

    const combo = parts.join("+");
    const updated = { ...hotkeys, [action]: combo };
    setHotkeys(updated);
    saveHotkeys(updated);
    setRecording(false);
  };

  return (
    <div className="hotkey-row">
      <div
        ref={kbdRef}
        className={recording ? "hotkey-recording" : "hotkey-display"}
        onClick={startRecording}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        style={{ cursor: "pointer", outline: recording ? "2px solid var(--accent-gold)" : "none", display: "inline-block" }}
      >
        {recording ? "Press keys..." : currentKeys}
      </div>
      <span>{label}</span>
      {!recording && (
        <button className="btn btn-xs" onClick={startRecording} title="Rebind">✏️</button>
      )}
      {recording && (
        <button className="btn btn-xs" onClick={() => setRecording(false)}>✕ Cancel</button>
      )}
    </div>
  );
}

// ── Settings Tab ──────────────────────────────────────────────────────────

function SettingsTab() {
  const [token, setToken] = useState("");
  const [saved, setSaved] = useState(false);
  const [tokenVisible, setTokenVisible] = useState(false);
  const [tokenStatus, setTokenStatus] = useState<"none" | "checking" | "valid" | "invalid">("none");
  const [testData, setTestData] = useState<{valid?: boolean; username?: string; error?: string} | null>(null);

  const handleHotkey = (action: HotkeyAction) => {
    if (action === "scan") {
      fetch(`${API}/api/scan`, { method: "POST" }).catch(() => {});
    } else if (action === "economy") {
      fetch(`${API}/api/economy-refresh`, { method: "POST" }).catch(() => {});
    } else if (action === "dashboard") {
      // Focus the main window (no-op in settings, but the hotkey itself works globally)
    }
  };

  // Load existing token on mount
  useEffect(() => {
    fetch(`${API}/api/settings/token`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.token) setToken(data.token); })
      .catch(() => {});
  }, []);

  const saveToken = async () => {
    try {
      const res = await fetch(`${API}/api/settings/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.replace(/^"|"$/g, '') }), // strip surrounding quotes
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      } else {
        alert("Failed to save token - server returned error. Is the Python server running?");
      }
    } catch {
      alert("Failed to save token - can't reach server. Is the app running?");
    }
  };

  const testToken = async () => {
    setTokenStatus("checking");
    setTestData(null);
    try {
      const res = await fetch(`${API}/api/settings/token/test`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setTestData(data);
        setTokenStatus(data.valid ? "valid" : "invalid");
      } else {
        setTokenStatus("invalid");
      }
    } catch {
      setTokenStatus("invalid");
    }
  };

  const [loginStatus, setLoginStatus] = useState<"idle" | "copied" | "error">("idle");

  const copyTokenSnippet = async () => {
    // Copy a simple one-liner that shows the token and copies it
    const snippet = `copy(localStorage.getItem('pd2-token')||localStorage.getItem('pd2Token'))`;
    try {
      await navigator.clipboard.writeText(snippet);
      setLoginStatus("copied");
      setTimeout(() => setLoginStatus("idle"), 3000);
      // Open PD2 in browser
      openAuthPage();
    } catch {
      setLoginStatus("error");
    }
  };

  const openAuthPage = async () => {
    try {
      const { open } = await import('@tauri-apps/plugin-shell');
      await open('https://projectdiablo2.com');
    } catch {
      window.open('https://projectdiablo2.com', '_blank');
    }
  };

  return (
    <div className="settings-panel">
      <h2>Settings</h2>

      <div className="setting-section">
        <h3>🔑 PD2 Authentication</h3>
        <p className="hint">
          Required for: direct offer submission, incoming/outgoing offers, market search via API.
        </p>
        <div className="setting-actions" style={{ marginBottom: 12 }}>
          <button
            className="btn btn-gold"
            onClick={copyTokenSnippet}
          >
            {loginStatus === "copied" ? "✅ Snippet copied!" : "📋 Copy Token Extractor"}
          </button>
          {loginStatus === "error" && <span className="error-msg">Failed to copy - use manual method below</span>}
        </div>
        <details className="manual-token-section">
          <summary>Manual token entry</summary>
          <div className="token-row">
            <input
              type={tokenVisible ? "text" : "password"}
              placeholder="Paste your PD2 JWT token here..."
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="token-input"
            />
            <button className="btn btn-xs" onClick={() => setTokenVisible(!tokenVisible)} title={tokenVisible ? "Hide" : "Show"}>
              {tokenVisible ? "🙈" : "👁️"}
            </button>
            <button className="btn btn-secondary" onClick={openAuthPage}>
              Open PD2 ↗
            </button>
          </div>
          <div className="setting-actions">
            <button className="btn btn-gold" onClick={saveToken}>Save Token</button>
            <button className="btn btn-secondary" onClick={testToken} disabled={!token}>
              Test Connection
            </button>
            {saved && <span className="saved-msg">✅ Saved!</span>}
            {tokenStatus === "checking" && <span className="hint">Checking...</span>}
            {tokenStatus === "valid" && <span className="saved-msg">✅ Token valid!</span>}
            {tokenStatus === "valid" && testData?.username && <span className="hint">(logged in as {testData.username})</span>}
            {tokenStatus === "invalid" && <span className="error-msg">❌ Invalid token</span>}
          </div>
          <p className="hint" style={{ marginTop: 8 }}>
            <strong>Get your token:</strong><br />
            1. Click "📋 Copy Token Extractor" above (copies a snippet)<br />
            2. PD2 opens in your browser — log in<br />
            3. Press <strong>F12</strong> → <strong>Console</strong> tab<br />
            4. Press <strong>Ctrl+V</strong> then <strong>Enter</strong> — token is copied to clipboard<br />
            5. Come back here, paste into the box below, click "Save Token"
          </p>
        </details>
      </div>

      <div className="setting-section">
        <h3>⌨️ Hotkeys</h3>
        <p className="hint">Click a hotkey to rebind it. Press your desired key combo.</p>

        <div className="hotkey-list">
          <HotkeyRow action="scan" label="Start / Stop Scan" defaultKeys="Ctrl+Shift+S" onTrigger={handleHotkey} />
          <HotkeyRow action="economy" label="Refresh Economy" defaultKeys="Ctrl+Shift+E" onTrigger={handleHotkey} />
          <HotkeyRow action="dashboard" label="Show Dashboard" defaultKeys="Ctrl+Shift+D" onTrigger={handleHotkey} />
        </div>
        <button className="btn btn-secondary" style={{ marginTop: 10 }} onClick={() => { saveHotkeys({...DEFAULT_HOTKEYS}); window.location.reload(); }}>
          🔄 Reset to Defaults
        </button>
      </div>

      <div className="setting-section">
        <h3>i️ About</h3>
        <p>PD2 Market Sniper v0.1.0</p>
        <p className="hint">
          Price data from <a href="https://pd2trader.com" target="_blank" rel="noreferrer">PD2Trader</a>
        </p>
      </div>
    </div>
  );
}

// ── Deal Card ─────────────────────────────────────────────────────────────

function DealCardView({ deal, expanded, onExpand, offerAmount, onOfferChange, onPriceCheck }: {
  deal: DealCard; expanded: boolean; onExpand: () => void;
  offerAmount: string; onOfferChange: (val: string) => void;
  onPriceCheck: (name: string) => Promise<any>;
}) {
  const [priceCheck, setPriceCheck] = useState<any>(null);
  const doPriceCheck = async () => { setPriceCheck(await onPriceCheck(deal.item_name)); };
  const discountPct = deal.economy_value_hr && deal.economy_value_hr > 0
    ? Math.round((1 - deal.price_hr / deal.economy_value_hr) * 100) : null;

  return (
    <div className={`deal-card ${expanded ? "expanded" : ""}`} onClick={onExpand}>
      <div className="deal-header">
        <div className="deal-title">
          <span className="deal-score">{deal.score?.toFixed(1)}</span>
          <span className="deal-name">{deal.item_name}</span>
        </div>
        <div className="deal-price">
          <span className="price-hr">{deal.price_hr} HR</span>
          {discountPct !== null && discountPct > 0 && <span className="discount">-{discountPct}%</span>}
          {deal.economy_value_hr && <span className="econ-val">Econ: {deal.economy_value_hr} HR</span>}
        </div>
      </div>
      <div className="deal-meta">
        <span>👤 {deal.seller_name}</span>
        <span>🏷️ {deal.filter_name}</span>
      </div>
      {expanded && (
        <div className="deal-details">
          {deal.stats && deal.stats.length > 0 && (
            <div className="deal-stats">
              {deal.stats.map((s, i) => <div key={i} className="stat-line">{s}</div>)}
            </div>
          )}
          {deal.corruption && deal.corruption.length > 0 && (
            <div className="deal-corruption">
              {deal.corruption.map((c, i) => <span key={i} className="corruption-tag">{c}</span>)}
            </div>
          )}
          <div className="deal-actions">
            <a href={deal.listing_url} target="_blank" className="btn btn-link" rel="noreferrer">Open Listing ↗</a>
            <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); doPriceCheck(); }}>📊 Price Check</button>
          </div>
          {priceCheck && (
            <div className="price-check-result">
              <div>Median: {priceCheck.median_price} HR ({priceCheck.sample_count} listings)</div>
              <div>Confidence: {priceCheck.confidence}</div>
              {priceCheck.trend && <div>Trend: {priceCheck.trend}</div>}
              {priceCheck.discount_pct && <div>Discount: {priceCheck.discount_pct}%</div>}
            </div>
          )}
          <div className="offer-input-row">
            <input type="number" step="0.05" placeholder="Offer amount (HR)" value={offerAmount}
              onChange={(e) => onOfferChange(e.target.value)} onClick={(e) => e.stopPropagation()} />
            <button className="btn btn-gold" onClick={(e) => { e.stopPropagation(); alert(`Offer ${offerAmount} HR - send this through chat!`); }} disabled={!offerAmount}>
              Submit Offer
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
