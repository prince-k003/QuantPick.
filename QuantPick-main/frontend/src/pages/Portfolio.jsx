import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { api, fmt } from "../lib/apiClient";
import { Delta, Loading, Stat } from "../components/quant";
import { RotateCcw } from "lucide-react";
import { toast } from "sonner";

const COLORS = ["#3B82F6", "#10B981", "#8B5CF6", "#06B6D4", "#EAB308", "#F97316", "#EF4444", "#A1A1AA"];

export default function Portfolio() {
  const [p, setP] = useState(null);
  const nav = useNavigate();

  const load = () => api.portfolio().then(setP);
  useEffect(() => { load(); }, []);

  const reset = () => api.resetPortfolio().then(() => { toast.success("Book reset to ₹10L"); load(); });
  const sell = (sym, qty) => api.trade({ symbol: sym, side: "SELL", qty }).then((r) => { toast.success(`Sold ${qty} ${sym} @ ${fmt.inr(r.executed_price)}`); load(); }).catch((e) => toast.error(e.response?.data?.detail || "Failed"));

  if (!p) return <Loading label="Loading paper book" />;
  const alloc = [...p.holdings.map((h) => ({ name: h.symbol, value: h.market_value })), { name: "Cash", value: p.cash }];

  return (
    <div className="fade-up space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Paper Trading Book</h1>
          <p className="mono text-xs text-[var(--text-muted)] mt-1">Virtual capital {fmt.inr0(p.initial_capital)} · mark-to-market live</p>
        </div>
        <button onClick={reset} data-testid="reset-portfolio" className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--surface-hover)] mono text-xs px-3 py-2 transition-colors">
          <RotateCcw size={13} /> Reset Book
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-px">
        <Stat label="Total Value" value={fmt.inr0(p.total_value)} color="#3B82F6" />
        <Stat label="Cash" value={fmt.inr0(p.cash)} />
        <Stat label="Invested" value={fmt.inr0(p.invested)} />
        <Stat label="Unrealized P&L" value={fmt.inr0(p.unrealized_pnl)} sub={fmt.pct(p.unrealized_pnl_pct)} color={p.unrealized_pnl >= 0 ? "var(--buy)" : "var(--sell)"} />
        <Stat label="Total Return" value={fmt.pct(p.total_return_pct)} color={p.total_return_pct >= 0 ? "var(--buy)" : "var(--sell)"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-px">
        <div className="grid-cell p-4 lg:col-span-2 overflow-x-auto">
          <div className="overline mb-3">Holdings</div>
          {p.holdings.length === 0 ? (
            <div className="mono text-xs text-[var(--text-muted)] py-6">No positions. Add picks from Top Picks or a stock deep-dive.</div>
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="border-b border-[var(--border)] text-left">
                {["Symbol", "Qty", "Avg", "LTP", "Value", "Weight", "P&L", ""].map((h, i) => <th key={h} className={`overline py-2 px-2 ${i > 0 && i < 7 ? "text-right" : ""}`}>{h}</th>)}
              </tr></thead>
              <tbody>
                {p.holdings.map((h) => (
                  <tr key={h.symbol} className="border-b border-[var(--border)] tr-hover">
                    <td className="py-2 px-2 cursor-pointer" onClick={() => nav(`/stock/${h.symbol}`)}><span className="mono font-semibold hover:text-[#3B82F6]">{h.symbol}</span></td>
                    <td className="mono py-2 px-2 text-right">{h.qty}</td>
                    <td className="mono py-2 px-2 text-right">{fmt.inr(h.avg_price)}</td>
                    <td className="mono py-2 px-2 text-right">{fmt.inr(h.ltp)}</td>
                    <td className="mono py-2 px-2 text-right">{fmt.inr0(h.market_value)}</td>
                    <td className="mono py-2 px-2 text-right text-[var(--text-muted)]">{h.weight}%</td>
                    <td className="py-2 px-2 text-right"><Delta value={h.pnl_pct} /><div className="mono text-[10px] text-[var(--text-muted)]">{fmt.inr0(h.pnl)}</div></td>
                    <td className="py-2 px-2 text-right"><button onClick={() => sell(h.symbol, h.qty)} data-testid={`sell-all-${h.symbol}`} className="mono text-[10px] border border-[var(--sell)] text-[var(--sell)] px-2 py-0.5 hover:bg-[var(--sell)] hover:text-white transition-colors">EXIT</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="grid-cell p-4">
          <div className="overline mb-3">Allocation</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={alloc} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={1} stroke="#050505" isAnimationActive={false}>
                {alloc.map((e, i) => <Cell key={i} fill={e.name === "Cash" ? "#27272A" : COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #27272A", borderRadius: 0, fontFamily: "JetBrains Mono", fontSize: 11 }} formatter={(v) => fmt.inr0(v)} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1 mt-2">
            {alloc.slice(0, 6).map((a, i) => (
              <div key={a.name} className="flex items-center justify-between mono text-[10px]">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2" style={{ background: a.name === "Cash" ? "#27272A" : COLORS[i % COLORS.length] }} />{a.name}</span>
                <span className="text-[var(--text-muted)]">{((a.value / p.total_value) * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid-cell p-4">
        <div className="overline mb-3">Transaction Log</div>
        {p.transactions.length === 0 ? <div className="mono text-xs text-[var(--text-muted)]">No trades yet.</div> : (
          <table className="w-full text-sm">
            <tbody>
              {p.transactions.map((tx, i) => (
                <tr key={i} className="border-b border-[var(--border)]">
                  <td className="py-1.5 px-2"><span className="mono text-[10px] px-1.5 py-0.5" style={{ color: tx.side === "BUY" ? "var(--buy)" : "var(--sell)", background: tx.side === "BUY" ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)" }}>{tx.side}</span></td>
                  <td className="mono py-1.5 px-2 font-semibold">{tx.symbol}</td>
                  <td className="mono py-1.5 px-2 text-right text-[var(--text-secondary)]">{tx.qty} @ {fmt.inr(tx.price)}</td>
                  <td className="mono py-1.5 px-2 text-right">{fmt.inr0(tx.value)}</td>
                  <td className="mono py-1.5 px-2 text-right text-[10px] text-[var(--text-muted)]">{new Date(tx.time).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
