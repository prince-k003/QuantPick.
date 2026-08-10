import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmt } from "../lib/apiClient";
import { SignalBadge, Loading } from "../components/quant";
import { Star, GitCompare } from "lucide-react";
import { toast } from "sonner";

export default function Watchlist({ risk }) {
  const [data, setData] = useState(null);
  const nav = useNavigate();

  const load = () => { setData(null); api.watchlist(risk).then(setData); };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [risk]);

  const unpin = (sym, e) => {
    e.stopPropagation();
    api.toggleWatch(sym).then(() => { toast.success(`Removed ${sym}`); load(); });
  };

  if (!data) return <Loading label="Loading watchlist" />;
  const items = data.items || [];

  return (
    <div className="fade-up space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Watchlist</h1>
          <p className="mono text-xs text-[var(--text-muted)] mt-1">{items.length} pinned equities · scored with {risk} weights</p>
        </div>
        {items.length >= 2 && (
          <button onClick={() => nav(`/compare?symbols=${items.slice(0, 5).map((i) => i.symbol).join(",")}`)}
            data-testid="compare-watchlist" className="flex items-center gap-1.5 bg-[#2563EB] hover:bg-[#1d4ed8] text-white mono text-xs px-3 py-2 transition-colors">
            <GitCompare size={13} /> Compare Top {Math.min(5, items.length)}
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="panel p-8 mono text-xs text-[var(--text-muted)]">
          No stocks pinned yet. Tap the <Star size={12} className="inline mx-1" /> star on any pick or deep-dive to add it here.
        </div>
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#0a0a0a]">
              <tr className="border-b border-[var(--border)] text-left">
                {["Symbol", "Sector", "LTP", "Target", "Composite", "ML", "Signal", ""].map((h, i) => (
                  <th key={h} className={`overline py-2.5 px-3 ${i > 1 && i < 7 ? "text-right" : ""}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.symbol} onClick={() => nav(`/stock/${r.symbol}`)} data-testid={`watch-row-${r.symbol}`} className="border-b border-[var(--border)] tr-hover cursor-pointer">
                  <td className="py-2.5 px-3"><span className="mono font-semibold">{r.symbol}</span><div className="text-[11px] text-[var(--text-muted)]">{r.name}</div></td>
                  <td className="py-2.5 px-3 text-xs text-[var(--text-secondary)]">{r.sector}</td>
                  <td className="mono py-2.5 px-3 text-right">{fmt.inr(r.price)}</td>
                  <td className="mono py-2.5 px-3 text-right">{fmt.inr(r.target)}</td>
                  <td className="mono py-2.5 px-3 text-right font-semibold">{r.composite}</td>
                  <td className="mono py-2.5 px-3 text-right" style={{ color: "#8B5CF6" }}>{r.ml_score ?? "—"}</td>
                  <td className="py-2.5 px-3 text-right"><SignalBadge signal={r.signal} /></td>
                  <td className="py-2.5 px-3 text-right">
                    <button onClick={(e) => unpin(r.symbol, e)} data-testid={`unpin-${r.symbol}`} title="Unpin">
                      <Star size={15} className="text-[var(--hold)] fill-[var(--hold)]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
