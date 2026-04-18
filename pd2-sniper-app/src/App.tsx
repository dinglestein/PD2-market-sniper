import { useState, useEffect, useCallback, useRef } from "react";
import "./App.css";

// Backend API base URL (Python server on port 8420)
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

export default function App() {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [deals, setDeals] = useState<DealCard[]>([]);
  const [economy, setEconomy] = useState<EconomyValue | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"deals" | "economy" | "offers">("deals");
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
          if (data.scan_running) {
            setLoading(true);
          }
          setServerStarting(false);
        }
      } catch {
        setStatus(null);
        attempts++;
        // Keep trying for up to 30 seconds (server might be starting)
        if (attempts > 30) setServerStarting(false);
      }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  const loadDeals = useCallback(async () => {
    try {
      await fetch(`${API}/api/refresh-dashboard`, { method: "POST" });
      const dataRes = await fetch(`${API}/assets/scan_results.json`);
      if (!dataRes.ok) {
        // Try alternate path
        const altRes = await fetch(`${API}/scan_results.json`);
        if (altRes.ok) {
          const data = await altRes.json();
          setDeals(data.deals || []);
          return;
        }
      } else {
        const data = await dataRes.json();
        setDeals(data.deals || []);
        return;
      }
      // Final fallback: try reading directly
      const dataRes2 = await fetch(`${API}/api/deals`);
      if (dataRes2.ok) {
        const data = await dataRes2.json();
        setDeals(data.deals || []);
      }
    } catch {
      // server not available
    }
  }, []);

  const loadEconomy = useCallback(async () => {
    try {
      // Try multiple paths to find economy data
      const paths = [
        `${API}/assets/all_economy.json`,
        `${API}/all_economy.json`,
      ];
      for (const url of paths) {
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          if (data.values && Object.keys(data.values).length > 0) {
            setEconomy(data);
            return;
          }
        }
      }
    } catch {
      // server not available
    }
  }, []);

  useEffect(() => {
    if (status) {
      loadDeals();
      loadEconomy();
    }
  }, [status, loadDeals, loadEconomy]);

  // Cleanup scan poll on unmount
  useEffect(() => {
    return () => {
      if (scanPollRef.current) clearInterval(scanPollRef.current);
    };
  }, []);

  const handleScan = async () => {
    if (loading) {
      // Stop the scan
      try {
        await fetch(`${API}/api/scan-stop`, { method: "POST" });
        setLoading(false);
        if (scanPollRef.current) {
          clearInterval(scanPollRef.current);
          scanPollRef.current = null;
        }
      } catch {
        // ignore
      }
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/scan`, { method: "POST" });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error || "Scan failed");
        setLoading(false);
        return;
      }
      // Poll until scan completes
      scanPollRef.current = setInterval(async () => {
        try {
          const s = await (await fetch(`${API}/api/status`)).json();
          if (!s.scan_running) {
            if (scanPollRef.current) clearInterval(scanPollRef.current);
            scanPollRef.current = null;
            setLoading(false);
            await loadDeals();
          }
        } catch {
          // server might restart
        }
      }, 3000);
    } catch (exc: any) {
      setError(exc.message);
      setLoading(false);
    }
  };

  const handleEconomyRefresh = async () => {
    try {
      await fetch(`${API}/api/economy-refresh`, { method: "POST" });
      // Poll for economy data to refresh
      let attempts = 0;
      const checkEcon = setInterval(async () => {
        attempts++;
        await loadEconomy();
        if (economy && economy.refreshed_at || attempts > 20) {
          clearInterval(checkEcon);
        }
      }, 2000);
    } catch {
      // ignore
    }
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
    } catch {
      // ignore
    }
    return null;
  };

  // Filter deals by search
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

  // Sort economy values by price descending
  const econEntries = economy
    ? Object.entries(economy.values).sort(([, a], [, b]) => (b as number) - (a as number))
    : [];

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <h1 className="logo">🎯 PD2 Market Sniper</h1>
          <span className={`status-dot ${status ? "online" : serverStarting ? "starting" : "offline"}`} />
          <span className="status-text">
            {serverStarting ? "Starting Server..." : status ? "Server Online" : "Server Offline"}
          </span>
        </div>
        <div className="header-actions">
          <button
            className={`btn ${loading ? "btn-stop" : "btn-gold"}`}
            onClick={handleScan}
            disabled={!status && !loading}
          >
            {loading ? (
              <><span className="spinner-red" /> ⏹ Stop Scan</>
            ) : (
              "🔍 Scan Now"
            )}
          </button>
          <button className="btn btn-secondary" onClick={handleEconomyRefresh} disabled={!status}>
            🔄 Economy
          </button>
          <button className="btn btn-danger" onClick={handleReset}>
            🗑️
          </button>
        </div>
      </header>

      {/* Error bar */}
      {error && (
        <div className="error-bar">
          {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Tab bar */}
      <nav className="tabs">
        <button className={`tab ${activeTab === "deals" && "active"}`} onClick={() => setActiveTab("deals")}>
          Deals {deals.length > 0 && <span className="badge">{deals.length}</span>}
        </button>
        <button className={`tab ${activeTab === "economy" && "active"}`} onClick={() => setActiveTab("economy")}>
          Economy {economy && <span className="badge">{Object.keys(economy.values).length}</span>}
        </button>
        <button className={`tab ${activeTab === "offers" && "active"}`} onClick={() => setActiveTab("offers")}>
          Offers
        </button>
      </nav>

      {/* Content */}
      <main className="content">
        {!status && !serverStarting && (
          <div className="empty-state">
            <div className="empty-icon">🔌</div>
            <p>Server Offline</p>
            <p className="hint">Start the Python server with: python scripts/sniper.py serve</p>
          </div>
        )}

        {serverStarting && !status && (
          <div className="empty-state">
            <div className="empty-icon">⏳</div>
            <p>Starting Python backend...</p>
            <p className="hint">This may take a few seconds</p>
          </div>
        )}

        {status && activeTab === "deals" && (
          <>
            <div className="search-bar">
              <input
                type="text"
                placeholder="Search deals by name, seller, stat..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              {search && <span className="result-count">{filteredDeals.length} results</span>}
            </div>

            {filteredDeals.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">🎯</div>
                <p>No deals found yet</p>
                <p className="hint">Click "Scan Now" to search the market</p>
              </div>
            ) : (
              <div className="deal-grid">
                {filteredDeals.map((deal, i) => (
                  <DealCardView
                    key={i}
                    deal={deal}
                    expanded={selectedDeal === i}
                    onExpand={() => setSelectedDeal(selectedDeal === i ? null : i)}
                    offerAmount={offerAmounts[i] || ""}
                    onOfferChange={(val) => setOfferAmounts({ ...offerAmounts, [i]: val })}
                    onPriceCheck={handlePriceCheck}
                  />
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
                <span className="refreshed">
                  Last refreshed: {new Date(economy.refreshed_at).toLocaleString()}
                </span>
              )}
            </div>
            {!economy || econEntries.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📊</div>
                <p>No economy data loaded</p>
                <p className="hint">Click "🔄 Economy" in the header to fetch prices</p>
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

        {status && activeTab === "offers" && (
          <div className="offers-panel">
            <p className="hint">Offer tracking will show incoming/outgoing offers when PD2 auth is configured.</p>
            <p className="hint">Save your PD2 token in <code>.pd2_token</code> to enable REST API offer management.</p>
          </div>
        )}
      </main>
    </div>
  );
}

// Deal card component
function DealCardView({
  deal,
  expanded,
  onExpand,
  offerAmount,
  onOfferChange,
  onPriceCheck,
}: {
  deal: DealCard;
  expanded: boolean;
  onExpand: () => void;
  offerAmount: string;
  onOfferChange: (val: string) => void;
  onPriceCheck: (name: string) => Promise<any>;
}) {
  const [priceCheck, setPriceCheck] = useState<any>(null);

  const doPriceCheck = async () => {
    const result = await onPriceCheck(deal.item_name);
    setPriceCheck(result);
  };

  const discountPct = deal.economy_value_hr && deal.economy_value_hr > 0
    ? Math.round((1 - deal.price_hr / deal.economy_value_hr) * 100)
    : null;

  return (
    <div className={`deal-card ${expanded ? "expanded" : ""}`} onClick={onExpand}>
      <div className="deal-header">
        <div className="deal-title">
          <span className="deal-score">{deal.score?.toFixed(1)}</span>
          <span className="deal-name">{deal.item_name}</span>
        </div>
        <div className="deal-price">
          <span className="price-hr">{deal.price_hr} HR</span>
          {discountPct !== null && discountPct > 0 && (
            <span className="discount">-{discountPct}%</span>
          )}
          {deal.economy_value_hr && (
            <span className="econ-val">Econ: {deal.economy_value_hr} HR</span>
          )}
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
              {deal.stats.map((s, i) => (
                <div key={i} className="stat-line">{s}</div>
              ))}
            </div>
          )}
          {deal.corruption && deal.corruption.length > 0 && (
            <div className="deal-corruption">
              {deal.corruption.map((c, i) => (
                <span key={i} className="corruption-tag">{c}</span>
              ))}
            </div>
          )}
          <div className="deal-actions">
            <a href={deal.listing_url} target="_blank" className="btn btn-link" rel="noreferrer">
              Open Listing ↗
            </a>
            <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); doPriceCheck(); }}>
              📊 Price Check
            </button>
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
            <input
              type="number"
              step="0.05"
              placeholder="Offer amount (HR)"
              value={offerAmount}
              onChange={(e) => onOfferChange(e.target.value)}
              onClick={(e) => e.stopPropagation()}
            />
            <button
              className="btn btn-gold"
              onClick={(e) => {
                e.stopPropagation();
                alert(`Offer ${offerAmount} HR — send this through chat and I'll submit it!`);
              }}
              disabled={!offerAmount}
            >
              Submit Offer
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
