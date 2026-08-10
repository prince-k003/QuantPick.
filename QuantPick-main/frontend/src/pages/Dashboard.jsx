import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmt } from "../lib/apiClient";
import { SignalBadge, Delta, Loading, Stat } from "../components/quant";
import { ArrowUpRight, Star } from "lucide-react";
import { toast } from "sonner";

export default function Dashboard({ risk }) {
  const [data, setData] = useState(null);
  const [pinned, setPinned] = useState([]);
  const nav = useNavigate();

  useEffect(() => {
    setData(null);
    api.picks(risk, 100).then(setData).catch(() => setData({ picks: [] }));
    api.watchlist(risk).then((w) => setPinned(w.symbols || [])).catch(() => {});
  }, [risk]);

  const togglePin = (sym, e) => {
    e.stopPropagation();
    api.toggleWatch(sym).then((r) => {
      setPinned(r.symbols);
      toast.success(r.pinned ? `Pinned ${sym}` : `Unpinned ${sym}`);
    });
  };

  if (!data) return <Loading />;
  const picks = data.picks || [];
  const buys = picks.filter((p) => p.signal === "BUY");
  const avg = picks.length ? picks.reduce((a, p) => a + p.composite, 0) / picks.length : 0;
  const top = picks[0];

  return (
    <div className="fade-up space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Top Picks</h1>
          <p className="mono text-xs text-[var(--text-muted)] mt-1">
            Composite = f(Fundamental, Technical, Multi-Factor, ML, Sentiment) · {risk} weights · {picks.length} ranked
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-px">
        <Stat label="BUY Signals" value={buys.length} sub={`of ${picks.length} scanned`} color="var(--buy)" />
        <Stat label="Avg Composite" value={avg.toFixed(1)} sub="cross-sectional" />
        <Stat label="Top Ranked" value={top?.symbol || "—"} sub={top ? `score ${top.composite}` : ""} color="#3B82F6" />
        <Stat label="Engine" value="Hybrid + ML" sub="XGBoost + factors" color="#8B5CF6" />
      </div>

      <div className="panel overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#0a0a0a]">
            <tr className="border-b border-[var(--border)] text-left">
              {["", "#", "Symbol", "Sector", "LTP", "Target", "Fund", "Tech", "Factor", "ML", "Sent", "Composite", "Signal"].map((h, i) => (
                <th key={i} className={`overline py-2.5 px-3 ${i > 3 ? "text-right" : ""}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {picks.map((p) => (
              <tr
                key={p.symbol}
                onClick={() => nav(`/stock/${p.symbol}`)}
                data-testid={`pick-row-${p.symbol}`}
                className="border-b border-[var(--border)] tr-hover cursor-pointer group"
              >
                <td className="py-2.5 px-3">
                  <button onClick={(e) => togglePin(p.symbol, e)} data-testid={`pin-${p.symbol}`}>
                    <Star size={14} className={pinned.includes(p.symbol) ? "text-[var(--hold)] fill-[var(--hold)]" : "text-[var(--text-muted)] hover:text-[var(--hold)]"} />
                  </button>
                </td>
                <td className="mono py-2.5 px-3 text-[var(--text-muted)]">{p.rank}</td>
                <td className="py-2.5 px-3">
                  <div className="flex items-center gap-2">
                    <span className="mono font-semibold group-hover:text-[#3B82F6]">{p.symbol}</span>
                    <span className="text-[9px] mono px-1 border border-[var(--border)] text-[var(--text-muted)]">{p.exchange}</span>
                    <ArrowUpRight size={12} className="opacity-0 group-hover:opacity-100 text-[#3B82F6]" />
                  </div>
                  <div className="text-[11px] text-[var(--text-muted)] truncate max-w-[180px]">{p.name}</div>
                </td>
                <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)]">{p.sector}</td>
                <td className="mono py-2.5 px-3 text-right">{fmt.inr(p.price)}</td>
                <td className="mono py-2.5 px-3 text-right">
                  {fmt.inr(p.target)}
                  <div className="text-[10px]"><Delta value={(p.target / p.price - 1) * 100} /></div>
                </td>
                <ScoreCell v={p.fundamental_score} c="#10B981" />
                <ScoreCell v={p.technical_score} c="#3B82F6" />
                <ScoreCell v={p.factor_score} c="#8B5CF6" />
                <ScoreCell v={p.ml_score ?? 50} c="#F97316" />
                <ScoreCell v={p.sentiment_score} c="#06B6D4" />
                <td className="mono py-2.5 px-3 text-right font-semibold text-base">{p.composite}</td>
                <td className="py-2.5 px-3 text-right"><SignalBadge signal={p.signal} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const ScoreCell = ({ v, c }) => (
  <td className="py-2.5 px-3 text-right">
    <span className="mono text-xs">{Number(v).toFixed(0)}</span>
    <div className="h-1 w-12 ml-auto mt-1 bg-[#0a0a0a]">
      <div className="h-full" style={{ width: `${Math.min(100, v)}%`, background: c }} />
    </div>
  </td>
);
