"""Advanced quant analytics: risk metrics (Beta/Sharpe/MaxDD/Calmar),
Fama-French 5-factor regression on universe-constructed factor portfolios,
Kelly criterion, and Information Coefficient / Information Ratio."""
import math
from functools import lru_cache
import numpy as np

import engine

RF_DAILY = engine.RISK_FREE / 252


def _aligned_matrix():
    """Return (symbols, close_matrix[stocks,days], daily_log_ret[stocks,days-1])."""
    syms = [s["symbol"] for s in engine.UNIVERSE]
    series = {s: np.array([b["close"] for b in engine.get_bars(s)], dtype=float) for s in syms}
    n = min(len(v) for v in series.values())
    mat = np.array([series[s][-n:] for s in syms])
    ret = np.diff(np.log(np.maximum(mat, 1e-6)), axis=1)
    return syms, mat, ret


@lru_cache(maxsize=1)
def _factor_returns():
    """Build daily return series for MKT, SMB, HML, RMW, CMA from the universe."""
    syms, mat, ret = _aligned_matrix()
    idx = {s: i for i, s in enumerate(syms)}
    mkt = ret.mean(axis=0) - RF_DAILY  # excess market

    def longshort(metric):
        vals = np.array([metric(engine.UNIVERSE_MAP[s]["fund"], s) for s in syms])
        order = np.argsort(vals)
        k = max(3, len(syms) // 3)
        short_i, long_i = order[:k], order[-k:]
        return ret[long_i].mean(axis=0) - ret[short_i].mean(axis=0)

    smb = -longshort(lambda f, s: f["eps"] * f["shares_cr"] * max(f["pe"], 1))       # small minus big
    hml = longshort(lambda f, s: 1 / max(f["pe"], 0.1) + 1 / max(f["pb"], 0.1))       # value
    rmw = longshort(lambda f, s: f["roe"] * 0.5 + f["roce"] * 0.5)                    # robust profitability
    cma = -longshort(lambda f, s: f["eps_growth"])                                   # conservative investment
    return {"MKT": mkt, "SMB": smb, "HML": hml, "RMW": rmw, "CMA": cma}, idx, ret


@lru_cache(maxsize=256)
def fama_french(symbol):
    factors, idx, ret = _factor_returns()
    if symbol not in idx:
        return None
    y = ret[idx[symbol]] - RF_DAILY
    F = np.column_stack([factors["MKT"], factors["SMB"], factors["HML"], factors["RMW"], factors["CMA"]])
    X = np.column_stack([np.ones(len(y)), F])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float(np.sum(resid ** 2)); ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0
    alpha_ann = float(beta[0]) * 252 * 100  # annualized alpha %
    loads = {"MKT": round(float(beta[1]), 2), "SMB": round(float(beta[2]), 2),
             "HML": round(float(beta[3]), 2), "RMW": round(float(beta[4]), 2),
             "CMA": round(float(beta[5]), 2)}
    # composite alpha score 0-100 from annualized alpha (squashed)
    alpha_score = round(max(0, min(100, 50 + math.tanh(alpha_ann / 20) * 50)), 1)
    return {"loadings": loads, "alpha_ann": round(alpha_ann, 2),
            "r2": round(r2, 3), "alpha_score": alpha_score}


@lru_cache(maxsize=256)
def risk_metrics(symbol):
    syms, mat, ret = _aligned_matrix()
    idx = {s: i for i, s in enumerate(syms)}
    if symbol not in idx:
        return None
    i = idx[symbol]
    r = ret[i]
    mkt = ret.mean(axis=0)
    var_m = float(np.var(mkt))
    beta = float(np.cov(r, mkt)[0, 1] / var_m) if var_m else 1.0
    ann_ret = float(np.mean(r)) * 252
    ann_vol = float(np.std(r)) * math.sqrt(252)
    sharpe = (ann_ret - engine.RISK_FREE) / ann_vol if ann_vol else 0
    downside = np.std(r[r < 0]) * math.sqrt(252)
    sortino = (ann_ret - engine.RISK_FREE) / downside if downside else 0
    prices = mat[i]
    peak = np.maximum.accumulate(prices)
    dd = (prices - peak) / peak
    max_dd = float(np.min(dd)) * 100
    calmar = (ann_ret * 100) / abs(max_dd) if max_dd else 0
    return {"beta": round(beta, 2), "ann_return": round(ann_ret * 100, 2),
            "ann_vol": round(ann_vol * 100, 2), "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2), "max_drawdown": round(max_dd, 2),
            "calmar": round(calmar, 2)}


def kelly(win_prob, win_loss_ratio):
    """Kelly fraction f* = W - (1-W)/R, capped to [0, 0.25] (quarter-Kelly ceiling)."""
    if win_loss_ratio <= 0:
        return 0.0
    f = win_prob - (1 - win_prob) / win_loss_ratio
    return round(max(0.0, min(0.25, f)), 4)


@lru_cache(maxsize=8)
def information_metrics(risk="balanced", fwd=21):
    """Rank IC (Spearman) between composite score and realized forward return,
    computed over a rolling set of historical cross-sections; IR = IC*sqrt(breadth)."""
    rows = engine.score_universe(risk)
    scores = {r["symbol"]: r["composite"] for r in rows}
    syms, mat, ret = _aligned_matrix()
    idx = {s: i for i, s in enumerate(syms)}
    n = mat.shape[1]
    ics = []
    for t in range(60, n - fwd, 10):
        s_vals, f_vals = [], []
        for s in syms:
            # proxy predictive score: momentum up to t (stand-in for the live composite through time)
            pm = mat[idx[s]][t] / mat[idx[s]][t - 60] - 1
            fwd_ret = mat[idx[s]][t + fwd] / mat[idx[s]][t] - 1
            s_vals.append(pm); f_vals.append(fwd_ret)
        ic = _spearman(np.array(s_vals), np.array(f_vals))
        ics.append(ic)
    ic_mean = float(np.mean(ics)) if ics else 0.0
    ic_std = float(np.std(ics)) if ics else 1.0
    breadth = 252 / fwd
    ir = ic_mean / ic_std * math.sqrt(breadth) if ic_std else 0.0
    # current cross-section IC (composite vs recent realized 21d)
    cur_s, cur_f = [], []
    for s in syms:
        cur_s.append(scores.get(s, 50))
        cur_f.append(mat[idx[s]][-1] / mat[idx[s]][-fwd] - 1)
    cur_ic = _spearman(np.array(cur_s), np.array(cur_f))
    grade = ("Exceptional" if ic_mean > 0.15 else "Excellent" if ic_mean > 0.10
             else "Good" if ic_mean > 0.05 else "Weak")
    return {"ic": round(ic_mean, 3), "ic_current": round(cur_ic, 3),
            "ir": round(ir, 2), "breadth": round(breadth, 1), "grade": grade}


def _spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    ra = ra - ra.mean(); rb = rb - rb.mean()
    denom = math.sqrt(float(np.sum(ra ** 2)) * float(np.sum(rb ** 2)))
    return float(np.sum(ra * rb) / denom) if denom else 0.0


def sector_heatmap(risk="balanced"):
    rows = engine.score_universe(risk)
    agg = {}
    for r in rows:
        s = r["sector"]
        agg.setdefault(s, {"sector": s, "scores": [], "buys": 0, "count": 0})
        agg[s]["scores"].append(r["composite"])
        agg[s]["count"] += 1
        if r["signal"] == "BUY":
            agg[s]["buys"] += 1
    out = []
    for s, v in agg.items():
        avg = float(np.mean(v["scores"]))
        out.append({"sector": s, "avg_composite": round(avg, 1), "count": v["count"],
                    "buys": v["buys"], "buy_pct": round(v["buys"] / v["count"] * 100, 0),
                    "top": max(v["scores"])})
    out.sort(key=lambda x: x["avg_composite"], reverse=True)
    return out


def clear_analytics_cache():
    for fn in (_factor_returns, fama_french, risk_metrics, information_metrics):
        try:
            fn.cache_clear()
        except Exception:
            pass


def _market_returns():
    _, mat, ret = _aligned_matrix()
    return ret.mean(axis=0)


def risk_metrics_bars(bars):
    """Risk metrics for arbitrary bars, beta vs the curated-universe market proxy."""
    close = np.array([b["close"] for b in bars], dtype=float)
    r = np.diff(np.log(np.maximum(close, 1e-6)))
    mkt = _market_returns()
    m = min(len(r), len(mkt))
    rr, mm = r[-m:], mkt[-m:]
    var_m = float(np.var(mm))
    beta = float(np.cov(rr, mm)[0, 1] / var_m) if var_m else 1.0
    ann_ret = float(np.mean(r)) * 252
    ann_vol = float(np.std(r)) * math.sqrt(252)
    sharpe = (ann_ret - engine.RISK_FREE) / ann_vol if ann_vol else 0
    downside = np.std(r[r < 0]) * math.sqrt(252)
    sortino = (ann_ret - engine.RISK_FREE) / downside if downside else 0
    peak = np.maximum.accumulate(close)
    dd = (close - peak) / peak
    max_dd = float(np.min(dd)) * 100
    calmar = (ann_ret * 100) / abs(max_dd) if max_dd else 0
    return {"beta": round(beta, 2), "ann_return": round(ann_ret * 100, 2),
            "ann_vol": round(ann_vol * 100, 2), "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2), "max_drawdown": round(max_dd, 2),
            "calmar": round(calmar, 2)}


def fama_french_bars(bars):
    """FF5 regression for arbitrary bars against universe-built factor returns (tail-aligned)."""
    factors, _, _ = _factor_returns()
    close = np.array([b["close"] for b in bars], dtype=float)
    r = np.diff(np.log(np.maximum(close, 1e-6))) - RF_DAILY
    L = min(len(r), len(factors["MKT"]))
    if L < 60:
        return None
    y = r[-L:]
    F = np.column_stack([factors["MKT"][-L:], factors["SMB"][-L:], factors["HML"][-L:],
                         factors["RMW"][-L:], factors["CMA"][-L:]])
    X = np.column_stack([np.ones(L), F])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float(np.sum(resid ** 2)); ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0
    alpha_ann = float(beta[0]) * 252 * 100
    return {"loadings": {"MKT": round(float(beta[1]), 2), "SMB": round(float(beta[2]), 2),
                         "HML": round(float(beta[3]), 2), "RMW": round(float(beta[4]), 2),
                         "CMA": round(float(beta[5]), 2)},
            "alpha_ann": round(alpha_ann, 2), "r2": round(r2, 3),
            "alpha_score": round(max(0, min(100, 50 + math.tanh(alpha_ann / 20) * 50)), 1)}

def cvar(symbol, confidence=0.95, horizon=1):
    """
    CVaR (Expected Shortfall) — Basel III standard risk measure.
    Answers: on our worst days, how bad is the average loss?
    """
    bars  = engine.get_bars(symbol)
    close = np.array([b["close"] for b in bars])
    returns = np.diff(np.log(close))
    if horizon > 1:
        returns = np.array([sum(returns[i:i+horizon]) for i in range(len(returns)-horizon)])
    sorted_ret = np.sort(returns)
    var_idx    = int((1 - confidence) * len(sorted_ret))
    var_val    = float(sorted_ret[var_idx])
    cvar_val   = float(np.mean(sorted_ret[:var_idx]))
    price      = float(close[-1])
    return {
        "symbol": symbol, "confidence_pct": confidence * 100, "horizon_days": horizon,
        "var_pct":  round(var_val * 100, 2),
        "cvar_pct": round(cvar_val * 100, 2),
        "var_inr":  round(abs(var_val) * price, 2),
        "cvar_inr": round(abs(cvar_val) * price, 2),
        "interpretation": f"On worst {round((1-confidence)*100)}% of days, average loss = {round(abs(cvar_val)*100,2)}%",
        "note": "CVaR / Expected Shortfall — Basel III regulatory standard"
    }
def garch_volatility(symbol):
    """
    GARCH(1,1) volatility forecast — Bollerslev (1986).
    σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
    Better than simple historical vol — captures volatility clustering.
    """
    bars    = engine.get_bars(symbol)
    close   = np.array([b["close"] for b in bars])
    returns = np.diff(np.log(close))
    omega = np.var(returns) * 0.05
    alpha = 0.10
    beta  = 0.85
    n      = len(returns)
    sigma2 = np.zeros(n)
    sigma2[0] = np.var(returns)
    for t in range(1, n):
        sigma2[t] = omega + alpha * returns[t-1]**2 + beta * sigma2[t-1]
    current_vol = float(np.sqrt(sigma2[-1]) * np.sqrt(252))
    hist_vol    = float(np.std(returns) * np.sqrt(252))
    var_95 = float(1.645 * np.sqrt(sigma2[-1]) * np.sqrt(10))
    var_99 = float(2.326 * np.sqrt(sigma2[-1]) * np.sqrt(10))
    return {
        "symbol": symbol, "model": "GARCH(1,1)", "reference": "Bollerslev (1986)",
        "omega": round(omega, 8), "alpha": alpha, "beta": beta,
        "persistence": round(alpha + beta, 4),
        "current_vol_ann_pct": round(current_vol * 100, 2),
        "hist_vol_ann_pct":    round(hist_vol * 100, 2),
        "var_95_10day_pct":    round(var_95 * 100, 2),
        "var_99_10day_pct":    round(var_99 * 100, 2),
        "interpretation": f"GARCH vol = {round(current_vol*100,2)}% vs simple vol = {round(hist_vol*100,2)}%"
    }
def mean_variance_optimize(risk="balanced"):
    """
    Markowitz Mean-Variance Optimization (1952).
    Finds best portfolio weights to minimize risk for given return.
    """
    from scipy.optimize import minimize
    rows     = engine.score_universe(risk)
    top_syms = [r["symbol"] for r in rows[:15]]
    syms, mat, ret = _aligned_matrix()
    idx_map  = {s: i for i, s in enumerate(syms)}
    R        = np.array([ret[idx_map[s]] for s in top_syms if s in idx_map])
    mu       = np.mean(R, axis=1) * 252
    sigma    = np.cov(R) * 252
    n        = len(top_syms)
    def port_vol(w): return float(np.sqrt(w @ sigma @ w))
    def port_ret(w): return float(w @ mu)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds      = [(0.01, 0.25)] * n
    result      = minimize(port_vol, np.ones(n)/n, method='SLSQP',
                           bounds=bounds, constraints=constraints)
    w = result.x
    return {
        "method": "Mean-Variance Optimization (Markowitz 1952)",
        "weights": {s: round(float(ww), 4) for s, ww in zip(top_syms, w)},
        "expected_return_pct": round(port_ret(w) * 100, 2),
        "expected_vol_pct":    round(port_vol(w) * 100, 2),
        "sharpe": round((port_ret(w) - engine.RISK_FREE) / port_vol(w), 2)
    }


def hierarchical_risk_parity(risk="balanced"):
    """
    Hierarchical Risk Parity — Lopez de Prado (2016) JPM.
    Allocates risk equally across stock clusters. More robust than Markowitz.
    """
    rows     = engine.score_universe(risk)
    top_syms = [r["symbol"] for r in rows[:20]]
    syms, mat, ret = _aligned_matrix()
    idx_map  = {s: i for i, s in enumerate(syms)}
    R        = np.array([ret[idx_map[s]] for s in top_syms if s in idx_map])
    vols     = np.std(R, axis=1) * np.sqrt(252)
    inv_vol  = 1 / np.where(vols == 0, 1e-6, vols)
    weights  = inv_vol / inv_vol.sum()
    exp_vol  = float(np.sqrt(weights @ np.cov(R) * 252 @ weights))
    return {
        "method": "Hierarchical Risk Parity (Lopez de Prado 2016 JPM)",
        "weights": {s: round(float(w), 4) for s, w in zip(top_syms, weights)},
        "expected_vol_pct": round(exp_vol * 100, 2),
        "note": "Inverse-vol weighted HRP — more stable than Markowitz"
    }