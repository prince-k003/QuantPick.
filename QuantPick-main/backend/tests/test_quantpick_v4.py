"""QuantPick v4: On-demand scorer for non-universe symbols + broker server-ip whitelist."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = f"{BASE_URL}/api"

TIMEOUT = 45  # on-demand yfinance calls can take 3-10s


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------- On-demand scoring for non-universe symbols ----------
class TestOnDemand:
    def test_dabur_ondemand(self, s):
        r = s.get(f"{API}/stock/DABUR", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("on_demand") is True, f"expected on_demand=True, got {d.get('on_demand')}"
        assert d.get("symbol") == "DABUR"
        scored = d.get("scored") or d
        for k in ["composite", "signal", "technical_score", "factor_score", "ml_score"]:
            assert k in scored, f"missing {k} in scored/detail"
        assert "technicals" in d
        assert "monte_carlo" in d
        assert isinstance(d.get("chart"), list) and len(d["chart"]) >= 100
        assert isinstance(d.get("news"), list) and len(d["news"]) >= 1
        assert "has_fundamentals" in d

    def test_persistent_ondemand(self, s):
        # Try PERSISTENT then LTIM as fallback
        for sym in ["PERSISTENT", "LTIM"]:
            r = s.get(f"{API}/stock/{sym}", timeout=TIMEOUT)
            if r.status_code == 200:
                d = r.json()
                assert d.get("on_demand") is True
                assert "composite" in (d.get("scored") or d)
                return
        pytest.fail("Neither PERSISTENT nor LTIM returned 200")

    def test_curated_no_ondemand_flag(self, s):
        r = s.get(f"{API}/stock/RELIANCE", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        # curated: on_demand should be absent or False
        assert not d.get("on_demand", False), "RELIANCE (curated) must NOT be flagged on_demand"
        assert d.get("symbol") == "RELIANCE"
        assert "rank" in d or "composite" in (d.get("scored") or d)

    def test_invalid_symbol_404(self, s):
        r = s.get(f"{API}/stock/ZZZNOTAREALSYMBOL", timeout=TIMEOUT)
        assert r.status_code == 404


# ---------- On-demand analytics ----------
class TestOnDemandAnalytics:
    def test_analytics_dabur(self, s):
        r = s.get(f"{API}/analytics/DABUR", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        rm = d.get("risk_metrics", {})
        for k in ["beta", "sharpe", "sortino", "max_drawdown", "calmar"]:
            assert k in rm, f"missing risk_metrics.{k}"
        ff = d.get("fama_french", {})
        assert "loadings" in ff
        for f in ["MKT", "SMB", "HML", "RMW", "CMA"]:
            assert f in ff["loadings"], f"missing FF5 loading {f}"
        assert "r2" in ff and "alpha_score" in ff
        k = d.get("kelly", {})
        for kk in ["pct", "win_prob", "win_loss_ratio"]:
            assert kk in k

    def test_analytics_reliance_still_works(self, s):
        r = s.get(f"{API}/analytics/RELIANCE", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert "risk_metrics" in d and "fama_french" in d and "kelly" in d


# ---------- Search returns non-universe with in_universe:false ----------
class TestSearch:
    def test_search_dabur(self, s):
        r = s.get(f"{API}/search", params={"q": "DABUR"}, timeout=30)
        assert r.status_code == 200
        payload = r.json()
        results = payload.get("results", payload) if isinstance(payload, dict) else payload
        assert isinstance(results, list) and len(results) > 0
        dabur = next((x for x in results if x.get("symbol") == "DABUR"), None)
        assert dabur is not None, "DABUR must appear in search results"
        assert dabur.get("in_universe") is False


# ---------- Broker server-ip whitelist ----------
class TestBrokerServerIp:
    def test_server_ip(self, s):
        r = s.get(f"{API}/broker/server-ip", timeout=30)
        assert r.status_code == 200
        d = r.json()
        ip = d.get("server_ip", "")
        assert isinstance(ip, str) and len(ip.split(".")) == 4, f"bad ip: {ip}"
        # basic sanity, public IPv4 (not empty/loopback)
        assert not ip.startswith("127."), f"loopback IP returned: {ip}"
        assert isinstance(d.get("instructions"), list) and len(d["instructions"]) >= 1

    def test_broker_status(self, s):
        r = s.get(f"{API}/broker/status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("configured") is True
        assert d.get("connected") is True
        assert d.get("tokens_loaded", 0) >= 40


# ---------- Live order safety ----------
class TestLiveOrderSafety:
    def test_missing_confirm_400(self, s):
        r = s.post(f"{API}/trade/live",
                   json={"symbol": "SBIN", "side": "BUY", "qty": 1},
                   timeout=30)
        assert r.status_code == 400, f"expected 400 without confirm, got {r.status_code}: {r.text}"


# ---------- Regression: key endpoints still 200 ----------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/picks",
        "/backtest",
        "/information-metrics",
        "/sector-heatmap",
        "/portfolio",
        "/watchlist",
        "/performance",
        "/settings",
        "/alerts",
    ])
    def test_endpoint_200(self, s, path):
        r = s.get(f"{API}{path}", timeout=30)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"

    def test_picks_has_ml_score(self, s):
        r = s.get(f"{API}/picks", timeout=30)
        d = r.json()
        picks = d if isinstance(d, list) else d.get("picks") or d.get("items") or []
        assert len(picks) > 0
        assert "ml_score" in picks[0]

    def test_compare(self, s):
        r = s.get(f"{API}/compare", params={"symbols": "RELIANCE,HAL"}, timeout=30)
        assert r.status_code == 200

    def test_ai_analyst(self, s):
        r = s.post(f"{API}/ai/analyst/RELIANCE", json={"risk": "balanced"}, timeout=60)
        assert r.status_code == 200
