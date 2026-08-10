import React, { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, Filter, Wallet, LineChart, Bell, Settings as SettingsIcon, Activity, Star, GitCompare, RefreshCw, Grid3x3, TrendingUp, Search } from "lucide-react";
import { api } from "../lib/apiClient";
import { toast } from "sonner";

const NAV = [
  { to: "/", label: "Top Picks", icon: LayoutDashboard, end: true },
  { to: "/screener", label: "Screener", icon: Filter },
  { to: "/heatmap", label: "Sector Heatmap", icon: Grid3x3 },
  { to: "/watchlist", label: "Watchlist", icon: Star },
  { to: "/compare", label: "Compare", icon: GitCompare },
  { to: "/portfolio", label: "Paper Book", icon: Wallet },
  { to: "/backtest", label: "Backtest", icon: LineChart },
  { to: "/performance", label: "Performance", icon: TrendingUp },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

const RISKS = ["conservative", "balanced", "aggressive"];

export default function Layout({ children, risk, setRisk, meta, dataStatus, reloadStatus }) {
  const navigate = useNavigate();
  const [refreshing, setRefreshing] = useState(false);
  const ds = dataStatus?.data || {};
  const live = ds.source && ds.source !== "seeded";

  const doRefresh = () => {
    setRefreshing(true);
    api.refresh().then(() => {
      toast.success("Data refresh started — updates in ~30s");
      setTimeout(() => { reloadStatus && reloadStatus(); setRefreshing(false); }, 30000);
    }).catch(() => { toast.error("Refresh failed"); setRefreshing(false); });
  };

  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const onSearch = (val) => {
    setQ(val); setOpen(true);
    if (val.trim().length < 1) { setResults([]); return; }
    api.search(val).then((r) => setResults(r.results || [])).catch(() => {});
  };
  const pick = (r) => {
    setOpen(false); setQ("");
    navigate(`/stock/${r.symbol}`);
  };
  return (
    <div className="min-h-screen flex bg-[var(--bg)]">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-[var(--border)] bg-[#050505] flex flex-col fixed h-screen">
        <div className="p-4 border-b border-[var(--border)] flex items-center gap-2">
          <div className="w-7 h-7 bg-[#2563EB] flex items-center justify-center">
            <Activity size={16} strokeWidth={2} color="#fff" />
          </div>
          <div>
            <div className="font-head font-800 text-sm tracking-tight leading-none" style={{ fontWeight: 800 }}>QuantPick</div>
            <div className="overline mt-0.5">NSE · BSE ALPHA ENGINE</div>
          </div>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-testid={`nav-${n.label.toLowerCase().replace(/\s/g, "-")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 text-sm transition-colors duration-75 border-l-2 ${
                  isActive
                    ? "text-white bg-[var(--surface-hover)] border-[#2563EB]"
                    : "text-[var(--text-secondary)] border-transparent hover:text-white hover:bg-[var(--surface)]"
                }`
              }
            >
              <n.icon size={15} strokeWidth={1.5} />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-[var(--border)]">
          <div className="overline mb-2">Universe</div>
          <div className="mono text-xs text-[var(--text-secondary)]">
            {meta ? `${meta.universe_size} equities` : "…"}
          </div>
          <div className="mono text-[10px] text-[var(--text-muted)] mt-1">
            {meta ? `${meta.sectors.length} sectors` : ""}
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 ml-56 flex flex-col">
        <header className="h-14 border-b border-[var(--border)] bg-[#050505] flex items-center justify-between px-6 sticky top-0 z-20">
          <div className="flex items-center gap-4">
            <div className="relative w-72">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input value={q} onChange={(e) => onSearch(e.target.value)} onFocus={() => setOpen(true)}
                onBlur={() => setTimeout(() => setOpen(false), 200)}
                data-testid="global-search" placeholder="Search all NSE + BSE stocks…"
                className="w-full bg-[#0a0a0a] border border-[var(--border)] mono text-xs pl-8 pr-2 py-1.5 outline-none focus:border-[#3B82F6]" />
              {open && results.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-[#0a0a0a] border border-[var(--border)] max-h-80 overflow-y-auto z-50">
                  {results.map((r) => (
                    <button key={r.tradingsymbol + r.exchange} onMouseDown={() => pick(r)} data-testid={`search-result-${r.symbol}`}
                      className="w-full text-left px-3 py-2 hover:bg-[var(--surface-hover)] flex items-center justify-between border-b border-[var(--border)]">
                      <div><span className="mono text-xs font-semibold">{r.symbol}</span><div className="text-[10px] text-[var(--text-muted)] truncate max-w-[180px]">{r.name}</div></div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] mono px-1 border border-[var(--border)] text-[var(--text-muted)]">{r.exchange}</span>
                        {r.in_universe && <span className="text-[9px] mono text-[var(--buy)]">SCORED</span>}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 text-[var(--text-muted)]">
              <span className="w-1.5 h-1.5 rounded-full live-dot" style={{ background: live ? "var(--buy)" : "var(--hold)" }} />
              <span className="mono text-xs" data-testid="data-source-indicator">
                {live ? `LIVE · ${(ds.source || "").includes("angel") ? "Angel+yf" : "yfinance"} ${ds.live_count || 0}/${ds.total || 0}` : "SEEDED DATA"}
                {dataStatus?.ml_trained ? " · ML ON" : ""}
              </span>
            </div>
            <button onClick={doRefresh} disabled={refreshing} data-testid="refresh-data-btn"
              className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--surface)] mono text-[11px] px-2 py-1 transition-colors disabled:opacity-50">
              <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} /> {refreshing ? "Refreshing" : "Refresh"}
            </button>
          </div>
          <div className="flex items-center gap-3">
            <span className="overline">Risk Profile</span>
            <div className="flex border border-[var(--border)]">
              {RISKS.map((r) => (
                <button
                  key={r}
                  onClick={() => setRisk(r)}
                  data-testid={`risk-${r}`}
                  className={`px-3 py-1.5 mono text-xs capitalize transition-colors duration-75 ${
                    risk === r ? "bg-[#2563EB] text-white" : "text-[var(--text-secondary)] hover:bg-[var(--surface)]"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        </header>
        <main className="flex-1 p-6 max-w-[1920px] w-full">{children}</main>
      </div>
    </div>
  );
}
