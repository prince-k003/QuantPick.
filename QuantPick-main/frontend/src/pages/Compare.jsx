import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { api, fmt } from "../lib/apiClient";
import { SignalBadge, ScoreBar, Loading } from "../components/quant";
import { X } from "lucide-react";

const COLORS = ["#3B82F6", "#10B981", "#8B5CF6", "#EAB308", "#EF4444"];
const METRICS = [
  ["composite", "Composite", (v) => v], ["fundamental_score", "Fundamental", (v) => v],
  ["technical_score", "Technical", (v) => v], ["factor_score", "Quant Factor", (v) => v],
  ["ml_score", "ML Score", (v) => v], ["sentiment_score", "Sentiment", (v) => v],
  ["piotroski", "Piotroski", (v) => v + "/9"], ["pe", "P/E", (v) => v],
  ["roe", "ROE %", (v) => v], ["de", "D/E", (v) => v], ["rsi", "RSI", (v) => v],
];

export default function Compare({ risk }) {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const nav = useNavigate();
  const symbols = (params.get("symbols") || "").split(",").filter(Boolean);

  useEffect(() => {
    if (symbols.length === 0) { setData({ items: [], chart: [] }); return; }
    setData(null);
    api.compare(symbols, risk).then(setData);
    /* eslint-disable-next-line */
  }, [params.get("symbols"), risk]);

  const remove = (sym) => setParams({ symbols: symbols.filter((s) => s !== sym).join(",") });

  if (!data) return <Loading label="Comparing" />;
  const items = data.items || [];

  return (
    <div className="fade-up space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Compare</h1>
        <p className="mono text-xs text-[var(--text-muted)] mt-1">Side-by-side scores & normalized price (base 100) · {risk} weights</p>
      </div>

      {items.length === 0 ? (
        <div className="panel p-8 mono text-xs text-[var(--text-muted)]">
          Add symbols to compare — pin stocks in your Watchlist and hit "Compare", or open a stock and use Compare.
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {items.map((r, i) => (
              <div key={r.symbol} className="flex items-center gap-2 border border-[var(--border)] px-2 py-1">
                <span className="w-2 h-2" style={{ background: COLORS[i % COLORS.length] }} />
                <span className="mono text-xs font-semibold">{r.symbol}</span>
                <button onClick={() => remove(r.symbol)} data-testid={`remove-${r.symbol}`}><X size={12} className="text-[var(--text-muted)] hover:text-white" /></button>
              </div>
            ))}
          </div>

          <div className="grid-cell p-4">
            <div className="overline mb-3">Normalized Price · 180d (base = 100)</div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data.chart} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid stroke="#27272A" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} tickFormatter={(v) => v.slice(2, 7)} minTickGap={50} />
                <YAxis tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} width={44} />
                <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #27272A", borderRadius: 0, fontFamily: "JetBrains Mono", fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 11, fontFamily: "JetBrains Mono" }} />
                {items.map((r, i) => (
                  <Line key={r.symbol} type="monotone" dataKey={r.symbol} stroke={COLORS[i % COLORS.length]} strokeWidth={1.6} dot={false} isAnimationActive={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="panel overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#0a0a0a]">
                <tr className="border-b border-[var(--border)]">
                  <th className="overline py-2.5 px-3 text-left">Metric</th>
                  {items.map((r) => (
                    <th key={r.symbol} className="overline py-2.5 px-3 text-right cursor-pointer hover:text-white" onClick={() => nav(`/stock/${r.symbol}`)}>{r.symbol}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[var(--border)]">
                  <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)]">Signal</td>
                  {items.map((r) => <td key={r.symbol} className="py-2.5 px-3 text-right"><SignalBadge signal={r.signal} /></td>)}
                </tr>
                {METRICS.map(([key, label, fmtFn]) => {
                  const vals = items.map((r) => r[key]).filter((v) => v != null);
                  const best = key === "pe" || key === "de" ? Math.min(...vals) : Math.max(...vals);
                  return (
                    <tr key={key} className="border-b border-[var(--border)] tr-hover">
                      <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)]">{label}</td>
                      {items.map((r) => (
                        <td key={r.symbol} className="mono py-2.5 px-3 text-right" style={{ color: r[key] === best ? "var(--buy)" : "#fff" }}>
                          {r[key] != null ? fmtFn(r[key]) : "—"}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
