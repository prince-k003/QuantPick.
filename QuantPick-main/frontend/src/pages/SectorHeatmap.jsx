import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/apiClient";
import { Loading } from "../components/quant";

const heat = (v) => {
  // 45..70 → red..green
  const t = Math.max(0, Math.min(1, (v - 45) / 25));
  const r = Math.round(239 - t * (239 - 16));
  const g = Math.round(68 + t * (185 - 68));
  const b = Math.round(68 + t * (129 - 68));
  return `rgb(${r},${g},${b})`;
};

export default function SectorHeatmap({ risk }) {
  const [data, setData] = useState(null);
  const nav = useNavigate();
  useEffect(() => { setData(null); api.sectorHeatmap(risk).then((d) => setData(d.sectors)); }, [risk]);
  if (!data) return <Loading label="Aggregating sector signals" />;

  const max = Math.max(...data.map((s) => s.count));
  return (
    <div className="fade-up space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Sector Heatmap</h1>
        <p className="mono text-xs text-[var(--text-muted)] mt-1">Where the engine is most bullish today · avg composite by sector · {risk} weights</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {data.map((s) => (
          <button key={s.sector} onClick={() => nav(`/screener`)} data-testid={`heat-${s.sector}`}
            className="text-left p-4 border border-[var(--border)] hover:brightness-110 transition-all relative overflow-hidden group"
            style={{ background: `linear-gradient(135deg, ${heat(s.avg_composite)}22, ${heat(s.avg_composite)}08)` }}>
            <div className="absolute top-0 left-0 h-1 transition-all" style={{ width: `${(s.count / max) * 100}%`, background: heat(s.avg_composite) }} />
            <div className="flex items-center justify-between">
              <span className="font-head font-semibold text-sm">{s.sector}</span>
              <span className="mono text-2xl font-bold" style={{ color: heat(s.avg_composite) }}>{s.avg_composite}</span>
            </div>
            <div className="mono text-[10px] text-[var(--text-muted)] mt-2 flex justify-between">
              <span>{s.count} stocks</span>
              <span style={{ color: s.buy_pct >= 50 ? "var(--buy)" : "var(--text-muted)" }}>{s.buy_pct}% BUY</span>
            </div>
          </button>
        ))}
      </div>

      <div className="panel p-4">
        <div className="overline mb-2">Scale</div>
        <div className="flex items-center gap-3">
          <span className="mono text-xs text-[var(--text-muted)]">Avoid</span>
          <div className="flex-1 h-3" style={{ background: "linear-gradient(90deg, rgb(239,68,68), rgb(234,179,8), rgb(16,185,129))" }} />
          <span className="mono text-xs text-[var(--text-muted)]">Strong Buy</span>
        </div>
      </div>
    </div>
  );
}
