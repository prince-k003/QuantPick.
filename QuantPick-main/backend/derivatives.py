"""
Derivatives Pricing Module — QuantPick
Black-Scholes, Binomial Tree, Greeks, Implied Volatility
"""
import math
import numpy as np
from scipy.stats import norm


def black_scholes(S, K, T, r, sigma, option_type="call"):
    """
    Black-Scholes-Merton (1973) option pricing.
    S=stock price, K=strike, T=time in years, r=risk-free rate, sigma=volatility
    """
    if T <= 0 or sigma <= 0:
        intrinsic = max(0, S - K) if option_type == "call" else max(0, K - S)
        return {"price": round(intrinsic, 2), "d1": 0, "d2": 0, "model": "Black-Scholes-Merton (1973)"}
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == "call":
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return {"price": round(price, 2), "d1": round(d1, 4), "d2": round(d2, 4), "model": "Black-Scholes-Merton (1973)"}


def greeks(S, K, T, r, sigma, option_type="call"):
    """Option Greeks: Delta, Gamma, Vega, Theta, Rho"""
    if T <= 0 or sigma <= 0:
        return {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "rho": 0}
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    phi_d1 = norm.pdf(d1)
    if option_type == "call":
        delta    = norm.cdf(d1)
        rho_val  = K * T * math.exp(-r * T) * norm.cdf(d2) / 100
        theta    = (-(S * phi_d1 * sigma) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
    else:
        delta    = norm.cdf(d1) - 1
        rho_val  = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100
        theta    = (-(S * phi_d1 * sigma) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365
    gamma = phi_d1 / (S * sigma * math.sqrt(T))
    vega  = S * phi_d1 * math.sqrt(T) / 100
    return {
        "delta": round(delta, 4), "gamma": round(gamma, 6),
        "vega": round(vega, 4),   "theta": round(theta, 4), "rho": round(rho_val, 4),
        "interpretation": {
            "delta": f"Price moves ₹{round(abs(delta),2)} per ₹1 stock move",
            "vega":  f"Price changes ₹{round(vega,4)} per 1% vol change",
            "theta": f"Loses ₹{abs(round(theta,4))} per day (time decay)"
        }
    }


def binomial_tree(S, K, T, r, sigma, n=100, option_type="call", style="european"):
    """CRR Binomial Tree (1979) — handles American options"""
    dt = T / n
    u  = math.exp(sigma * math.sqrt(dt))
    d  = 1 / u
    p  = (math.exp(r * dt) - d) / (u - d)
    ST = np.array([S * u**j * d**(n - j) for j in range(n + 1)])
    V  = np.maximum(ST - K, 0) if option_type == "call" else np.maximum(K - ST, 0)
    disc = math.exp(-r * dt)
    for i in range(n - 1, -1, -1):
        ST = np.array([S * u**j * d**(i - j) for j in range(i + 1)])
        V  = disc * (p * V[1:i+2] + (1 - p) * V[:i+1])
        if style == "american":
            V = np.maximum(V, ST - K) if option_type == "call" else np.maximum(V, K - ST)
    return {"price": round(float(V[0]), 2), "u": round(u,4), "d": round(d,4), "p": round(p,4),
            "model": f"CRR Binomial Tree ({n} steps, {style})", "reference": "Cox, Ross, Rubinstein (1979)"}


def implied_volatility(market_price, S, K, T, r, option_type="call"):
    """Newton-Raphson IV solver — finds volatility from market price"""
    sigma = 0.3
    for _ in range(100):
        bs   = black_scholes(S, K, T, r, sigma, option_type)
        g    = greeks(S, K, T, r, sigma, option_type)
        vega = g["vega"] * 100
        if abs(vega) < 1e-10:
            break
        diff = market_price - bs["price"]
        if abs(diff) < 1e-5:
            break
        sigma += diff / vega
        sigma = max(0.001, min(sigma, 5.0))
    return {"implied_vol_pct": round(sigma * 100, 2), "sigma": round(sigma, 5)}


def put_call_parity(call_price, put_price, S, K, T, r):
    """Put-Call Parity check: C - P = S - Ke^(-rT). Violation = arbitrage."""
    lhs  = call_price - put_price
    rhs  = S - K * math.exp(-r * T)
    diff = abs(lhs - rhs)
    return {"lhs": round(lhs,2), "rhs": round(rhs,2),
            "difference": round(diff,4), "arbitrage_exists": diff > 1.0,
            "formula": "C - P = S - Ke^(-rT)"}