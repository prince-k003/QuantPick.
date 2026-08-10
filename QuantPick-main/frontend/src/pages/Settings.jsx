import React, { useEffect, useState } from "react";
import { api } from "../lib/apiClient";
import { Loading } from "../components/quant";
import { Save, Mail, MessageCircle, KeyRound, Copy, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";

const RISK_DESC = {
  conservative: "Overweights fundamentals, value & low-volatility. Prioritizes capital preservation.",
  balanced: "Even blend of fundamental, technical & multi-factor signals. Default engine.",
  aggressive: "Overweights momentum & technical breakout signals. Higher turnover, higher risk.",
};

export default function Settings({ risk, setRisk }) {
  const [s, setS] = useState(null);
  const [broker, setBroker] = useState(null);
  const [ip, setIp] = useState(null);
  useEffect(() => {
    api.settings().then(setS);
    api.brokerStatus().then(setBroker).catch(() => {});
    api.serverIp().then(setIp).catch(() => {});
  }, []);
  if (!s) return <Loading label="Loading settings" />;

  const save = () => api.updateSettings({ ...s, risk_profile: risk }).then(() => toast.success("Settings saved"));
  const setAlert = (k, v) => setS((p) => ({ ...p, alerts: { ...p.alerts, [k]: v } }));

  return (
    <div className="fade-up space-y-5 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="mono text-xs text-[var(--text-muted)] mt-1">Risk profile, alert channels & broker integration</p>
      </div>

      <div className="grid-cell p-5">
        <div className="overline mb-3">Risk Profile</div>
        <div className="grid grid-cols-3 gap-3">
          {["conservative", "balanced", "aggressive"].map((r) => (
            <button key={r} onClick={() => setRisk(r)} data-testid={`settings-risk-${r}`}
              className={`text-left p-3 border transition-colors ${risk === r ? "border-[#2563EB] bg-[var(--surface-hover)]" : "border-[var(--border)] hover:bg-[var(--surface-hover)]"}`}>
              <div className="mono text-sm font-semibold capitalize" style={{ color: risk === r ? "#3B82F6" : "#fff" }}>{r}</div>
              <div className="text-[11px] text-[var(--text-muted)] mt-1 leading-snug">{RISK_DESC[r]}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="grid-cell p-5">
        <div className="overline mb-3">Alert Channels</div>
        <div className="space-y-3">
          {[["email", Mail, "Email (Resend)"], ["whatsapp", MessageCircle, "WhatsApp (Twilio)"]].map(([k, Icon, label]) => (
            <div key={k} className="flex items-center justify-between py-1">
              <span className="flex items-center gap-2 text-sm"><Icon size={15} className="text-[var(--text-muted)]" />{label}</span>
              <button onClick={() => setAlert(k, !s.alerts[k])} data-testid={`toggle-${k}`}
                className={`w-10 h-5 relative transition-colors ${s.alerts[k] ? "bg-[#2563EB]" : "bg-[#27272A]"}`}>
                <span className={`absolute top-0.5 w-4 h-4 bg-white transition-all ${s.alerts[k] ? "left-5" : "left-0.5"}`} />
              </button>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3 mt-4">
          <input placeholder="alert email" value={s.email} onChange={(e) => setS({ ...s, email: e.target.value })} data-testid="alert-email"
            className="bg-[#0a0a0a] border border-[var(--border)] mono text-xs px-3 py-2 outline-none focus:border-[#3B82F6]" />
          <input placeholder="whatsapp number" value={s.whatsapp_number} onChange={(e) => setS({ ...s, whatsapp_number: e.target.value })} data-testid="alert-whatsapp"
            className="bg-[#0a0a0a] border border-[var(--border)] mono text-xs px-3 py-2 outline-none focus:border-[#3B82F6]" />
        </div>
        <div className="mono text-[10px] text-[var(--hold)] mt-3">⚠ Email & WhatsApp delivery are MOCKED in this MVP — add Resend/Twilio keys to go live.</div>
      </div>

      <div className="grid-cell p-5">
        <div className="flex items-center gap-2 mb-3"><KeyRound size={14} className="text-[var(--text-muted)]" /><span className="overline">Live Broker — Angel One SmartAPI</span></div>
        <div className="flex flex-wrap items-center gap-6 mb-4">
          <div className="flex items-center gap-2">
            {broker?.connected ? <CheckCircle2 size={16} className="text-[var(--buy)]" /> : <XCircle size={16} className="text-[var(--sell)]" />}
            <span className="mono text-sm">{broker?.connected ? "Connected" : broker?.configured ? "Configured (not connected)" : "Not configured"}</span>
          </div>
          <div><span className="overline">Available Funds</span><div className="mono text-sm" data-testid="broker-funds">{broker?.funds != null ? `₹${Number(broker.funds).toLocaleString("en-IN")}` : "—"}</div></div>
          <div><span className="overline">Tokens Mapped</span><div className="mono text-sm">{broker?.tokens_loaded ?? 0}</div></div>
        </div>

        <div className="border border-[var(--border)] bg-[#0a0a0a] p-4">
          <div className="overline mb-2">Whitelist this server for Live Trading</div>
          <p className="text-xs text-[var(--text-secondary)] mb-3 leading-relaxed">
            Angel One requires your app's <b>Static IP</b> to match the server placing orders. Add the IP below as the
            Primary/Secondary Static IP in your SmartAPI app at <span className="mono text-[#3B82F6]">smartapi.angelone.in/new/apps</span>.
          </p>
          <div className="flex items-center gap-2 mb-3">
            <code className="mono text-lg text-[#06B6D4] bg-black px-3 py-1.5 border border-[var(--border)]" data-testid="server-ip">{ip?.server_ip || "…"}</code>
            <button onClick={() => { navigator.clipboard.writeText(ip?.server_ip || ""); toast.success("IP copied"); }}
              data-testid="copy-ip-btn" className="border border-[var(--border)] hover:bg-[var(--surface-hover)] p-2 transition-colors"><Copy size={14} /></button>
          </div>
          <ol className="text-[11px] text-[var(--text-muted)] mono space-y-1 list-decimal pl-4">
            {(ip?.instructions || []).map((line, i) => <li key={i}>{line}</li>)}
          </ol>
        </div>
        <div className="mono text-[10px] text-[var(--hold)] mt-3">
          ⚠ Live orders place REAL trades on your Angel One account. Requires whitelisted IP + sufficient funds.
        </div>
      </div>

      <button onClick={save} data-testid="save-settings" className="bg-[#2563EB] hover:bg-[#1d4ed8] text-white mono text-sm px-5 py-2.5 flex items-center gap-2 transition-colors">
        <Save size={15} /> Save Settings
      </button>
    </div>
  );
}
