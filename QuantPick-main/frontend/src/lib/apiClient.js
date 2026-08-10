import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API, timeout: 45000 });

export const api = {
  meta: () => client.get("/meta").then((r) => r.data),
  picks: (risk, limit = 100) => client.get(`/picks`, { params: { risk, limit } }).then((r) => r.data),
  screener: (params) => client.get(`/screener`, { params }).then((r) => r.data),
  stock: (symbol, risk) => client.get(`/stock/${symbol}`, { params: { risk } }).then((r) => r.data),
  aiAnalyst: (symbol, risk) => client.post(`/ai/analyst/${symbol}`, null, { params: { risk } }).then((r) => r.data),
  backtest: (risk, top_n) => client.get(`/backtest`, { params: { risk, top_n } }).then((r) => r.data),
  settings: () => client.get(`/settings`).then((r) => r.data),
  updateSettings: (body) => client.put(`/settings`, body).then((r) => r.data),
  portfolio: () => client.get(`/portfolio`).then((r) => r.data),
  trade: (body) => client.post(`/portfolio/trade`, body).then((r) => r.data),
  resetPortfolio: () => client.post(`/portfolio/reset`).then((r) => r.data),
  alerts: (risk) => client.get(`/alerts`, { params: { risk } }).then((r) => r.data),
  dataStatus: () => client.get(`/data-status`).then((r) => r.data),
  refresh: () => client.post(`/refresh`).then((r) => r.data),
  watchlist: (risk) => client.get(`/watchlist`, { params: { risk } }).then((r) => r.data),
  toggleWatch: (symbol) => client.post(`/watchlist/toggle`, { symbol }).then((r) => r.data),
  compare: (symbols, risk) => client.get(`/compare`, { params: { symbols: symbols.join(","), risk } }).then((r) => r.data),
  analytics: (symbol, risk) => client.get(`/analytics/${symbol}`, { params: { risk } }).then((r) => r.data),
  sectorHeatmap: (risk) => client.get(`/sector-heatmap`, { params: { risk } }).then((r) => r.data),
  infoMetrics: (risk) => client.get(`/information-metrics`, { params: { risk } }).then((r) => r.data),
  search: (q) => client.get(`/search`, { params: { q } }).then((r) => r.data),
  performance: () => client.get(`/performance`).then((r) => r.data),
  brokerStatus: () => client.get(`/broker/status`).then((r) => r.data),
  serverIp: () => client.get(`/broker/server-ip`).then((r) => r.data),
  tradeLive: (body) => client.post(`/trade/live`, body).then((r) => r.data),
};

export const fmt = {
  inr: (v) => "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 }),
  inr0: (v) => "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 }),
  num: (v, d = 2) => Number(v).toFixed(d),
  pct: (v, d = 2) => (v >= 0 ? "+" : "") + Number(v).toFixed(d) + "%",
  compact: (v) => {
    const n = Number(v);
    if (Math.abs(n) >= 1e7) return "₹" + (n / 1e7).toFixed(2) + "Cr";
    if (Math.abs(n) >= 1e5) return "₹" + (n / 1e5).toFixed(2) + "L";
    return "₹" + n.toFixed(0);
  },
};

export const signalColor = (s) =>
  s === "BUY" ? "var(--buy)" : s === "SELL" ? "var(--sell)" : "var(--hold)";
