import React, { useEffect, useState } from "react";
import { api } from "../lib/apiClient";
import { Loading } from "../components/quant";
import { Bell, AlertTriangle, TrendingUp, ShieldAlert } from "lucide-react";

const META = {
  NEW_PICK: { icon: TrendingUp, color: "#10B981", tag: "NEW PICK" },
  OVERBOUGHT: { icon: AlertTriangle, color: "#EAB308", tag: "OVERBOUGHT" },
  STOP_LOSS: { icon: ShieldAlert, color: "#EF4444", tag: "STOP LOSS" },
};

export default function Alerts({ risk }) {
  const [data, setData] = useState(null);
  useEffect(() => { setData(null); api.alerts(risk).then(setData); }, [risk]);
  if (!data) return <Loading label="Scanning for signals" />;

  return (
    <div className="fade-up space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Signal Alerts</h1>
        <p className="mono text-xs text-[var(--text-muted)] mt-1">{data.channels_note}</p>
      </div>

      <div className="panel divide-y divide-[var(--border)]">
        {data.alerts.length === 0 && <div className="mono text-xs text-[var(--text-muted)] p-6">No active alerts.</div>}
        {data.alerts.map((a, i) => {
          const m = META[a.type] || META.NEW_PICK;
          return (
            <div key={i} className="flex items-start gap-3 p-4 tr-hover" data-testid={`alert-${i}`}>
              <div className="w-8 h-8 flex items-center justify-center shrink-0 border" style={{ borderColor: m.color + "40", background: m.color + "12" }}>
                <m.icon size={15} style={{ color: m.color }} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="mono text-[10px] tracking-wider px-1.5 py-0.5" style={{ color: m.color, background: m.color + "12" }}>{m.tag}</span>
                  <span className="mono text-xs font-semibold">{a.symbol}</span>
                </div>
                <div className="text-sm text-[var(--text-secondary)] mt-1">{a.message}</div>
              </div>
              <span className="mono text-[10px] text-[var(--text-muted)]">now</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
