"""QuantPick v3: Angel One live, analytics (risk/FF5/Kelly), IC/IR, sector heatmap,
search, performance, live-order safety."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------- Broker status ----------
class TestBroker:
    def test_broker_status(self, s):
        r = s.get(f"{API}/broker/status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["configured"] is True
        assert d["connected"] is True
        assert d["tokens_loaded"] >= 40
        assert "funds" in d


# ---------- Data status v3 ----------
class TestDataStatusV3:
    def test_source_and_angel(self, s):
        r = s.get(f"{API}/data-status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["angel_configured"] is True
        assert d["ml_trained"] is True
        assert d["data"]["source"] in ("angelone+yfinance", "yfinance")
        assert d["data"]["angel_ltp"] >= 1
        assert d["data"]["total"] == 60


# ---------- Analytics ----------
class TestAnalytics:
    @pytest.mark.parametrize("sym", ["RELIANCE", "HAL"])
    def test_analytics(self, s, sym):
        r = s.get(f"{API}/analytics/{sym}", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        rm = d["risk_metrics"]
        for k in ["beta", "ann_return", "ann_vol", "sharpe", "sortino", "max_drawdown", "calmar"]:
            assert k in rm, f"missing risk_metrics.{k}"
        ff = d["fama_french"]
        assert "loadings" in ff
        for f in ["MKT", "SMB", "HML", "RMW", "CMA"]:
            assert f in ff["loadings"], f"missing FF loading {f}"
        for k in ["alpha_ann", "r2", "alpha_score"]:
            assert k in ff
        k = d["kelly"]
        for kk in ["fraction", "pct", "win_prob", "win_loss_ratio"]:
            assert kk in k


# ---------- Sector heatmap ----------
class TestSectorHeatmap:
    def test_heatmap(self, s):
        r = s.get(f"{API}/sector-heatmap", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "sectors" in d and isinstance(d["sectors"], list)
        assert len(d["sectors"]) >= 3
        s0 = d["sectors"][0]
        for k in ["sector", "avg_composite", "count", "buys", "buy_pct", "top"]:
            assert k in s0
        # sorted desc
        avgs = [x["avg_composite"] for x in d["sectors"]]
        assert avgs == sorted(avgs, reverse=True)


# ---------- Information metrics ----------
class TestInfoMetrics:
    def test_info(self, s):
        r = s.get(f"{API}/information-metrics", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["ic", "ic_current", "ir", "breadth", "grade"]:
            assert k in d, f"missing {k}"


# ---------- Search ----------
class TestSearch:
    def test_search_rel(self, s):
        r = s.get(f"{API}/search?q=REL", timeout=30)
        assert r.status_code == 200
        d = r.json()
        results = d.get("results", d) if isinstance(d, dict) else d
        assert isinstance(results, list)
        assert len(results) > 0
        syms = [x["symbol"] for x in results]
        assert "RELIANCE" in syms
        # RELIANCE should have in_universe True
        rel = next(x for x in results if x["symbol"] == "RELIANCE")
        assert rel.get("in_universe") is True
        for f in ["symbol", "name", "exchange", "tradingsymbol", "in_universe"]:
            assert f in results[0]

    def test_search_tata_many(self, s):
        r = s.get(f"{API}/search?q=TATA", timeout=30)
        assert r.status_code == 200
        d = r.json()
        results = d.get("results", d) if isinstance(d, dict) else d
        assert len(results) >= 5


# ---------- Performance ----------
class TestPerformance:
    def test_perf(self, s):
        r = s.get(f"{API}/performance", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["tracking_days", "records", "win_rate", "buy_count"]:
            assert k in d, f"missing {k}"


# ---------- LIVE ORDER SAFETY (confirm=false must reject) ----------
class TestLiveOrderSafety:
    def test_live_requires_confirm(self, s):
        r = s.post(f"{API}/trade/live", json={"symbol": "SBIN", "side": "BUY", "qty": 1}, timeout=15)
        assert r.status_code == 400
        body = r.text.lower()
        assert "confirm" in body


# ---------- Regression: prior v1/v2 endpoints ----------
class TestRegression:
    def test_picks(self, s):
        r = s.get(f"{API}/picks?risk=balanced", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 60
        assert "ml_score" in d["picks"][0]

    def test_stock(self, s):
        r = s.get(f"{API}/stock/RELIANCE", timeout=60)
        assert r.status_code == 200

    def test_backtest(self, s):
        r = s.get(f"{API}/backtest", timeout=60)
        assert r.status_code == 200

    def test_watchlist(self, s):
        r = s.get(f"{API}/watchlist", timeout=15)
        assert r.status_code == 200

    def test_compare(self, s):
        r = s.get(f"{API}/compare?symbols=TITAN,INFY", timeout=60)
        assert r.status_code == 200

    def test_settings(self, s):
        r = s.get(f"{API}/settings", timeout=15)
        assert r.status_code == 200

    def test_alerts(self, s):
        r = s.get(f"{API}/alerts", timeout=15)
        assert r.status_code == 200

    def test_portfolio(self, s):
        r = s.get(f"{API}/portfolio", timeout=15)
        assert r.status_code == 200
