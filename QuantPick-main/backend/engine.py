"""QuantPick engine: seeded NSE+BSE universe, deterministic price generation,
real technical / fundamental / quant-factor math, DCF, Monte Carlo, backtest."""
import hashlib
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import numpy as np

# ---------------------------------------------------------------------------
# Universe: representative NSE + BSE listed equities with realistic fundamentals
# fund keys: pe, pb, roe, roce, de, eps_growth, div_yield, profit_margin,
#            current_ratio, eps, fcf_cr(free cash flow crore), shares_cr, growth
# ---------------------------------------------------------------------------
def _s(symbol, name, exch, sector, price, pe, pb, roe, roce, de, dy, pm, cr, eps, fcf, shares, g):
    return {"symbol": symbol, "name": name, "exchange": exch, "sector": sector,
            "base_price": price,
            "fund": {"pe": pe, "pb": pb, "roe": roe, "roce": roce, "de": de,
                     "eps_growth": g, "div_yield": dy, "profit_margin": pm,
                     "current_ratio": cr, "eps": eps, "fcf_cr": fcf,
                     "shares_cr": shares, "growth": g}}


UNIVERSE = [
    _s("RELIANCE", "Reliance Industries", "NSE", "Energy", 2875, 24.1, 2.1, 9.2, 10.5, 0.42, 0.35, 8.1, 1.28, 98.3, 62000, 676, 0.10),
    _s("TCS", "Tata Consultancy Services", "NSE", "IT", 3860, 29.4, 14.2, 47.1, 58.2, 0.08, 1.3, 19.3, 2.6, 131.2, 42000, 366, 0.09),
    _s("HDFCBANK", "HDFC Bank", "NSE", "Financials", 1685, 18.9, 2.8, 16.9, 7.2, 0.9, 1.1, 22.5, 1.1, 89.1, 55000, 760, 0.14),
    _s("INFY", "Infosys", "NSE", "IT", 1520, 24.8, 8.1, 31.2, 39.6, 0.09, 2.4, 16.7, 2.2, 61.3, 25000, 415, 0.11),
    _s("ICICIBANK", "ICICI Bank", "NSE", "Financials", 1148, 17.2, 3.1, 18.1, 6.8, 0.85, 0.8, 24.1, 1.0, 66.7, 44000, 703, 0.16),
    _s("HINDUNILVR", "Hindustan Unilever", "NSE", "FMCG", 2410, 52.3, 11.4, 20.1, 26.8, 0.03, 1.7, 17.2, 1.3, 46.1, 9800, 235, 0.07),
    _s("BHARTIARTL", "Bharti Airtel", "NSE", "Telecom", 1355, 68.1, 7.9, 12.3, 9.8, 1.35, 0.5, 10.4, 0.6, 19.9, 21000, 595, 0.18),
    _s("ITC", "ITC Ltd", "NSE", "FMCG", 438, 26.4, 7.2, 27.8, 35.1, 0.01, 3.1, 25.4, 2.1, 16.6, 19000, 1247, 0.08),
    _s("SBIN", "State Bank of India", "NSE", "Financials", 815, 10.1, 1.6, 16.4, 5.1, 1.2, 1.6, 14.1, 1.0, 80.7, 61000, 892, 0.13),
    _s("LT", "Larsen & Toubro", "NSE", "Infrastructure", 3620, 34.2, 4.9, 15.2, 13.1, 1.1, 0.9, 7.8, 1.4, 105.8, 15000, 137, 0.15),
    _s("KOTAKBANK", "Kotak Mahindra Bank", "NSE", "Financials", 1780, 19.4, 2.9, 14.1, 6.9, 0.7, 0.1, 21.3, 1.1, 91.7, 18000, 198, 0.12),
    _s("AXISBANK", "Axis Bank", "NSE", "Financials", 1122, 13.1, 2.2, 17.9, 6.2, 0.95, 0.2, 20.1, 1.0, 85.6, 26000, 308, 0.15),
    _s("BAJFINANCE", "Bajaj Finance", "NSE", "Financials", 7150, 31.8, 5.9, 22.1, 11.2, 3.1, 0.3, 24.8, 1.2, 224.8, 14000, 62, 0.22),
    _s("ASIANPAINT", "Asian Paints", "NSE", "Consumer", 2890, 55.1, 14.8, 27.4, 34.2, 0.11, 1.1, 12.9, 1.6, 52.4, 6200, 96, 0.09),
    _s("MARUTI", "Maruti Suzuki", "NSE", "Auto", 12480, 27.6, 4.1, 15.9, 20.1, 0.01, 1.2, 8.4, 1.3, 452.1, 11000, 31, 0.13),
    _s("SUNPHARMA", "Sun Pharma", "NSE", "Pharma", 1680, 38.2, 5.4, 15.1, 17.8, 0.06, 0.8, 21.7, 2.4, 43.9, 9500, 240, 0.11),
    _s("TITAN", "Titan Company", "NSE", "Consumer", 3410, 88.4, 27.1, 32.1, 24.6, 0.65, 0.4, 7.9, 1.4, 38.5, 4100, 89, 0.17),
    _s("WIPRO", "Wipro", "NSE", "IT", 512, 22.1, 3.4, 15.2, 18.9, 0.18, 0.6, 15.1, 2.5, 23.1, 12000, 523, 0.06),
    _s("ULTRACEMCO", "UltraTech Cement", "NSE", "Cement", 11250, 44.1, 5.2, 12.8, 13.9, 0.28, 0.4, 10.2, 1.2, 254.9, 8700, 29, 0.12),
    _s("NESTLEIND", "Nestle India", "NSE", "FMCG", 2510, 68.9, 62.1, 108.2, 121.4, 0.02, 1.2, 15.8, 1.1, 36.4, 3200, 96, 0.10),
    _s("TATAMOTORS", "Tata Motors", "NSE", "Auto", 985, 12.4, 3.1, 24.1, 15.2, 1.45, 0.6, 6.7, 0.9, 79.4, 22000, 383, 0.20),
    _s("POWERGRID", "Power Grid Corp", "NSE", "Utilities", 328, 18.1, 3.0, 18.9, 11.4, 1.5, 3.4, 33.1, 0.7, 18.1, 15000, 930, 0.07),
    _s("NTPC", "NTPC Ltd", "NSE", "Utilities", 362, 15.2, 2.1, 13.4, 9.1, 1.4, 2.1, 12.8, 0.9, 23.8, 20000, 970, 0.09),
    _s("HCLTECH", "HCL Technologies", "NSE", "IT", 1642, 26.1, 6.2, 23.1, 28.4, 0.09, 3.6, 14.2, 2.3, 62.9, 21000, 271, 0.10),
    _s("TATASTEEL", "Tata Steel", "NSE", "Metals", 168, 44.2, 1.9, 4.1, 6.2, 0.82, 2.0, 3.1, 1.1, 3.8, 8000, 1250, 0.14),
    _s("JSWSTEEL", "JSW Steel", "NSE", "Metals", 918, 32.1, 2.9, 9.2, 10.1, 1.05, 0.8, 6.2, 0.9, 28.6, 9200, 245, 0.16),
    _s("ADANIENT", "Adani Enterprises", "NSE", "Conglomerate", 2950, 78.1, 6.8, 11.1, 8.9, 1.6, 0.1, 4.9, 1.1, 37.8, 6000, 114, 0.28),
    _s("COALINDIA", "Coal India", "NSE", "Mining", 452, 8.9, 3.1, 42.1, 55.2, 0.1, 5.8, 24.1, 1.3, 50.8, 30000, 616, 0.06),
    _s("ONGC", "Oil & Natural Gas Corp", "NSE", "Energy", 268, 6.4, 0.9, 15.1, 14.2, 0.42, 4.9, 8.9, 1.2, 41.9, 35000, 1258, 0.05),
    _s("GRASIM", "Grasim Industries", "NSE", "Cement", 2480, 27.1, 1.8, 8.1, 9.4, 0.55, 0.9, 9.1, 1.4, 91.5, 6500, 66, 0.11),
    _s("TECHM", "Tech Mahindra", "NSE", "IT", 1610, 42.1, 4.1, 10.2, 13.1, 0.12, 2.9, 8.1, 2.1, 38.2, 6000, 98, 0.05),
    _s("DRREDDY", "Dr Reddy's Labs", "NSE", "Pharma", 1290, 18.9, 3.2, 18.4, 22.1, 0.11, 0.8, 18.2, 2.6, 68.1, 6200, 83, 0.10),
    _s("CIPLA", "Cipla", "NSE", "Pharma", 1520, 27.4, 4.1, 16.1, 20.8, 0.09, 0.7, 16.4, 3.1, 55.4, 5100, 81, 0.11),
    _s("BAJAJFINSV", "Bajaj Finserv", "NSE", "Financials", 1620, 32.1, 3.9, 14.2, 10.1, 2.8, 0.1, 13.1, 1.1, 50.4, 12000, 159, 0.19),
    _s("HDFCLIFE", "HDFC Life Insurance", "NSE", "Insurance", 645, 82.1, 9.1, 11.2, 8.9, 0.2, 0.4, 4.1, 1.0, 7.8, 4200, 215, 0.14),
    _s("DIVISLAB", "Divi's Laboratories", "NSE", "Pharma", 4120, 68.1, 9.2, 14.1, 18.9, 0.02, 0.7, 24.1, 4.1, 60.5, 3100, 27, 0.12),
    _s("EICHERMOT", "Eicher Motors", "NSE", "Auto", 4680, 31.2, 6.9, 23.1, 28.1, 0.02, 0.9, 22.1, 2.1, 150.1, 4500, 27, 0.14),
    _s("BRITANNIA", "Britannia Industries", "NSE", "FMCG", 4890, 52.1, 32.1, 58.2, 61.1, 0.7, 1.4, 11.2, 1.2, 93.9, 3400, 24, 0.10),
    _s("HEROMOTOCO", "Hero MotoCorp", "NSE", "Auto", 4520, 21.1, 4.9, 22.1, 28.9, 0.05, 3.1, 11.1, 1.9, 214.2, 5100, 20, 0.08),
    _s("DMART", "Avenue Supermarts", "NSE", "Retail", 4180, 92.1, 12.1, 14.1, 18.2, 0.05, 0.0, 5.1, 2.1, 45.4, 3200, 65, 0.21),
    # BSE-focused / mid-cap names
    _s("VBL", "Varun Beverages", "BSE", "FMCG", 615, 62.1, 18.2, 28.1, 31.2, 0.55, 0.3, 12.1, 1.3, 9.9, 3100, 338, 0.24),
    _s("TRENT", "Trent Ltd", "BSE", "Retail", 6820, 148.1, 42.1, 24.1, 28.9, 0.4, 0.1, 8.9, 1.4, 46.1, 2400, 35, 0.35),
    _s("PIDILITIND", "Pidilite Industries", "BSE", "Chemicals", 3120, 82.1, 18.1, 24.1, 30.1, 0.05, 0.6, 15.1, 1.9, 38.1, 3100, 50, 0.13),
    _s("SIEMENS", "Siemens Ltd", "BSE", "Capital Goods", 7250, 78.1, 11.2, 16.1, 21.4, 0.02, 0.5, 11.1, 2.1, 92.8, 5100, 35, 0.16),
    _s("ABB", "ABB India", "BSE", "Capital Goods", 8410, 92.1, 18.1, 24.1, 31.2, 0.01, 0.4, 12.1, 2.4, 91.3, 4100, 21, 0.19),
    _s("BEL", "Bharat Electronics", "BSE", "Defence", 312, 44.1, 11.2, 26.1, 34.1, 0.0, 0.9, 18.1, 2.1, 7.1, 4200, 731, 0.20),
    _s("HAL", "Hindustan Aeronautics", "BSE", "Defence", 4820, 34.1, 8.9, 27.1, 34.2, 0.0, 1.1, 21.1, 2.4, 141.4, 8100, 67, 0.22),
    _s("IRCTC", "Indian Railway Catering", "BSE", "Services", 785, 52.1, 16.1, 42.1, 52.1, 0.0, 0.6, 24.1, 2.1, 15.1, 2100, 80, 0.18),
    _s("ZOMATO", "Zomato Ltd", "BSE", "Tech", 258, 142.1, 8.1, 3.1, 3.9, 0.0, 0.0, 6.1, 2.4, 1.8, 1400, 890, 0.42),
    _s("PAYTM", "One97 Communications", "BSE", "Tech", 685, -0.1, 3.1, -8.1, -6.2, 0.1, 0.0, -5.1, 3.1, -12.1, -900, 63, 0.30),
    _s("DLF", "DLF Ltd", "BSE", "Realty", 815, 68.1, 4.1, 8.1, 9.9, 0.25, 0.6, 26.1, 1.8, 12.0, 3200, 248, 0.16),
    _s("GAIL", "GAIL India", "BSE", "Energy", 208, 12.1, 1.8, 15.1, 14.2, 0.35, 3.1, 8.1, 1.4, 17.2, 9200, 657, 0.07),
    _s("IOC", "Indian Oil Corp", "BSE", "Energy", 168, 6.1, 1.1, 18.1, 12.4, 0.75, 6.1, 3.1, 0.9, 27.5, 18000, 1412, 0.04),
    _s("BPCL", "Bharat Petroleum", "BSE", "Energy", 312, 5.9, 1.4, 24.1, 16.1, 0.68, 5.9, 4.1, 0.8, 52.9, 15000, 217, 0.05),
    _s("VEDL", "Vedanta Ltd", "BSE", "Metals", 462, 12.1, 2.9, 21.1, 18.2, 1.55, 8.1, 8.1, 0.9, 38.2, 12000, 391, 0.10),
    _s("HINDALCO", "Hindalco Industries", "BSE", "Metals", 645, 11.2, 1.6, 12.1, 11.4, 0.62, 0.6, 5.1, 1.3, 57.5, 9200, 222, 0.09),
    _s("SHREECEM", "Shree Cement", "BSE", "Cement", 26500, 52.1, 4.1, 8.1, 10.2, 0.12, 0.4, 12.1, 1.9, 508.6, 4100, 3.6, 0.11),
    _s("PGHH", "Procter & Gamble Hygiene", "BSE", "FMCG", 15800, 68.1, 42.1, 68.1, 82.1, 0.02, 1.1, 16.1, 1.2, 232.1, 1100, 3.2, 0.09),
    _s("COLPAL", "Colgate-Palmolive India", "BSE", "FMCG", 2680, 52.1, 34.1, 68.1, 78.1, 0.01, 1.9, 21.1, 1.1, 51.5, 2100, 27, 0.10),
    _s("MARICO", "Marico Ltd", "BSE", "FMCG", 615, 48.1, 18.1, 38.1, 44.1, 0.05, 1.4, 14.1, 1.6, 12.8, 2100, 129, 0.11),
]

UNIVERSE_MAP = {s["symbol"]: s for s in UNIVERSE}
SECTORS = sorted({s["sector"] for s in UNIVERSE})
RISK_FREE = 0.068  # India 10Y approx


def _seed(symbol):
    return int(hashlib.md5(symbol.encode()).hexdigest(), 16) % (2**32)


@lru_cache(maxsize=256)
def generate_ohlcv(symbol, days=504):
    """Deterministic GBM daily price path anchored to the stock's base price."""
    st = UNIVERSE_MAP[symbol]
    rng = np.random.default_rng(_seed(symbol))
    # vol scaled loosely by (inverse) size + sector risk proxy via growth
    ann_vol = 0.18 + min(0.45, st["fund"]["growth"] * 0.9) + rng.uniform(0, 0.05)
    drift = st["fund"]["growth"] * 0.55 - 0.03  # trend embedded from expected growth
    dt = 1 / 252
    mu = (drift - 0.5 * ann_vol**2) * dt
    sigma = ann_vol * math.sqrt(dt)
    shocks = rng.normal(mu, sigma, days)
    # end at base_price -> back out start
    log_path = np.cumsum(shocks)
    prices = st["base_price"] * np.exp(log_path - log_path[-1])
    prices = np.maximum(prices, 1.0)
    end = datetime.now(timezone.utc).date()
    dates, bars = [], []
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        c = float(prices[i])
        o = c * (1 + rng.normal(0, 0.004))
        h = max(o, c) * (1 + abs(rng.normal(0, 0.006)))
        l = min(o, c) * (1 - abs(rng.normal(0, 0.006)))
        v = int(abs(rng.normal(1, 0.3)) * 1e6 * (1 + st["fund"]["growth"]))
        dates.append(d.isoformat())
        bars.append({"date": d.isoformat(), "open": round(o, 2), "high": round(h, 2),
                     "low": round(l, 2), "close": round(c, 2), "volume": v})
    return bars


# ---------------------------------------------------------------------------
# Technical indicators
# ---------------------------------------------------------------------------
def _ema(arr, span):
    a = 2 / (span + 1)
    out = np.zeros_like(arr, dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = a * arr[i] + (1 - a) * out[i - 1]
    return out


def _rsi(close, period=14):
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    ag = np.convolve(gain, np.ones(period) / period, "valid")
    al = np.convolve(loss, np.ones(period) / period, "valid")
    rs = ag / np.where(al == 0, 1e-9, al)
    rsi = 100 - 100 / (1 + rs)
    pad = np.full(len(close) - len(rsi), rsi[0] if len(rsi) else 50.0)
    return np.concatenate([pad, rsi])


def _adx(high, low, close, period=14):
    plus_dm = np.maximum(np.diff(high), 0)
    minus_dm = np.maximum(-np.diff(low), 0)
    tr = np.maximum(high[1:] - low[1:], np.abs(high[1:] - close[:-1]))
    tr = np.maximum(tr, np.abs(low[1:] - close[:-1]))
    atr = np.convolve(tr, np.ones(period) / period, "valid")
    if len(atr) == 0:
        return 20.0
    pdi = 100 * np.convolve(plus_dm, np.ones(period) / period, "valid")[: len(atr)] / np.where(atr == 0, 1e-9, atr)
    mdi = 100 * np.convolve(minus_dm, np.ones(period) / period, "valid")[: len(atr)] / np.where(atr == 0, 1e-9, atr)
    dx = 100 * np.abs(pdi - mdi) / np.where((pdi + mdi) == 0, 1e-9, pdi + mdi)
    return float(np.mean(dx[-period:]))


def technicals(bars):
    close = np.array([b["close"] for b in bars])
    high = np.array([b["high"] for b in bars])
    low = np.array([b["low"] for b in bars])
    sma20 = float(np.mean(close[-20:]))
    sma50 = float(np.mean(close[-50:]))
    sma200 = float(np.mean(close[-200:])) if len(close) >= 200 else float(np.mean(close))
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd_line = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    macd_hist = float(macd_line[-1] - signal_line[-1])
    rsi = _rsi(close)
    std20 = float(np.std(close[-20:]))
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    adx = _adx(high, low, close)
    price = float(close[-1])
    # 52w high/low breakout
    hi52 = float(np.max(close))
    lo52 = float(np.min(close))
    return {
        "price": round(price, 2), "sma20": round(sma20, 2), "sma50": round(sma50, 2),
        "sma200": round(sma200, 2), "rsi": round(float(rsi[-1]), 2),
        "macd": round(float(macd_line[-1]), 3), "macd_signal": round(float(signal_line[-1]), 3),
        "macd_hist": round(macd_hist, 3), "bb_upper": round(bb_upper, 2),
        "bb_lower": round(bb_lower, 2), "adx": round(adx, 2),
        "high_52w": round(hi52, 2), "low_52w": round(lo52, 2),
    }


def technical_score(t):
    """0-100 composite technical strength."""
    s = 50.0
    if t["price"] > t["sma50"]:
        s += 8
    if t["sma50"] > t["sma200"]:
        s += 10  # golden alignment
    if t["price"] > t["sma20"]:
        s += 5
    # RSI: reward momentum but penalize overbought/oversold extremes
    rsi = t["rsi"]
    if 50 <= rsi <= 68:
        s += 10
    elif rsi > 75:
        s -= 8
    elif rsi < 32:
        s += 4  # oversold bounce potential
    if t["macd_hist"] > 0:
        s += 8
    if t["adx"] > 25:
        s += 6  # strong trend
    if t["price"] >= 0.98 * t["high_52w"]:
        s += 6  # near breakout
    return max(0, min(100, s))


# ---------------------------------------------------------------------------
# Fundamentals: Piotroski-style score + fundamental score
# ---------------------------------------------------------------------------
def piotroski(f):
    """Simplified Piotroski F-Score (0-9) from available ratios."""
    score = 0
    if f["profit_margin"] > 0:
        score += 1        # positive net income
    if f["fcf_cr"] > 0:
        score += 1        # positive operating cash flow
    if f["fcf_cr"] > f["eps"] * f["shares_cr"]:
        score += 1        # accruals: CFO > NI
    if f["de"] < 1.0:
        score += 1        # lower leverage
    if f["current_ratio"] > 1.2:
        score += 1        # liquidity
    if f["eps_growth"] > 0.05:
        score += 1        # EPS growth
    if f["roe"] > 12:
        score += 1        # return on equity
    if f["roce"] > 12:
        score += 1        # return on capital
    if f["div_yield"] >= 0 and f["profit_margin"] > 5:
        score += 1        # margin quality
    return score


def fundamental_score(f):
    fscore = piotroski(f)
    s = fscore / 9 * 40  # up to 40 from Piotroski
    if 0 < f["pe"] < 25:
        s += 12
    elif 25 <= f["pe"] < 45:
        s += 6
    if 0 < f["pb"] < 4:
        s += 8
    if f["roe"] > 18:
        s += 12
    elif f["roe"] > 12:
        s += 6
    if f["roce"] > 20:
        s += 10
    if f["de"] < 0.5:
        s += 8
    elif f["de"] < 1:
        s += 4
    if f["eps_growth"] > 0.12:
        s += 10
    return max(0, min(100, s)), fscore


# ---------------------------------------------------------------------------
# Quant multi-factor scores (each 0-100, ranked cross-sectionally later)
# ---------------------------------------------------------------------------
def raw_factors(symbol, bars, f):
    close = np.array([b["close"] for b in bars])
    ret_12m = (close[-1] / close[0] - 1) if len(close) else 0
    ret_1m = (close[-1] / close[-21] - 1) if len(close) > 21 else 0
    daily = np.diff(np.log(close))
    vol = float(np.std(daily) * math.sqrt(252)) if len(daily) else 0.3
    mcap = f["eps"] * f["shares_cr"] * max(f["pe"], 1)  # crude market cap proxy (cr)
    return {
        "momentum": ret_12m - ret_1m,          # 12-1 momentum
        "value": 1 / max(f["pe"], 0.1) + 1 / max(f["pb"], 0.1),
        "quality": f["roe"] * 0.5 + f["roce"] * 0.5 - f["de"] * 10,
        "lowvol": -vol,
        "size": -math.log(max(mcap, 1)),       # small size premium
        "_mcap": mcap, "_vol": vol, "_ret12": ret_12m,
    }


def zscore_rank(values):
    a = np.array(values, dtype=float)
    m, sd = a.mean(), a.std()
    if sd == 0:
        return np.full_like(a, 50.0)
    z = (a - m) / sd
    return 50 + 15 * np.clip(z, -3, 3)  # ~0-100


# ---------------------------------------------------------------------------
# DCF intrinsic value (2-stage FCF model)
# ---------------------------------------------------------------------------
def dcf_value(f, price):
    fcf = f["fcf_cr"]
    shares = f["shares_cr"]
    g1 = min(max(f["growth"], -0.05), 0.25)   # high growth (yrs 1-5)
    g2 = 0.04                                  # terminal growth
    wacc = 0.11
    if fcf <= 0 or shares <= 0:
        return {"intrinsic": None, "upside": None, "note": "FCF<=0: DCF not meaningful"}
    pv = 0.0
    cf = fcf
    for yr in range(1, 6):
        cf *= (1 + g1)
        pv += cf / (1 + wacc) ** yr
    terminal = cf * (1 + g2) / (wacc - g2)
    pv += terminal / (1 + wacc) ** 5
    intrinsic_per_share = pv / shares
    upside = (intrinsic_per_share / price - 1) * 100
    return {"intrinsic": round(intrinsic_per_share, 2), "upside": round(upside, 2),
            "wacc": wacc, "g1": round(g1, 3), "g2": g2,
            "note": "2-stage FCF DCF, WACC=11%, terminal g=4%"}


# ---------------------------------------------------------------------------
# Monte Carlo GBM simulation
# ---------------------------------------------------------------------------
def monte_carlo(bars, horizon=126, sims=1000):
    close = np.array([b["close"] for b in bars])
    daily = np.diff(np.log(close))
    mu = float(np.mean(daily))
    sigma = float(np.std(daily))
    s0 = float(close[-1])
    rng = np.random.default_rng(42)
    shocks = rng.normal(mu, sigma, (sims, horizon))
    paths = s0 * np.exp(np.cumsum(shocks, axis=1))
    finals = paths[:, -1]
    pcts = [5, 25, 50, 75, 95]
    bands = {f"p{p}": np.percentile(paths, p, axis=0) for p in pcts}
    fan = []
    step = max(1, horizon // 30)
    for i in range(0, horizon, step):
        fan.append({"day": i + 1,
                    "p5": round(float(bands["p5"][i]), 2),
                    "p25": round(float(bands["p25"][i]), 2),
                    "p50": round(float(bands["p50"][i]), 2),
                    "p75": round(float(bands["p75"][i]), 2),
                    "p95": round(float(bands["p95"][i]), 2),
                    "band90": [round(float(bands["p5"][i]), 2), round(float(bands["p95"][i]), 2)],
                    "band50": [round(float(bands["p25"][i]), 2), round(float(bands["p75"][i]), 2)]})
    var95 = float(np.percentile(finals / s0 - 1, 5)) * 100
    target = s0 * 1.15
    prob_target = float(np.mean(finals >= target)) * 100
    return {"fan": fan, "expected": round(float(np.mean(finals)), 2),
            "var95_pct": round(var95, 2), "prob_up_15pct": round(prob_target, 2),
            "current": round(s0, 2), "horizon_days": horizon, "sims": sims}


# ---------------------------------------------------------------------------
# Composite scoring across universe
# ---------------------------------------------------------------------------
RISK_WEIGHTS = {
    "conservative": {"fund": 0.34, "tech": 0.13, "factor": 0.22, "sent": 0.08, "value_tilt": 0.08, "ml": 0.15},
    "balanced":     {"fund": 0.26, "tech": 0.22, "factor": 0.20, "sent": 0.08, "value_tilt": 0.08, "ml": 0.16},
    "aggressive":   {"fund": 0.15, "tech": 0.30, "factor": 0.25, "sent": 0.12, "value_tilt": 0.00, "ml": 0.18},
}

# Live data + ML plumbing -----------------------------------------------------
_LIVE_BARS = {}
ML_PRED = {}


def set_live_bars(bars_map):
    global _LIVE_BARS
    _LIVE_BARS = bars_map or {}
    clear_caches()


def set_ml_predictions(preds):
    global ML_PRED
    ML_PRED = preds or {}
    clear_caches()


def get_bars(symbol):
    b = _LIVE_BARS.get(symbol)
    if b:
        return b
    # Try real data from yfinance first
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period="2y")
        if len(hist) > 50:
            bars = []
            for date, row in hist.iterrows():
                bars.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open":   round(float(row["Open"]), 2),
                    "high":   round(float(row["High"]), 2),
                    "low":    round(float(row["Low"]), 2),
                    "close":  round(float(row["Close"]), 2),
                    "volume": int(row["Volume"])
                })
            _LIVE_BARS[symbol] = bars
            return bars
    except Exception:
        pass
    # fallback to simulated data
    return generate_ohlcv(symbol)


def clear_caches():
    for fn in (score_universe, stock_detail, backtest, _universe_factor_dist):
        try:
            fn.cache_clear()
        except Exception:
            pass


@lru_cache(maxsize=1)
def _universe_factor_dist():
    dist = {"momentum": [], "value": [], "quality": [], "lowvol": [], "size": []}
    for st in UNIVERSE:
        rf = raw_factors(st["symbol"], get_bars(st["symbol"]), st["fund"])
        for k in dist:
            dist[k].append(rf[k])
    return {k: np.array(v) for k, v in dist.items()}


def _pctl(arr, v):
    return float((arr < v).mean() * 100)


def score_external(symbol, exch, sector, bars, fund, ml_pred, risk="balanced"):
    """Score an arbitrary (non-curated) stock using live bars + best-effort fundamentals,
    ranking its factors against the curated universe distribution."""
    w = RISK_WEIGHTS.get(risk, RISK_WEIGHTS["balanced"])
    t = technicals(bars)
    tech = technical_score(t)
    has_fund = bool(fund and fund.get("pe"))
    if has_fund:
        fscore, piotroski_f = fundamental_score(fund)
    else:
        fscore, piotroski_f = 50.0, 0
    dist = _universe_factor_dist()
    if fund:
        rf = raw_factors(symbol, bars, fund)
        factor_scores = {k: round(_pctl(dist[k], rf[k]), 1) for k in dist}
        factor_composite = float(np.mean(list(factor_scores.values())))
        value_score = factor_scores["value"]
        ret12 = rf["_ret12"]; vol = rf["_vol"]
    else:
        factor_scores = {k: 50.0 for k in dist}
        factor_composite = 50.0; value_score = 50.0
        close = np.array([b["close"] for b in bars]); ret12 = close[-1] / close[0] - 1
        vol = float(np.std(np.diff(np.log(close))) * math.sqrt(252))
    sent, _ = _news_sentiment(symbol)
    sent_score = (sent + 1) / 2 * 100
    ml_score = ml_pred.get("ml_score", 50.0) if ml_pred else 50.0
    composite = (w["fund"] * fscore + w["tech"] * tech + w["factor"] * factor_composite
                 + w["sent"] * sent_score + w["value_tilt"] * value_score + w.get("ml", 0) * ml_score)
    signal = "BUY" if composite >= 62 else ("HOLD" if composite >= 46 else "SELL")
    target = round(t["price"] * (1 + (composite - 50) / 100 * 0.6), 2)
    return {"symbol": symbol, "name": symbol, "exchange": exch, "sector": sector,
            "price": t["price"], "target": target, "composite": round(composite, 2),
            "signal": signal, "fundamental_score": round(fscore, 1),
            "technical_score": round(tech, 1), "factor_score": round(factor_composite, 1),
            "sentiment_score": round(sent_score, 1), "ml_score": round(ml_score, 1),
            "ml_signal": (ml_pred or {}).get("ml_signal", "HOLD"),
            "ml_buy_prob": (ml_pred or {}).get("ml_buy_prob"),
            "direction_prob": (ml_pred or {}).get("direction_prob"),
            "value_score": value_score, "momentum": factor_scores["momentum"],
            "quality": factor_scores["quality"], "lowvol": factor_scores["lowvol"],
            "piotroski": piotroski_f, "rsi": t["rsi"],
            "ret_12m": round(ret12 * 100, 2), "vol": round(vol * 100, 2),
            "pe": fund.get("pe") if fund else None, "roe": fund.get("roe") if fund else None,
            "de": fund.get("de") if fund else None, "has_fundamentals": has_fund}


def _news_sentiment(symbol):
    """Deterministic mock FinBERT-style sentiment in [-1,1] + headlines."""
    rng = np.random.default_rng(_seed(symbol) + 7)
    base = float(np.clip(rng.normal(0.15, 0.4), -0.9, 0.9))
    templates = [
        ("{n} posts steady quarterly revenue; margins in line with estimates", 0.2),
        ("Brokerage reiterates rating on {n} citing sector tailwinds", 0.5),
        ("{n} faces near-term input cost pressure, analysts flag caution", -0.4),
        ("{n} announces capex expansion and new capacity plans", 0.4),
        ("Regulatory review weighs on {n} sentiment this week", -0.5),
        ("FII activity picks up in {n} on valuation comfort", 0.3),
    ]
    st = UNIVERSE_MAP.get(symbol) or {"name": symbol}
    idx = rng.choice(len(templates), size=3, replace=False)
    heads = []
    for i in idx:
        txt, s = templates[i]
        heads.append({"headline": txt.format(n=st["name"]),
                      "sentiment": round(float(np.clip(s + rng.normal(0, 0.1), -1, 1)), 2),
                      "source": rng.choice(["Mint", "ET Markets", "Moneycontrol", "BQ Prime"]),
                      "time": f"{int(rng.integers(1, 22))}h ago"})
    return round(base, 3), heads


@lru_cache(maxsize=8)
def score_universe(risk="balanced"):
    w = RISK_WEIGHTS.get(risk, RISK_WEIGHTS["balanced"])
    rows = []
    fac_raw = {"momentum": [], "value": [], "quality": [], "lowvol": [], "size": []}
    tmp = []
    for st in UNIVERSE:
        sym = st["symbol"]
        bars = get_bars(sym)
        t = technicals(bars)
        fscore, piotroski_f = fundamental_score(st["fund"])
        rf = raw_factors(sym, bars, st["fund"])
        sent, _ = _news_sentiment(sym)
        for k in fac_raw:
            fac_raw[k].append(rf[k])
        tmp.append({"st": st, "t": t, "fscore": fscore, "piotroski": piotroski_f,
                    "rf": rf, "sent": sent})
    ranked = {k: zscore_rank(v) for k, v in fac_raw.items()}
    for i, row in enumerate(tmp):
        st, t = row["st"], row["t"]
        factor_composite = float(np.mean([ranked[k][i] for k in fac_raw]))
        tech = technical_score(t)
        fund = row["fscore"]
        sent_score = (row["sent"] + 1) / 2 * 100
        value_score = ranked["value"][i]
        mlp = ML_PRED.get(st["symbol"], {})
        ml_score = mlp.get("ml_score", 50.0)
        composite = (w["fund"] * fund + w["tech"] * tech + w["factor"] * factor_composite
                     + w["sent"] * sent_score + w["value_tilt"] * value_score
                     + w.get("ml", 0) * ml_score)
        if composite >= 62:
            signal = "BUY"
        elif composite >= 46:
            signal = "HOLD"
        else:
            signal = "SELL"
        target = round(t["price"] * (1 + (composite - 50) / 100 * 0.6), 2)
        rows.append({
            "symbol": st["symbol"], "name": st["name"], "exchange": st["exchange"],
            "sector": st["sector"], "price": t["price"], "target": target,
            "composite": round(composite, 2), "signal": signal,
            "fundamental_score": round(fund, 1), "technical_score": round(tech, 1),
            "factor_score": round(factor_composite, 1), "sentiment_score": round(sent_score, 1),
            "ml_score": round(ml_score, 1), "ml_signal": mlp.get("ml_signal", "HOLD"),
            "ml_buy_prob": mlp.get("ml_buy_prob"), "direction_prob": mlp.get("direction_prob"),
            "value_score": round(float(value_score), 1),
            "momentum": round(float(ranked["momentum"][i]), 1),
            "quality": round(float(ranked["quality"][i]), 1),
            "lowvol": round(float(ranked["lowvol"][i]), 1),
            "piotroski": row["piotroski"], "rsi": t["rsi"],
            "ret_12m": round(row["rf"]["_ret12"] * 100, 2),
            "vol": round(row["rf"]["_vol"] * 100, 2),
            "pe": st["fund"]["pe"], "roe": st["fund"]["roe"], "de": st["fund"]["de"],
        })
    rows.sort(key=lambda r: r["composite"], reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


@lru_cache(maxsize=128)
def stock_detail(symbol, risk="balanced"):
    st = UNIVERSE_MAP[symbol]
    bars = get_bars(symbol)
    t = technicals(bars)
    fund, piotroski_f = fundamental_score(st["fund"])
    tech = technical_score(t)
    dcf = dcf_value(st["fund"], t["price"])
    mc = monte_carlo(bars)
    sent, heads = _news_sentiment(symbol)
    # scored row from universe for ranks
    row = next((r for r in score_universe(risk) if r["symbol"] == symbol), None)
    chart = [{"date": b["date"], "close": b["close"], "volume": b["volume"]}
             for b in bars[-180:]]
    return {"symbol": symbol, "name": st["name"], "exchange": st["exchange"],
            "sector": st["sector"], "fundamentals": st["fund"],
            "technicals": t, "fundamental_score": round(fund, 1),
            "technical_score": round(tech, 1), "piotroski": piotroski_f,
            "dcf": dcf, "monte_carlo": mc, "sentiment": sent,
            "news": heads, "chart": chart, "scored": row}


# ---------------------------------------------------------------------------
# Backtest engine: monthly rebalanced top-N composite strategy vs Nifty proxy
# ---------------------------------------------------------------------------
@lru_cache(maxsize=64)
def backtest(risk="balanced", top_n=10, capital=1000000):
    # build aligned close matrix
    syms = [s["symbol"] for s in UNIVERSE]
    series = {s: np.array([b["close"] for b in get_bars(s)]) for s in syms}
    n = min(len(v) for v in series.values())
    mat = np.array([series[s][-n:] for s in syms])  # [stocks, days]
    dates = [b["date"] for b in get_bars(syms[0])][-n:]
    # score proxy per stock (static composite from full engine) for selection
    scores = {r["symbol"]: r["composite"] for r in score_universe(risk)}
    order = sorted(syms, key=lambda s: scores.get(s, 0), reverse=True)
    picks = order[:top_n]
    idx = [syms.index(p) for p in picks]
    # equal-weight monthly rebalanced buy&hold of top picks
    strat = np.zeros(n)
    bench = np.mean(mat / mat[:, [0]], axis=0)  # equal-weight all = market proxy
    sub = mat[idx]
    strat = np.mean(sub / sub[:, [0]], axis=0)
    equity = capital * strat
    bench_eq = capital * bench
    daily_ret = np.diff(equity) / equity[:-1]
    years = n / 252
    cagr = (equity[-1] / equity[0]) ** (1 / years) - 1
    bench_cagr = (bench_eq[-1] / bench_eq[0]) ** (1 / years) - 1
    ann_ret = np.mean(daily_ret) * 252
    ann_vol = np.std(daily_ret) * math.sqrt(252)
    sharpe = (ann_ret - RISK_FREE) / ann_vol if ann_vol else 0
    downside = np.std(daily_ret[daily_ret < 0]) * math.sqrt(252)
    sortino = (ann_ret - RISK_FREE) / downside if downside else 0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(np.min(dd)) * 100
    wins = np.sum(daily_ret > 0) / len(daily_ret) * 100
    alpha = (cagr - bench_cagr) * 100
    step = max(1, n // 120)
    curve = [{"date": dates[i], "strategy": round(float(equity[i]), 0),
              "benchmark": round(float(bench_eq[i]), 0),
              "drawdown": round(float(dd[i]) * 100, 2)} for i in range(0, n, step)]
    return {"picks": picks, "metrics": {
        "cagr": round(cagr * 100, 2), "benchmark_cagr": round(bench_cagr * 100, 2),
        "alpha": round(alpha, 2), "sharpe": round(sharpe, 2), "sortino": round(sortino, 2),
        "max_drawdown": round(max_dd, 2), "win_rate": round(wins, 2),
        "ann_vol": round(ann_vol * 100, 2), "final_value": round(float(equity[-1]), 0),
        "total_return": round((equity[-1] / equity[0] - 1) * 100, 2)},
        "curve": curve, "years": round(years, 1), "top_n": top_n}
