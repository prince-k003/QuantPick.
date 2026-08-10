"""QuantPick backend regression tests."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------- Meta ----------
class TestMeta:
    def test_meta(self, s):
        r = s.get(f"{API}/meta", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["universe_size"] == 60
        assert "NSE" in d["exchanges"] and "BSE" in d["exchanges"]
        assert isinstance(d["sectors"], list) and len(d["sectors"]) > 5


# ---------- Picks ----------
class TestPicks:
    def test_picks_balanced(self, s):
        r = s.get(f"{API}/picks?risk=balanced", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 60
        p0 = d["picks"][0]
        for k in ["composite", "signal", "fundamental_score", "technical_score",
                  "factor_score", "sentiment_score", "rank", "price", "target"]:
            assert k in p0
        assert p0["rank"] == 1
        assert p0["signal"] in ["BUY", "HOLD", "SELL"]

    def test_picks_risk_variants_reorder(self, s):
        cons = s.get(f"{API}/picks?risk=conservative", timeout=60).json()["picks"]
        agg = s.get(f"{API}/picks?risk=aggressive", timeout=60).json()["picks"]
        top_cons = [p["symbol"] for p in cons[:10]]
        top_agg = [p["symbol"] for p in agg[:10]]
        assert top_cons != top_agg, "conservative and aggressive should reorder picks"


# ---------- Screener ----------
class TestScreener:
    def test_screener_filters(self, s):
        r = s.get(f"{API}/screener?exchange=NSE&max_pe=30&min_roe=15&max_de=1&signal=BUY", timeout=60)
        assert r.status_code == 200
        d = r.json()
        for row in d["results"]:
            assert row["exchange"] == "NSE"
            assert 0 < row["pe"] <= 30
            assert row["roe"] >= 15
            assert row["de"] <= 1
            assert row["signal"] == "BUY"

    def test_screener_sector(self, s):
        r = s.get(f"{API}/screener?sector=IT", timeout=60)
        assert r.status_code == 200
        for row in r.json()["results"]:
            assert row["sector"] == "IT"


# ---------- Stock detail ----------
class TestStockDetail:
    @pytest.mark.parametrize("sym", ["HAL", "RELIANCE"])
    def test_stock(self, s, sym):
        r = s.get(f"{API}/stock/{sym}", timeout=60)
        assert r.status_code == 200
        d = r.json()
        t = d["technicals"]
        for k in ["rsi", "macd_hist", "adx", "sma50", "sma200", "bb_upper", "bb_lower"]:
            assert k in t
        assert "intrinsic" in d["dcf"]
        mc = d["monte_carlo"]
        assert "fan" in mc and isinstance(mc["fan"], list) and len(mc["fan"]) > 5
        assert "band90" in mc["fan"][0] and "band50" in mc["fan"][0]
        assert "expected" in mc and "var95_pct" in mc and "prob_up_15pct" in mc
        assert len(d["news"]) == 3
        assert all("sentiment" in n for n in d["news"])
        assert len(d["chart"]) == 180
        assert d["scored"] is not None
        assert d["fundamental_score"] is not None
        assert d["piotroski"] is not None

    def test_invalid_symbol(self, s):
        r = s.get(f"{API}/stock/INVALIDSYM", timeout=30)
        assert r.status_code == 404


# ---------- AI Analyst ----------
class TestAI:
    def test_ai_analyst_and_cache(self, s):
        r1 = s.post(f"{API}/ai/analyst/HAL", timeout=90)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["analysis"] and len(d1["analysis"]) > 200
        # cached second call
        r2 = s.post(f"{API}/ai/analyst/HAL", timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["cached"] is True
        # quant content
        low = d1["analysis"].lower()
        assert any(k in low for k in ["sharpe", "dcf", "var", "wacc", "capm", "factor"])


# ---------- Backtest ----------
class TestBacktest:
    def test_backtest(self, s):
        r = s.get(f"{API}/backtest?risk=balanced&top_n=10", timeout=90)
        assert r.status_code == 200
        d = r.json()
        m = d["metrics"]
        for k in ["cagr", "benchmark_cagr", "alpha", "sharpe", "sortino",
                  "max_drawdown", "win_rate", "final_value"]:
            assert k in m
        assert 100 <= len(d["curve"]) <= 140
        c0 = d["curve"][0]
        for k in ["date", "strategy", "benchmark", "drawdown"]:
            assert k in c0
        assert len(d["picks"]) == 10


# ---------- Paper trading ----------
class TestPortfolio:
    def test_full_flow(self, s):
        # reset first
        r = s.post(f"{API}/portfolio/reset", timeout=30)
        assert r.status_code == 200
        p = s.get(f"{API}/portfolio", timeout=30).json()
        assert p["cash"] == 1000000.0
        assert p["holdings"] == []

        # BUY 5 HAL
        r = s.post(f"{API}/portfolio/trade", json={"symbol": "HAL", "side": "BUY", "qty": 5}, timeout=30)
        assert r.status_code == 200
        after = s.get(f"{API}/portfolio", timeout=30).json()
        assert after["cash"] < 1000000
        assert any(h["symbol"] == "HAL" and h["qty"] == 5 for h in after["holdings"])

        # BUY too much -> 400
        r = s.post(f"{API}/portfolio/trade", json={"symbol": "RELIANCE", "side": "BUY", "qty": 100000}, timeout=30)
        assert r.status_code == 400

        # SELL more than held
        r = s.post(f"{API}/portfolio/trade", json={"symbol": "HAL", "side": "SELL", "qty": 999}, timeout=30)
        assert r.status_code == 400

        # SELL 2
        r = s.post(f"{API}/portfolio/trade", json={"symbol": "HAL", "side": "SELL", "qty": 2}, timeout=30)
        assert r.status_code == 200
        after2 = s.get(f"{API}/portfolio", timeout=30).json()
        assert any(h["symbol"] == "HAL" and h["qty"] == 3 for h in after2["holdings"])

        # reset restores 1M
        s.post(f"{API}/portfolio/reset", timeout=30)
        p2 = s.get(f"{API}/portfolio", timeout=30).json()
        assert p2["cash"] == 1000000.0


# ---------- Settings ----------
class TestSettings:
    def test_settings(self, s):
        r = s.get(f"{API}/settings", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "risk_profile" in d and "alerts" in d
        r = s.put(f"{API}/settings", json={"risk_profile": "aggressive",
                                           "alerts": {"email": False, "whatsapp": True}}, timeout=30)
        assert r.status_code == 200
        d2 = s.get(f"{API}/settings", timeout=30).json()
        assert d2["risk_profile"] == "aggressive"
        assert d2["alerts"]["whatsapp"] is True
        # restore
        s.put(f"{API}/settings", json={"risk_profile": "balanced"}, timeout=30)


# ---------- Alerts ----------
class TestAlerts:
    def test_alerts(self, s):
        r = s.get(f"{API}/alerts?risk=balanced", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "alerts" in d
        if d["alerts"]:
            a0 = d["alerts"][0]
            for k in ["type", "symbol", "message"]:
                assert k in a0
