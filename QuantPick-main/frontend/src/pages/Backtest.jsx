import React, { useEffect, useState } from "react";
import { ComposedChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { api, fmt } from "../lib/apiClient";
import { Delta, Loading, Stat } from "../components/quant";
import { Play } from "lucide-react";

export default function Backtest({ risk }) {
  const [topN, setTopN] = useState(10);
  const [data, setData] = useState(null);
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  const run = () => { setLoading(true); api.backtest(risk, topN).then((d) => { setData(d); setLoading(false); }); };
  useEffect(() => { run(); api.infoMetrics(risk).then(setInfo).catch(() => {}); /* eslint-disable-next-line */ }, [risk]);

  return (
    <div className="fade-up space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Backtest — Top-N Composite Strategy</h1>
          <p className="mono text-xs text-[var(--text-muted)] mt-1">Equal-weight top-N by composite score vs equal-weight market proxy · {risk} weights</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <div className="overline mb-1">Top N</div>
            <input type="number" min="3" max="30" value={topN} onChange={(e) => setTopN(Number(e.target.value))} data-testid="backtest-topn"
              className="w-20 bg-[#0a0a0a] border border-[var(--border)] mono text-sm px-2 py-2 outline-none focus:border-[#3B82F6]" />
          </div>
          <button onClick={run} data-testid="run-backtest" className="bg-[#2563EB] hover:bg-[#1d4ed8] text-white mono text-xs px-4 py-2.5 flex items-center gap-1.5 transition-colors">
            <Play size={13} /> Run
          </button>
        </div>
      </div>

      {loading || !data ? <Loading label="Simulating strategy" /> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-px">
            <Stat label="CAGR" value={fmt.pct(data.metrics.cagr)} color={data.metrics.cagr >= 0 ? "var(--buy)" : "var(--sell)"} />
            <Stat label="Alpha vs Mkt" value={fmt.pct(data.metrics.alpha)} sub={`Nifty proxy ${data.metrics.benchmark_cagr}%`} color={data.metrics.alpha >= 0 ? "var(--buy)" : "var(--sell)"} />
            <Stat label="Sharpe" value={data.metrics.sharpe} color="#3B82F6" />
            <Stat label="Sortino" value={data.metrics.sortino} color="#8B5CF6" />
            <Stat label="Max DD" value={fmt.pct(data.metrics.max_drawdown)} color="var(--sell)" />
            <Stat label="Win Rate" value={data.metrics.win_rate + "%"} />
            <Stat label="Final Value" value={fmt.compact(data.metrics.final_value)} sub={fmt.pct(data.metrics.total_return)} color="var(--buy)" />
          </div>

          {info && (
            <div className="grid-cell p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="overline">Signal Quality · Information Coefficient</span>
                <span className="mono text-[10px] px-2 py-0.5 border" style={{ color: info.grade === "Weak" ? "var(--hold)" : "var(--buy)", borderColor: "var(--border)" }}>{info.grade}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-px">
                <MiniM label="IC (rolling)" value={info.ic} hint="corr(pred, realized)" color={info.ic > 0.05 ? "var(--buy)" : "var(--hold)"} />
                <MiniM label="IC (current)" value={info.ic_current} hint="latest cross-section" />
                <MiniM label="Info Ratio" value={info.ir} hint="IC×√breadth" color={info.ir > 0.5 ? "var(--buy)" : "var(--text)"} />
                <MiniM label="Breadth" value={info.breadth} hint="bets / year" />
              </div>
              <div className="mono text-[10px] text-[var(--text-muted)] mt-3 bg-[#0a0a0a] border border-[var(--border)] p-2">
                IC = Spearman corr(predicted, realized return) · IR = IC × √(bets/yr) · IC&gt;0.05 good, &gt;0.10 excellent, &gt;0.15 hedge-fund grade
              </div>
            </div>
          )}

          <div className="grid-cell p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="overline">Equity Curve · {data.years}y · ₹10L start</div>
              <div className="mono text-[10px] text-[var(--text-muted)]">Sharpe = (Rp − Rf)/σp · Rf=6.8%</div>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={data.curve} margin={{ top: 4, right: 6, left: 6, bottom: 0 }}>
                <defs>
                  <linearGradient id="strat" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#27272A" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} tickFormatter={(v) => v.slice(0, 7)} minTickGap={50} />
                <YAxis tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} tickFormatter={(v) => (v / 1e5).toFixed(1) + "L"} width={44} />
                <Tooltip contentStyle={tipStyle} formatter={(v, n) => [fmt.inr0(v), n]} />
                <Legend wrapperStyle={{ fontSize: 11, fontFamily: "JetBrains Mono" }} />
                <Area type="monotone" dataKey="strategy" name="Strategy" stroke="#3B82F6" strokeWidth={1.8} fill="url(#strat)" isAnimationActive={false} className="glow-line" />
                <Line type="monotone" dataKey="benchmark" name="Market" stroke="#71717A" strokeWidth={1.2} dot={false} strokeDasharray="4 4" isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-px">
            <div className="grid-cell p-4 lg:col-span-2">
              <div className="overline mb-3">Drawdown</div>
              <ResponsiveContainer width="100%" height={180}>
                <ComposedChart data={data.curve} margin={{ top: 4, right: 6, left: 6, bottom: 0 }}>
                  <CartesianGrid stroke="#27272A" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} tickFormatter={(v) => v.slice(0, 7)} minTickGap={50} />
                  <YAxis tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} tickFormatter={(v) => v + "%"} width={40} />
                  <Tooltip contentStyle={tipStyle} formatter={(v) => v + "%"} />
                  <Area type="monotone" dataKey="drawdown" stroke="#EF4444" strokeWidth={1.2} fill="#EF4444" fillOpacity={0.15} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="grid-cell p-4">
              <div className="overline mb-3">Selected Basket (Top {data.top_n})</div>
              <div className="flex flex-wrap gap-1.5">
                {data.picks.map((s) => <span key={s} className="mono text-xs px-2 py-1 border border-[var(--border)] bg-[#0a0a0a]">{s}</span>)}
              </div>
              <div className="mono text-[10px] text-[var(--text-muted)] mt-4 leading-relaxed bg-[#0a0a0a] border border-[var(--border)] p-2">
                Ann.Vol σ = {data.metrics.ann_vol}%<br />
                Sortino = (Rp − Rf)/σ_down<br />
                Alpha = CAGR_strat − CAGR_mkt
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
const tipStyle = { background: "#0a0a0a", border: "1px solid #27272A", borderRadius: 0, fontFamily: "JetBrains Mono", fontSize: 11 };

const MiniM = ({ label, value, hint, color }) => (
  <div className="bg-[#0a0a0a] border border-[var(--border)] p-3">
    <div className="overline">{label}</div>
    <div className="mono text-xl font-semibold mt-1" style={{ color: color || "#fff" }}>{value}</div>
    <div className="mono text-[9px] text-[var(--text-muted)] mt-0.5">{hint}</div>
  </div>
);
