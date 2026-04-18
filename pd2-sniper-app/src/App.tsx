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

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1 className="logo">🎯 PD2 Market Sniper</h1>
          <span className={`status-dot ${status ? "online" : serverStarting ? "starting" : "offline"}`} />
          <span className="status-text">
            {serverStarting ? "Starting Server..." : status ? "Server Online" : "Server Offline"}
          </span>
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

// ── Settings Tab ──────────────────────────────────────────────────────────

function SettingsTab() {
  const [token, setToken] = useState("");
  const [saved, setSaved] = useState(false);
  const [tokenStatus, setTokenStatus] = useState<"none" | "checking" | "valid" | "invalid">("none");

  // Load existing token on mount
  useEffect(() => {
    fetch(`${API}/api/settings/token`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.token) setToken(data.token); })
      .catch(() => {});
  }, []);

  const saveToken = async () => {
    try {
      await fetch(`${API}/api/settings/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch { /* */ }
  };

  const testToken = async () => {
    setTokenStatus("checking");
    try {
      const res = await fetch(`${API}/api/settings/token/test`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setTokenStatus(data.valid ? "valid" : "invalid");
      } else {
        setTokenStatus("invalid");
      }
    } catch {
      setTokenStatus("invalid");
    }
  };

  const [loginStatus, setLoginStatus] = useState<"idle" | "logging-in" | "success" | "error">("idle");

  const autoLogin = async () => {
    setLoginStatus("logging-in");
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const result = await invoke<string>('open_pd2_login');
      if (result) {
        setToken(result);
        // Auto-save
        await fetch(`${API}/api/settings/token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: result }),
        });
        setSaved(true);
        setLoginStatus("success");
        setTimeout(() => { setSaved(false); setLoginStatus("idle"); }, 3000);
      } else {
        setLoginStatus("error");
      }
    } catch (e) {
      // Not running in Tauri or failed — fall back to manual
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
            onClick={autoLogin}
            disabled={loginStatus === "logging-in"}
          >
            {loginStatus === "logging-in" ? "⏳ Waiting for login..." : "🔐 Auto-Login to PD2"}
          </button>
          {loginStatus === "success" && <span className="saved-msg">✅ Token captured & saved!</span>}
          {loginStatus === "error" && <span className="hint">Auto-login unavailable — use manual method below</span>}
        </div>
        <details className="manual-token-section">
          <summary>Manual token entry</summary>
          <div className="token-row">
            <input
              type="password"
              placeholder="Paste your PD2 JWT token here..."
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="token-input"
            />
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
            {tokenStatus === "invalid" && <span className="error-msg">❌ Invalid token</span>}
          </div>
          <p className="hint" style={{ marginTop: 8 }}>
            How to get your token manually:<br />
            1. Click "Open PD2" above<br />
            2. Log in to your PD2 account<br />
            3. Press F12 → Console tab<br />
            4. Type: <code>localStorage.getItem('pd2-token')</code><br />
            5. Copy the token value and paste above
          </p>
        </details>
      </div>

      <div className="setting-section">
        <h3>⌨️ Hotkeys</h3>
        <p className="hint">Keyboard shortcuts (coming in future update)</p>
        <div className="hotkey-list">
          <div className="hotkey-row">
            <kbd>Ctrl+Shift+S</kbd>
            <span>Start / Stop Scan</span>
          </div>
          <div className="hotkey-row">
            <kbd>Ctrl+Shift+E</kbd>
            <span>Refresh Economy</span>
          </div>
          <div className="hotkey-row">
            <kbd>Ctrl+Shift+D</kbd>
            <span>Show Dashboard</span>
          </div>
        </div>
      </div>

      <div className="setting-section">
        <h3>ℹ️ About</h3>
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
            <button className="btn btn-gold" onClick={(e) => { e.stopPropagation(); alert(`Offer ${offerAmount} HR — send this through chat!`); }} disabled={!offerAmount}>
              Submit Offer
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
