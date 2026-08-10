import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ComposedChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid,
} from "recharts";
import { api, fmt } from "../lib/apiClient";
import { SignalBadge, ScoreBar, Delta, Loading } from "../components/quant";
import { ArrowLeft, Sparkles, ShoppingCart, Newspaper, Star, GitCompare, BrainCircuit } from "lucide-react";
import { toast } from "sonner";

const renderNote = (md) => {
  let h = md
    .replace(/^# (.*)$/gm, "<h1>$1</h1>")
    .replace(/^#{2,3} (.*)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/^---$/gm, "<hr/>")
    .replace(/^- (.*)$/gm, "<li>$1</li>");
  h = h.split(/\n{2,}/).map((b) => (b.startsWith("<") ? b : `<p>${b.replace(/\n/g, "<br/>")}</p>`)).join("");
  return h;
};

export default function StockDetail({ risk }) {
  const { symbol } = useParams();
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [ai, setAi] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [qty, setQty] = useState(10);
  const [pinned, setPinned] = useState(false);
  const [an, setAn] = useState(null);

  useEffect(() => { setD(null); setErr(null); setAi(null); setAn(null);
    api.stock(symbol, risk).then(setD).catch((e) => setErr(e.message || "Failed to load"));
    api.analytics(symbol, risk).then(setAn).catch(() => {});
    api.watchlist(risk).then((w) => setPinned((w.symbols || []).includes(symbol))).catch(() => {}); }, [symbol, risk]);

  const togglePin = () => api.toggleWatch(symbol).then((r) => { setPinned(r.pinned); toast.success(r.pinned ? `Pinned ${symbol}` : `Unpinned ${symbol}`); });

  const tradeLive = (side) => {
    if (!window.confirm(`⚠ LIVE ORDER (real money via Angel One)\n\n${side} ${qty} ${symbol} at MARKET.\n\nThis places a real order on your broker account. Proceed?`)) return;
    api.tradeLive({ symbol, side, qty: Number(qty), confirm: true })
      .then((r) => r.ok ? toast.success(`Live ${side} placed · order ${r.order_id || "sent"}`) : toast.error(r.message || "Order rejected"))
      .catch((e) => toast.error(e.response?.data?.detail || "Live order failed"));
  };

  const runAi = () => {
    setAiLoading(true);
    api.aiAnalyst(symbol, risk).then((r) => { setAi(r.analysis); setAiLoading(false); })
      .catch(() => { setAiLoading(false); toast.error("AI analysis failed"); });
  };

  const trade = (side) => {
    api.trade({ symbol, side, qty: Number(qty) })
      .then((r) => toast.success(`${side} ${qty} ${symbol} @ ${fmt.inr(r.executed_price)}`))
      .catch((e) => toast.error(e.response?.data?.detail || "Trade failed"));
  };

  if (err) return <div className="mono text-sm text-[var(--sell)] p-8" data-testid="detail-error">Error: {err}</div>;
  if (!d) return <Loading label="Loading deep-dive" />;
  const sc = d.scored || {};
  const t = d.technicals;
  const f = d.fundamentals;
  const dcf = d.dcf;

  return (
    <div className="fade-up space-y-5">
      <button onClick={() => nav(-1)} className="flex items-center gap-1.5 mono text-xs text-[var(--text-muted)] hover:text-white transition-colors" data-testid="back-btn">
        <ArrowLeft size={13} /> back
      </button>

      {/* Header */}
      <div className="panel p-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight mono">{d.symbol}</h1>
            <span className="text-[10px] mono px-1.5 py-0.5 border border-[var(--border)] text-[var(--text-muted)]">{d.exchange}</span>
            <span className="text-[10px] mono px-1.5 py-0.5 border border-[var(--border)] text-[var(--text-secondary)]">{d.sector}</span>
            <button onClick={togglePin} data-testid="pin-detail-btn" title="Pin to watchlist">
              <Star size={16} className={pinned ? "text-[var(--hold)] fill-[var(--hold)]" : "text-[var(--text-muted)] hover:text-[var(--hold)]"} />
            </button>
            <button onClick={() => nav(`/compare?symbols=${symbol}`)} data-testid="compare-detail-btn" title="Compare"
              className="flex items-center gap-1 mono text-[10px] border border-[var(--border)] px-1.5 py-0.5 text-[var(--text-secondary)] hover:text-white hover:bg-[var(--surface-hover)] transition-colors">
              <GitCompare size={11} /> compare
            </button>
          </div>
          <div className="text-sm text-[var(--text-secondary)] mt-1">{d.name}</div>
        </div>
        <div className="flex items-center gap-8">
          <div>
            <div className="overline">Last Price</div>
            <div className="mono text-3xl font-semibold" data-testid="detail-price">{fmt.inr(t.price)}</div>
          </div>
          <div>
            <div className="overline">Composite</div>
            <div className="mono text-3xl font-semibold text-[#3B82F6]">{sc.composite}</div>
          </div>
          <div className="text-center">
            <div className="overline mb-1">{sc.rank ? `Rank #${sc.rank}` : (d.on_demand ? "On-Demand" : "")}</div>
            <SignalBadge signal={sc.signal} size="lg" />
          </div>
        </div>
      </div>

      {d.on_demand && (
        <div className="panel p-2.5 mono text-[11px] flex items-center gap-2" style={{ borderLeft: "2px solid #06B6D4" }} data-testid="ondemand-badge">
          <span className="text-[#06B6D4]">◆ ON-DEMAND</span>
          <span className="text-[var(--text-muted)]">Scored live on request (outside the curated universe).{!d.has_fundamentals && " Fundamentals limited — DCF/Piotroski may be unavailable."}</span>
        </div>
      )}

      {/* ML + Sub scores + trade */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-px">
        <div className="grid-cell p-4 space-y-3 lg:col-span-2">
          <div className="overline mb-1">Signal Decomposition</div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-3">
            <ScoreBar label="Fundamental" value={d.fundamental_score} color="#10B981" />
            <ScoreBar label="Technical" value={d.technical_score} color="#3B82F6" />
            <ScoreBar label="Quant Factor" value={sc.factor_score} color="#8B5CF6" />
            <ScoreBar label="ML (XGBoost)" value={sc.ml_score ?? 50} color="#F97316" />
            <ScoreBar label="News Sentiment" value={sc.sentiment_score} color="#06B6D4" />
            <ScoreBar label="Momentum (pctl)" value={sc.momentum} color="#EAB308" />
          </div>
          <div className="grid grid-cols-3 gap-px mt-2 pt-3 border-t border-[var(--border)]">
            <div className="text-center" data-testid="ml-signal">
              <div className="overline mb-1 flex items-center justify-center gap-1"><BrainCircuit size={11} className="text-[#F97316]" /> ML Signal</div>
              <SignalBadge signal={sc.ml_signal || "HOLD"} />
            </div>
            <MiniStat label="Buy Prob" value={(sc.ml_buy_prob ?? "—") + "%"} color="var(--buy)" />
            <MiniStat label="Next-day Up" value={(sc.direction_prob ?? "—") + "%"} color={sc.direction_prob >= 50 ? "var(--buy)" : "var(--sell)"} />
          </div>
        </div>
        <div className="grid-cell p-4 space-y-3">
          <div className="overline">Paper Trade</div>
          <div className="flex items-center gap-2">
            <input type="number" value={qty} onChange={(e) => setQty(e.target.value)} data-testid="trade-qty"
              className="w-20 bg-[#0a0a0a] border border-[var(--border)] mono text-sm px-2 py-2 outline-none focus:border-[#3B82F6]" />
            <span className="mono text-xs text-[var(--text-muted)]">≈ {fmt.inr(qty * t.price)}</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => trade("BUY")} data-testid="buy-btn" className="bg-[var(--buy)] hover:opacity-90 text-black font-semibold mono text-sm py-2.5 flex items-center justify-center gap-1.5 transition-opacity">
              <ShoppingCart size={14} /> BUY
            </button>
            <button onClick={() => trade("SELL")} data-testid="sell-btn" className="bg-[var(--sell)] hover:opacity-90 text-white font-semibold mono text-sm py-2.5 transition-opacity">
              SELL
            </button>
          </div>
          <div className="pt-2 border-t border-[var(--border)]">
            <div className="overline mb-1.5">Live Order · Angel One <span className="text-[var(--sell)]">real money</span></div>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => tradeLive("BUY")} data-testid="live-buy-btn" className="border border-[var(--buy)] text-[var(--buy)] hover:bg-[var(--buy)] hover:text-black font-semibold mono text-xs py-2 transition-colors">
                LIVE BUY
              </button>
              <button onClick={() => tradeLive("SELL")} data-testid="live-sell-btn" className="border border-[var(--sell)] text-[var(--sell)] hover:bg-[var(--sell)] hover:text-white font-semibold mono text-xs py-2 transition-colors">
                LIVE SELL
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced quant analytics */}
      {an && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-px">
        <div className="grid-cell p-4">
          <div className="overline mb-3">Risk Metrics</div>
          <div className="grid grid-cols-2 gap-y-2.5 gap-x-4 mono text-xs">
            <Kv k="Beta (vs mkt)" v={an.risk_metrics?.beta} />
            <Kv k="Ann. Return" v={(an.risk_metrics?.ann_return) + "%"} />
            <Kv k="Ann. Vol σ" v={(an.risk_metrics?.ann_vol) + "%"} />
            <Kv k="Sharpe" v={an.risk_metrics?.sharpe} />
            <Kv k="Sortino" v={an.risk_metrics?.sortino} />
            <Kv k="Max Drawdown" v={(an.risk_metrics?.max_drawdown) + "%"} />
            <Kv k="Calmar" v={an.risk_metrics?.calmar} />
          </div>
        </div>

        <div className="grid-cell p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="overline">Fama-French 5-Factor</span>
            <span className="mono text-[10px] text-[var(--text-muted)]">R²={an.fama_french?.r2}</span>
          </div>
          <div className="space-y-1.5 mono text-xs">
            {an.fama_french && Object.entries({ "Market (β)": an.fama_french.loadings.MKT, "Size (SMB)": an.fama_french.loadings.SMB, "Value (HML)": an.fama_french.loadings.HML, "Profit (RMW)": an.fama_french.loadings.RMW, "Invest (CMA)": an.fama_french.loadings.CMA }).map(([k, v]) => (
              <div key={k} className="flex items-center gap-2">
                <span className="w-24 text-[var(--text-muted)]">{k}</span>
                <div className="flex-1 h-3 bg-[#0a0a0a] relative">
                  <div className="absolute top-0 bottom-0 left-1/2" style={{ width: 1, background: "#3f3f42" }} />
                  <div className="absolute top-0 bottom-0" style={{ left: v >= 0 ? "50%" : `${50 + v * 25}%`, width: `${Math.min(50, Math.abs(v) * 25)}%`, background: v >= 0 ? "var(--buy)" : "var(--sell)" }} />
                </div>
                <span className="w-10 text-right" style={{ color: v >= 0 ? "var(--buy)" : "var(--sell)" }}>{v > 0 ? "+" : ""}{v}</span>
              </div>
            ))}
          </div>
          <div className="mono text-[10px] text-[var(--text-muted)] mt-3 pt-2 border-t border-[var(--border)] flex justify-between">
            <span>Ann. Alpha: <span style={{ color: an.fama_french?.alpha_ann >= 0 ? "var(--buy)" : "var(--sell)" }}>{an.fama_french?.alpha_ann}%</span></span>
            <span>Alpha Score: <span className="text-[#8B5CF6]">{an.fama_french?.alpha_score}/100</span></span>
          </div>
        </div>

        <div className="grid-cell p-4">
          <div className="overline mb-3">Kelly Position Sizing</div>
          <div className="text-center py-2">
            <div className="mono text-4xl font-bold text-[#8B5CF6]" data-testid="kelly-pct">{an.kelly?.pct}%</div>
            <div className="mono text-[10px] text-[var(--text-muted)] mt-1">of portfolio (¼-Kelly cap)</div>
          </div>
          <div className="grid grid-cols-2 gap-y-2 gap-x-4 mono text-xs mt-2">
            <Kv k="Win Prob (W)" v={an.kelly?.win_prob + "%"} />
            <Kv k="Win/Loss (R)" v={an.kelly?.win_loss_ratio} />
          </div>
          <div className="mono text-[10px] text-[var(--text-muted)] mt-3 bg-[#0a0a0a] border border-[var(--border)] p-2">
            f* = W − (1−W)/R
          </div>
        </div>
      </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px">
        <div className="grid-cell p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="overline">Price · SMA50 · Bollinger (180d)</div>
            <div className="mono text-[10px] text-[var(--text-muted)]">RSI {t.rsi} · ADX {t.adx}</div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={d.chart} margin={{ top: 4, right: 6, left: -12, bottom: 0 }}>
              <CartesianGrid stroke="#27272A" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} tickFormatter={(v) => v.slice(5)} minTickGap={40} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} width={50} />
              <Tooltip contentStyle={tipStyle} labelStyle={{ color: "#71717A", fontSize: 10 }} />
              <ReferenceLine y={t.sma50} stroke="#EAB308" strokeDasharray="4 4" />
              <ReferenceLine y={t.bb_upper} stroke="#8B5CF6" strokeDasharray="2 4" />
              <ReferenceLine y={t.bb_lower} stroke="#8B5CF6" strokeDasharray="2 4" />
              <Line type="monotone" dataKey="close" stroke="#3B82F6" strokeWidth={1.6} dot={false} isAnimationActive={false} className="glow-line" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <div className="grid-cell p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="overline">Monte Carlo Fan · {d.monte_carlo.sims} paths · {d.monte_carlo.horizon_days}d GBM</div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={d.monte_carlo.fan} margin={{ top: 4, right: 6, left: -12, bottom: 0 }}>
              <CartesianGrid stroke="#27272A" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 9, fill: "#71717A", fontFamily: "JetBrains Mono" }} width={50} />
              <Tooltip contentStyle={tipStyle} />
              <Area type="monotone" dataKey="band90" stroke="none" fill="#3B82F6" fillOpacity={0.12} isAnimationActive={false} />
              <Area type="monotone" dataKey="band50" stroke="none" fill="#3B82F6" fillOpacity={0.25} isAnimationActive={false} />
              <Line type="monotone" dataKey="p50" stroke="#06B6D4" strokeWidth={1.6} dot={false} isAnimationActive={false} className="glow-line" />
            </ComposedChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-3 gap-px mt-3">
            <MiniStat label="Expected" value={fmt.inr(d.monte_carlo.expected)} />
            <MiniStat label="VaR 95%" value={fmt.pct(d.monte_carlo.var95_pct)} color="var(--sell)" />
            <MiniStat label="P(+15%)" value={d.monte_carlo.prob_up_15pct + "%"} color="var(--buy)" />
          </div>
        </div>
      </div>

      {/* DCF + fundamentals + factors */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-px">
        <div className="grid-cell p-4">
          <div className="overline mb-3">DCF Intrinsic Value</div>
          {dcf.intrinsic ? (
            <>
              <div className="flex items-end justify-between">
                <div><div className="mono text-xs text-[var(--text-muted)]">Intrinsic</div><div className="mono text-2xl font-semibold">{fmt.inr(dcf.intrinsic)}</div></div>
                <div className="text-right"><div className="mono text-xs text-[var(--text-muted)]">Upside</div><div className="text-xl"><Delta value={dcf.upside} /></div></div>
              </div>
              <div className="mono text-[10px] text-[var(--text-muted)] mt-3 bg-[#0a0a0a] border border-[var(--border)] p-2 leading-relaxed">
                V = Σ FCFₜ/(1+WACC)ᵗ + TV/(1+WACC)⁵<br />
                WACC={(dcf.wacc * 100).toFixed(0)}% · g₁={(dcf.g1 * 100).toFixed(0)}% · g_term={(dcf.g2 * 100).toFixed(0)}%
              </div>
            </>
          ) : <div className="mono text-xs text-[var(--text-muted)]">{dcf.note}</div>}
        </div>

        <div className="grid-cell p-4">
          <div className="overline mb-3">Fundamentals</div>
          <div className="grid grid-cols-2 gap-y-2.5 gap-x-4 mono text-xs">
            <Kv k="P/E" v={f.pe} /><Kv k="P/B" v={f.pb} />
            <Kv k="ROE" v={f.roe + "%"} /><Kv k="ROCE" v={f.roce + "%"} />
            <Kv k="D/E" v={f.de} /><Kv k="EPS Growth" v={(f.eps_growth * 100).toFixed(0) + "%"} />
            <Kv k="Profit Margin" v={f.profit_margin + "%"} /><Kv k="Div Yield" v={f.div_yield + "%"} />
            <Kv k="Current Ratio" v={f.current_ratio} /><Kv k="Piotroski" v={d.piotroski + "/9"} />
          </div>
        </div>

        <div className="grid-cell p-4">
          <div className="overline mb-3">Technical Levels</div>
          <div className="grid grid-cols-2 gap-y-2.5 gap-x-4 mono text-xs">
            <Kv k="SMA 20" v={fmt.inr(t.sma20)} /><Kv k="SMA 50" v={fmt.inr(t.sma50)} />
            <Kv k="SMA 200" v={fmt.inr(t.sma200)} /><Kv k="RSI 14" v={t.rsi} />
            <Kv k="MACD Hist" v={t.macd_hist} /><Kv k="ADX" v={t.adx} />
            <Kv k="BB Upper" v={fmt.inr(t.bb_upper)} /><Kv k="BB Lower" v={fmt.inr(t.bb_lower)} />
            <Kv k="52W High" v={fmt.inr(t.high_52w)} /><Kv k="52W Low" v={fmt.inr(t.low_52w)} />
          </div>
        </div>
      </div>

      {/* AI + News */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-px">
        <div className="grid-cell p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><Sparkles size={14} className="text-[#8B5CF6]" /><span className="overline" style={{ color: "#8B5CF6" }}>AI Quant Analyst</span></div>
            {!ai && <button onClick={runAi} disabled={aiLoading} data-testid="ai-analyst-btn" className="bg-[#8B5CF6] hover:opacity-90 text-white mono text-xs px-3 py-1.5 transition-opacity disabled:opacity-50">
              {aiLoading ? "Analyzing…" : "Generate Note"}
            </button>}
          </div>
          {aiLoading && <Loading label="Running quant analyst LLM" />}
          {ai ? <div className="ai-note" data-testid="ai-note" dangerouslySetInnerHTML={{ __html: renderNote(ai) }} />
            : !aiLoading && <div className="mono text-xs text-[var(--text-muted)]">Generate a rigorous LLM analyst note: DCF, factor loadings, VaR & CAPM-based verdict.</div>}
        </div>

        <div className="grid-cell p-4">
          <div className="flex items-center gap-2 mb-3"><Newspaper size={14} className="text-[#06B6D4]" /><span className="overline">News · FinBERT Sentiment</span></div>
          <div className="mono text-xs mb-3">Aggregate: <span style={{ color: d.sentiment >= 0 ? "var(--buy)" : "var(--sell)" }}>{d.sentiment > 0 ? "+" : ""}{d.sentiment}</span></div>
          <div className="space-y-3">
            {d.news.map((n, i) => (
              <div key={i} className="border-l-2 pl-3" style={{ borderColor: n.sentiment >= 0 ? "var(--buy)" : "var(--sell)" }}>
                <div className="text-xs text-[var(--text-secondary)] leading-snug">{n.headline}</div>
                <div className="mono text-[10px] text-[var(--text-muted)] mt-1 flex justify-between">
                  <span>{n.source} · {n.time}</span>
                  <span style={{ color: n.sentiment >= 0 ? "var(--buy)" : "var(--sell)" }}>{n.sentiment > 0 ? "+" : ""}{n.sentiment}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const tipStyle = { background: "#0a0a0a", border: "1px solid #27272A", borderRadius: 0, fontFamily: "JetBrains Mono", fontSize: 11 };
const Kv = ({ k, v }) => (<><span className="text-[var(--text-muted)]">{k}</span><span className="text-right">{v}</span></>);
const MiniStat = ({ label, value, color }) => (
  <div className="bg-[#0a0a0a] border border-[var(--border)] p-2 text-center">
    <div className="overline">{label}</div><div className="mono text-sm mt-1" style={{ color: color || "#fff" }}>{value}</div>
  </div>
);
