import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmt } from "../lib/apiClient";
import { Delta, Loading, Stat } from "../components/quant";
import { TrendingUp } from "lucide-react";

export default function Performance() {
  const [data, setData] = useState(null);
  const nav = useNavigate();
  useEffect(() => { api.performance().then(setData); }, []);
  if (!data) return <Loading label="Loading performance" />;

  return (
    <div className="fade-up space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Performance Tracker</h1>
        <p className="mono text-xs text-[var(--text-muted)] mt-1">Forward returns of published BUY picks, marked to latest price</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-px">
        <Stat label="Tracking Since" value={`${data.tracking_days} day${data.tracking_days === 1 ? "" : "s"}`} sub="daily snapshots" color="#3B82F6" />
        <Stat label="Win Rate" value={data.win_rate != null ? data.win_rate + "%" : "—"} sub={`${data.buy_count || 0} BUY picks`} color={data.win_rate >= 50 ? "var(--buy)" : "var(--hold)"} />
        <Stat label="Records" value={data.records.length} sub="pick observations" />
      </div>

      <div className="panel p-3 mono text-[11px] text-[var(--hold)] border-l-2 border-[var(--hold)]">
        ℹ {data.note}
      </div>

      {data.records.length > 0 && (
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#0a0a0a]">
              <tr className="border-b border-[var(--border)] text-left">
                {["Date", "Symbol", "Signal", "Entry", "Current", "Return"].map((h, i) => (
                  <th key={h} className={`overline py-2.5 px-3 ${i > 2 ? "text-right" : ""}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.records.map((r, i) => (
                <tr key={i} onClick={() => nav(`/stock/${r.symbol}`)} className="border-b border-[var(--border)] tr-hover cursor-pointer">
                  <td className="mono py-2.5 px-3 text-[var(--text-muted)] text-xs">{r.date}</td>
                  <td className="mono py-2.5 px-3 font-semibold">{r.symbol}</td>
                  <td className="py-2.5 px-3"><span className="mono text-[10px]" style={{ color: r.signal === "BUY" ? "var(--buy)" : r.signal === "SELL" ? "var(--sell)" : "var(--hold)" }}>{r.signal}</span></td>
                  <td className="mono py-2.5 px-3 text-right">{fmt.inr(r.entry)}</td>
                  <td className="mono py-2.5 px-3 text-right">{fmt.inr(r.current)}</td>
                  <td className="py-2.5 px-3 text-right"><Delta value={r.return_pct} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
