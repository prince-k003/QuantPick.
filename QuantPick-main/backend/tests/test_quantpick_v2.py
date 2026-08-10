"""QuantPick v2: tests for new features - live data, ML, watchlist, compare."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    # Wait for ML training to complete (in case previous run triggered a refresh)
    import time
    for _ in range(30):
        try:
            r = sess.get(f"{API}/data-status", timeout=10)
            if r.status_code == 200 and r.json().get("ml_trained"):
                break
        except Exception:
            pass
        time.sleep(2)
    return sess


# ---------- Data status ----------
class TestDataStatus:
    def test_data_status(self, s):
        r = s.get(f"{API}/data-status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["ml_trained"] is True
        assert d["angel_configured"] is False
        assert d["data"]["total"] == 60
        assert d["data"]["source"] in ["yfinance", "seeded"]
        assert 0 <= d["data"]["live_count"] <= 60


# ---------- Picks with ML ----------
class TestPicksML:
    def test_picks_include_ml_fields(self, s):
        r = s.get(f"{API}/picks?risk=balanced", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 60
        p0 = d["picks"][0]
        for k in ["ml_score", "ml_signal", "ml_buy_prob", "direction_prob"]:
            assert k in p0, f"missing {k}"
        assert 0 <= p0["ml_score"] <= 100
        assert p0["ml_signal"] in ["BUY", "HOLD", "SELL"]
        # ml_buy_prob/direction_prob may be returned as percentage (0-100) or ratio (0-1)
        assert 0 <= p0["ml_buy_prob"] <= 100
        assert 0 <= p0["direction_prob"] <= 100


# ---------- Refresh ----------
class TestRefresh:
    def test_refresh(self, s):
        r = s.post(f"{API}/refresh", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is True


# ---------- Watchlist ----------
class TestWatchlist:
    def test_watchlist_get_toggle(self, s):
        # Ensure TCS not pinned initially - toggle twice guarantees back to original
        r = s.get(f"{API}/watchlist", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "symbols" in d and "items" in d
        initially_pinned = "TCS" in d["symbols"]

        # Toggle once
        r = s.post(f"{API}/watchlist/toggle", json={"symbol": "TCS"}, timeout=15)
        assert r.status_code == 200
        d1 = r.json()
        assert d1["pinned"] == (not initially_pinned)

        # Toggle back to original state
        r = s.post(f"{API}/watchlist/toggle", json={"symbol": "TCS"}, timeout=15)
        assert r.status_code == 200
        d2 = r.json()
        assert d2["pinned"] == initially_pinned

        # Verify TCS presence matches initial
        r = s.get(f"{API}/watchlist", timeout=15)
        final = r.json()
        assert ("TCS" in final["symbols"]) == initially_pinned

    def test_watchlist_invalid_symbol(self, s):
        r = s.post(f"{API}/watchlist/toggle", json={"symbol": "NOTREAL123"}, timeout=15)
        assert r.status_code == 404


# ---------- Compare ----------
class TestCompare:
    def test_compare_three(self, s):
        r = s.get(f"{API}/compare?symbols=TITAN,INFY,BEL", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "chart" in d
        assert len(d["items"]) == 3
        syms = {it["symbol"] for it in d["items"]}
        assert syms == {"TITAN", "INFY", "BEL"}
        # Chart aligned
        assert isinstance(d["chart"], list) and len(d["chart"]) > 10
        pt0 = d["chart"][0]
        assert "date" in pt0
        for sym in ["TITAN", "INFY", "BEL"]:
            assert sym in pt0, f"missing {sym} in chart point"
        # Base-100 normalization: first non-null value for each symbol should be ~100
        for sym in ["TITAN", "INFY", "BEL"]:
            first_val = next((p[sym] for p in d["chart"] if p.get(sym) is not None), None)
            assert first_val is not None
            assert 99 <= first_val <= 101, f"{sym} base not 100: {first_val}"

    def test_compare_cap_at_5(self, s):
        r = s.get(f"{API}/compare?symbols=TITAN,INFY,BEL,HAL,RELIANCE,TCS,WIPRO", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert len(d["items"]) == 5


# ---------- Stock detail ML fields ----------
class TestStockML:
    def test_stock_has_ml(self, s):
        r = s.get(f"{API}/stock/HAL", timeout=60)
        assert r.status_code == 200
        d = r.json()
        sc = d["scored"]
        for k in ["ml_score", "ml_signal", "ml_buy_prob", "direction_prob"]:
            assert k in sc, f"missing {k} in scored"
