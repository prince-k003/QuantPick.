import { useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Screener from "@/pages/Screener";
import StockDetail from "@/pages/StockDetail";
import Portfolio from "@/pages/Portfolio";
import Backtest from "@/pages/Backtest";
import Alerts from "@/pages/Alerts";
import Settings from "@/pages/Settings";
import Watchlist from "@/pages/Watchlist";
import Compare from "@/pages/Compare";
import SectorHeatmap from "@/pages/SectorHeatmap";
import Performance from "@/pages/Performance";
import { api } from "@/lib/apiClient";

function App() {
  const [risk, setRiskState] = useState(localStorage.getItem("qp_risk") || "balanced");
  const [meta, setMeta] = useState(null);
  const [dataStatus, setDataStatus] = useState(null);

  const setRisk = (r) => { setRiskState(r); localStorage.setItem("qp_risk", r); };
  const reloadStatus = () => api.dataStatus().then(setDataStatus).catch(() => {});

  useEffect(() => {
    api.meta().then(setMeta).catch(() => {});
    api.settings().then((s) => { if (s.risk_profile) setRiskState(s.risk_profile); }).catch(() => {});
    reloadStatus();
    const iv = setInterval(reloadStatus, 20000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="App">
      <Toaster theme="dark" position="bottom-right" toastOptions={{ style: { fontFamily: "JetBrains Mono", borderRadius: 0, background: "#121212", border: "1px solid #27272A" } }} />
      <BrowserRouter>
        <Layout risk={risk} setRisk={setRisk} meta={meta} dataStatus={dataStatus} reloadStatus={reloadStatus}>
          <Routes>
            <Route path="/" element={<Dashboard risk={risk} />} />
            <Route path="/screener" element={<Screener risk={risk} meta={meta} />} />
            <Route path="/heatmap" element={<SectorHeatmap risk={risk} />} />
            <Route path="/watchlist" element={<Watchlist risk={risk} />} />
            <Route path="/compare" element={<Compare risk={risk} />} />
            <Route path="/performance" element={<Performance />} />
            <Route path="/stock/:symbol" element={<StockDetail risk={risk} />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/backtest" element={<Backtest risk={risk} />} />
            <Route path="/alerts" element={<Alerts risk={risk} />} />
            <Route path="/settings" element={<Settings risk={risk} setRisk={setRisk} />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </div>
  );
}

export default App;
