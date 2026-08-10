import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmt } from "../lib/apiClient";
import { SignalBadge, Loading } from "../components/quant";
import { Filter, RotateCcw } from "lucide-react";

const initial = { sector: "", exchange: "", max_pe: "", min_roe: "", max_de: "", signal: "" };

export default function Screener({ risk, meta }) {
  const [filters, setFilters] = useState(initial);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

  const run = () => {
    setLoading(true);
    const params = { risk };
    Object.entries(filters).forEach(([k, v]) => { if (v !== "") params[k] = v; });
    api.screener(params).then((d) => { setData(d); setLoading(false); });
  };

  useEffect(() => { run(); /* eslint-disable-next-line */ }, [risk]);

  const set = (k, v) => setFilters((f) => ({ ...f, [k]: v }));

  return (
    <div className="fade-up space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Fundamental & Signal Screener</h1>
        <p className="mono text-xs text-[var(--text-muted)] mt-1">Filter the universe by valuation, quality, leverage & engine signal</p>
      </div>

      <div className="panel p-4 grid grid-cols-2 md:grid-cols-7 gap-3 items-end">
        <Field label="Sector">
          <select value={filters.sector} onChange={(e) => set("sector", e.target.value)} data-testid="filter-sector" className="scr-in">
            <option value="">All</option>
            {meta?.sectors?.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Exchange">
          <select value={filters.exchange} onChange={(e) => set("exchange", e.target.value)} data-testid="filter-exchange" className="scr-in">
            <option value="">All</option><option value="NSE">NSE</option><option value="BSE">BSE</option>
          </select>
        </Field>
        <Field label="Max P/E">
          <input type="number" value={filters.max_pe} onChange={(e) => set("max_pe", e.target.value)} placeholder="e.g. 30" data-testid="filter-pe" className="scr-in" />
        </Field>
        <Field label="Min ROE %">
          <input type="number" value={filters.min_roe} onChange={(e) => set("min_roe", e.target.value)} placeholder="e.g. 15" data-testid="filter-roe" className="scr-in" />
        </Field>
        <Field label="Max D/E">
          <input type="number" value={filters.max_de} onChange={(e) => set("max_de", e.target.value)} placeholder="e.g. 1" data-testid="filter-de" className="scr-in" />
        </Field>
        <Field label="Signal">
          <select value={filters.signal} onChange={(e) => set("signal", e.target.value)} data-testid="filter-signal" className="scr-in">
            <option value="">All</option><option value="BUY">BUY</option><option value="HOLD">HOLD</option><option value="SELL">SELL</option>
          </select>
        </Field>
        <div className="flex gap-2">
          <button onClick={run} data-testid="run-screener" className="flex-1 bg-[#2563EB] hover:bg-[#1d4ed8] text-white mono text-xs py-2 flex items-center justify-center gap-1.5 transition-colors">
            <Filter size={13} /> Run
          </button>
          <button onClick={() => { setFilters(initial); setTimeout(run, 0); }} data-testid="reset-screener" className="border border-[var(--border)] hover:bg-[var(--surface-hover)] px-2 transition-colors">
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {loading ? <Loading label="Screening universe" /> : (
        <div className="panel overflow-x-auto">
          <div className="px-3 py-2 border-b border-[var(--border)] mono text-xs text-[var(--text-muted)]">
            {data.count} matches
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left">
                {["Symbol", "Sector", "LTP", "P/E", "ROE%", "D/E", "Piotroski", "RSI", "Composite", "Signal"].map((h, i) => (
                  <th key={h} className={`overline py-2.5 px-3 ${i > 1 ? "text-right" : ""}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.symbol} onClick={() => nav(`/stock/${r.symbol}`)} data-testid={`screener-row-${r.symbol}`} className="border-b border-[var(--border)] tr-hover cursor-pointer">
                  <td className="py-2.5 px-3"><span className="mono font-semibold">{r.symbol}</span><div className="text-[11px] text-[var(--text-muted)]">{r.name}</div></td>
                  <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)]">{r.sector}</td>
                  <td className="mono py-2.5 px-3 text-right">{fmt.inr(r.price)}</td>
                  <td className="mono py-2.5 px-3 text-right">{r.pe}</td>
                  <td className="mono py-2.5 px-3 text-right">{r.roe}</td>
                  <td className="mono py-2.5 px-3 text-right">{r.de}</td>
                  <td className="mono py-2.5 px-3 text-right" style={{ color: r.piotroski >= 7 ? "var(--buy)" : r.piotroski <= 3 ? "var(--sell)" : "var(--text)" }}>{r.piotroski}/9</td>
                  <td className="mono py-2.5 px-3 text-right" style={{ color: r.rsi > 70 ? "var(--sell)" : r.rsi < 35 ? "var(--hold)" : "var(--text)" }}>{r.rsi}</td>
                  <td className="mono py-2.5 px-3 text-right font-semibold">{r.composite}</td>
                  <td className="py-2.5 px-3 text-right"><SignalBadge signal={r.signal} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <style>{`.scr-in{width:100%;background:#0a0a0a;border:1px solid var(--border);padding:7px 8px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#fff;outline:none}.scr-in:focus{border-color:#3B82F6}`}</style>
    </div>
  );
}

const Field = ({ label, children }) => (
  <div><div className="overline mb-1.5">{label}</div>{children}</div>
);
