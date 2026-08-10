import React from "react";

export const SignalBadge = ({ signal, size = "sm" }) => {
  const map = {
    BUY: { c: "var(--buy)", bg: "rgba(16,185,129,0.12)" },
    SELL: { c: "var(--sell)", bg: "rgba(239,68,68,0.12)" },
    HOLD: { c: "var(--hold)", bg: "rgba(234,179,8,0.12)" },
  };
  const s = map[signal] || map.HOLD;
  const pad = size === "lg" ? "px-3 py-1 text-xs" : "px-2 py-0.5 text-[10px]";
  return (
    <span
      className={`mono font-semibold tracking-wider ${pad} rounded-sm border`}
      style={{ color: s.c, background: s.bg, borderColor: s.c + "40" }}
      data-testid={`signal-badge-${signal}`}
    >
      {signal}
    </span>
  );
};

export const ScoreBar = ({ value, color = "#3B82F6", label }) => (
  <div className="w-full">
    {label && <div className="flex justify-between mb-1"><span className="overline">{label}</span>
      <span className="mono text-xs" style={{ color }}>{Number(value).toFixed(1)}</span></div>}
    <div className="h-1.5 w-full bg-[#0a0a0a] border border-[#27272A] overflow-hidden">
      <div className="h-full transition-all duration-500" style={{ width: `${Math.min(100, Math.max(0, value))}%`, background: color }} />
    </div>
  </div>
);

export const Delta = ({ value, suffix = "%", digits = 2 }) => {
  const pos = value >= 0;
  return (
    <span className="mono" style={{ color: pos ? "var(--buy)" : "var(--sell)" }}>
      {pos ? "+" : ""}{Number(value).toFixed(digits)}{suffix}
    </span>
  );
};

export const Stat = ({ label, value, sub, color }) => (
  <div className="grid-cell p-4">
    <div className="overline mb-2">{label}</div>
    <div className="mono text-2xl font-semibold" style={{ color: color || "#fff" }}>{value}</div>
    {sub && <div className="mono text-xs text-[var(--text-muted)] mt-1">{sub}</div>}
  </div>
);

export const Loading = ({ label = "Computing quant signals" }) => (
  <div className="flex items-center gap-3 text-[var(--text-muted)] p-8 fade-up">
    <span className="w-2 h-2 rounded-full bg-[#3B82F6] live-dot" />
    <span className="mono text-sm">{label}…</span>
  </div>
);
