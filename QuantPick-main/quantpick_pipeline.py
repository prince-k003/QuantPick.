"""
QuantPick — Standalone Quant Pipeline (runnable module / notebook cell)
========================================================================
This script reproduces the full QuantPick hybrid stock-picking pipeline
outside the web app. It reuses the same engine used by the FastAPI backend,
so the maths is identical to what the dashboard shows.

Run:
    cd /app/backend
    python ../quantpick_pipeline.py

Pipeline stages (matching the problem statement phases):
  1. Data layer            -> seeded NSE+BSE universe + deterministic OHLCV
  2. Fundamental screener  -> Piotroski F-Score + valuation/quality scoring
  3. DCF valuation         -> 2-stage FCF intrinsic value vs market price
  4. Monte Carlo           -> GBM price simulation, VaR(95), P(target)
  5. Technical signals     -> RSI, MACD, Bollinger, ADX, MA crossovers
  6. Quant factors         -> Momentum / Value / Quality / LowVol / Size z-scores
  7. Composite score       -> risk-weighted blend -> ranked Buy/Hold/Sell list
  8. Backtest              -> Top-N strategy vs market: CAGR, Sharpe, Sortino, MDD

NOTE: For a production system, swap `engine.generate_ohlcv` / the seeded
`engine.UNIVERSE` for live yfinance / NSEpy / Alpha Vantage ingestion, and
plug an XGBoost/LightGBM classifier + LSTM + FinBERT sentiment into the
composite blend. The composite architecture below is model-agnostic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
import engine  # noqa: E402


def stage_screen(risk="balanced", top=10):
    print(f"\n{'='*70}\n[1-7] SCORING UNIVERSE  (risk profile = {risk})\n{'='*70}")
    rows = engine.score_universe(risk)
    print(f"Universe: {len(rows)} equities across {len(engine.SECTORS)} sectors\n")
    hdr = f"{'#':>2} {'SYM':<11}{'SIG':<5}{'COMP':>6}{'FUND':>6}{'TECH':>6}{'FACT':>6}{'PIO':>5}{'RSI':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows[:top]:
        print(f"{r['rank']:>2} {r['symbol']:<11}{r['signal']:<5}{r['composite']:>6}"
              f"{r['fundamental_score']:>6}{r['technical_score']:>6}{r['factor_score']:>6}"
              f"{r['piotroski']:>4}/9{r['rsi']:>7}")
    return rows


def stage_deep_dive(symbol, risk="balanced"):
    print(f"\n{'='*70}\n[3-4] DEEP DIVE: {symbol}\n{'='*70}")
    d = engine.stock_detail(symbol, risk)
    t, dcf, mc = d["technicals"], d["dcf"], d["monte_carlo"]
    print(f"{d['name']} ({symbol}, {d['exchange']}) | {d['sector']} | LTP Rs {t['price']}")
    print(f"  Technicals : RSI {t['rsi']} | MACD_hist {t['macd_hist']} | ADX {t['adx']} "
          f"| SMA50 {t['sma50']} SMA200 {t['sma200']}")
    print(f"  DCF        : intrinsic Rs {dcf.get('intrinsic')} | upside {dcf.get('upside')}% "
          f"({dcf.get('note')})")
    print(f"  MonteCarlo : E[S_T] Rs {mc['expected']} | VaR95 {mc['var95_pct']}% "
          f"| P(+15%) {mc['prob_up_15pct']}% over {mc['horizon_days']}d")
    print(f"  Sentiment  : {d['sentiment']} (FinBERT-style aggregate)")
    return d


def stage_backtest(risk="balanced", top_n=10):
    print(f"\n{'='*70}\n[8] BACKTEST: equal-weight Top-{top_n} vs market proxy\n{'='*70}")
    bt = engine.backtest(risk, top_n)
    m = bt["metrics"]
    print(f"  Basket    : {', '.join(bt['picks'])}")
    print(f"  Window    : {bt['years']} years")
    print(f"  CAGR      : {m['cagr']}%   (market {m['benchmark_cagr']}%,  alpha {m['alpha']}%)")
    print(f"  Sharpe    : {m['sharpe']}   Sortino {m['sortino']}")
    print(f"  Max DD    : {m['max_drawdown']}%   Win rate {m['win_rate']}%   AnnVol {m['ann_vol']}%")
    print(f"  Final     : Rs {m['final_value']:,.0f}  (total {m['total_return']}%)")
    return bt


if __name__ == "__main__":
    print("QuantPick standalone pipeline — Indian markets (NSE + BSE)")
    ranked = stage_screen("balanced", top=12)
    top_symbol = ranked[0]["symbol"]
    stage_deep_dive(top_symbol, "balanced")
    stage_backtest("balanced", 10)
    print("\nDone. Same engine powers the FastAPI backend at /api/*.")
