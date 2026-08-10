from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

import engine
import analytics
import derivatives
import data_provider
from ml_models import ml_engine

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="QuantPick API")
api_router = APIRouter(prefix="/api")

logger = logging.getLogger("quantpick")

DEFAULT_SETTINGS = {
    "_id": "settings",
    "risk_profile": "balanced",
    "top_n": 10,
    "alerts": {"email": True, "whatsapp": False, "new_picks": True,
               "price_target": True, "stop_loss": True, "news": False},
    "email": "", "whatsapp_number": "",
}
INITIAL_CAPITAL = 1000000.0


async def get_settings():
    s = await db.config.find_one({"_id": "settings"})
    if not s:
        await db.config.insert_one(dict(DEFAULT_SETTINGS))
        return dict(DEFAULT_SETTINGS)
    s.pop("_id", None)
    return {**{k: v for k, v in DEFAULT_SETTINGS.items() if k != "_id"}, **s}


async def get_portfolio_doc():
    p = await db.portfolio.find_one({"_id": "paper"})
    if not p:
        p = {"_id": "paper", "cash": INITIAL_CAPITAL, "holdings": {},
             "transactions": [], "created": datetime.now(timezone.utc).isoformat()}
        await db.portfolio.insert_one(p)
    return p


# ------------------------- Models -------------------------
class SettingsUpdate(BaseModel):
    risk_profile: Optional[str] = None
    top_n: Optional[int] = None
    alerts: Optional[dict] = None
    email: Optional[str] = None
    whatsapp_number: Optional[str] = None


class TradeRequest(BaseModel):
    symbol: str
    side: str  # BUY / SELL
    qty: int


# ------------------------- Routes -------------------------
@api_router.get("/")
async def root():
    return {"message": "QuantPick API", "status": "ok"}


@api_router.get("/meta")
async def meta():
    return {"universe_size": len(engine.UNIVERSE), "sectors": engine.SECTORS,
            "exchanges": ["NSE", "BSE"], "risk_free_rate": engine.RISK_FREE}


@api_router.get("/picks")
async def picks(risk: str = "balanced", limit: int = 100):
    rows = await asyncio.to_thread(engine.score_universe, risk)
    return {"risk": risk, "generated": datetime.now(timezone.utc).isoformat(),
            "count": len(rows), "picks": rows[:limit]}


@api_router.get("/screener")
async def screener(risk: str = "balanced", sector: Optional[str] = None,
                   exchange: Optional[str] = None, max_pe: Optional[float] = None,
                   min_roe: Optional[float] = None, max_de: Optional[float] = None,
                   signal: Optional[str] = None):
    rows = await asyncio.to_thread(engine.score_universe, risk)
    out = []
    for r in rows:
        if sector and r["sector"] != sector:
            continue
        if exchange and r["exchange"] != exchange:
            continue
        if max_pe is not None and not (0 < r["pe"] <= max_pe):
            continue
        if min_roe is not None and r["roe"] < min_roe:
            continue
        if max_de is not None and r["de"] > max_de:
            continue
        if signal and r["signal"] != signal.upper():
            continue
        out.append(r)
    return {"count": len(out), "results": out}


@api_router.get("/stock/{symbol}")
async def stock(symbol: str, risk: str = "balanced"):
    symbol = symbol.upper()
    if symbol in engine.UNIVERSE_MAP:
        return await asyncio.to_thread(engine.stock_detail, symbol, risk)
    detail = await _ondemand_detail(symbol, risk)
    if not detail:
        raise HTTPException(404, "No tradable data found for this symbol")
    return detail


async def _resolve_instrument(symbol):
    doc = await db.instruments.find_one({"base": symbol, "exch": "NSE"})
    if not doc:
        doc = await db.instruments.find_one({"$or": [{"base": symbol}, {"name": symbol}], "exch": "BSE"})
    return doc


async def _ondemand_detail(symbol, risk):
    """Full signals for any tradable NSE/BSE stock outside the curated universe."""
    cache_key = f"{symbol}:{risk}"
    today = datetime.now(timezone.utc).date().isoformat()
    cached = await db.ondemand_scores.find_one({"_id": cache_key})
    if cached and cached.get("date") == today:
        return cached["detail"]
    inst = await _resolve_instrument(symbol)
    if not inst:
        return None
    exch = inst["exch"]
    bars = await asyncio.to_thread(data_provider.fetch_one_bars, symbol, exch)
    if not bars:
        return None
    # real-time LTP overlay if we can resolve a token
    if data_provider.angel.configured:
        try:
            c = await asyncio.to_thread(data_provider.angel.session)
            r = await asyncio.to_thread(c.ltpData, exch, inst["tradingsymbol"], inst["token"])
            ltp = r.get("data", {}).get("ltp")
            if ltp:
                bars[-1] = {**bars[-1], "close": round(float(ltp), 2)}
        except Exception:
            pass
    fund = await asyncio.to_thread(data_provider.fetch_fundamentals, symbol, exch)
    name = (fund or {}).get("name", inst.get("name", symbol))
    sector = (fund or {}).get("sector", "—")
    ml = await asyncio.to_thread(__import__("ml_models").predict_bars, bars)
    scored = await asyncio.to_thread(engine.score_external, symbol, exch, sector, bars, fund, ml, risk)
    scored["name"] = name
    price = scored["price"]
    dcf = engine.dcf_value(fund, price) if fund and fund.get("fcf_cr") else {"intrinsic": None, "upside": None, "note": "Fundamentals unavailable for DCF"}
    mc = await asyncio.to_thread(engine.monte_carlo, bars)
    sent, heads = engine._news_sentiment(symbol)
    t = engine.technicals(bars)
    detail = {"symbol": symbol, "name": name, "exchange": exch, "sector": sector,
              "fundamentals": fund or {}, "technicals": t,
              "fundamental_score": scored["fundamental_score"], "technical_score": scored["technical_score"],
              "piotroski": scored["piotroski"], "dcf": dcf, "monte_carlo": mc,
              "sentiment": sent, "news": heads,
              "chart": [{"date": b["date"], "close": b["close"], "volume": b["volume"]} for b in bars[-180:]],
              "scored": scored, "on_demand": True, "has_fundamentals": scored.get("has_fundamentals", False)}
    await db.ondemand_scores.update_one({"_id": cache_key},
        {"$set": {"date": today, "detail": detail}}, upsert=True)
    return detail


@api_router.get("/backtest")
async def backtest(risk: str = "balanced", top_n: int = 10):
    return await asyncio.to_thread(engine.backtest, risk, top_n)


@api_router.post("/ai/analyst/{symbol}")
async def ai_analyst(symbol: str, risk: str = "balanced"):
    symbol = symbol.upper()
    if symbol not in engine.UNIVERSE_MAP:
        raise HTTPException(404, "Symbol not in universe")
    cached = await db.ai_analysis.find_one({"_id": f"{symbol}:{risk}"})
    if cached:
        return {"symbol": symbol, "analysis": cached["analysis"], "cached": True}

    d = await asyncio.to_thread(engine.stock_detail, symbol, risk)
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    key = os.environ.get("EMERGENT_LLM_KEY")
    sc = d["scored"] or {}
    f = d["fundamentals"]
    context = f"""Stock: {d['name']} ({symbol}, {d['exchange']}) | Sector: {d['sector']}
Price: Rs {d['technicals']['price']} | Composite: {sc.get('composite')} | Signal: {sc.get('signal')} | Rank: {sc.get('rank')}
Sub-scores -> Fundamental: {d['fundamental_score']}, Technical: {d['technical_score']}, Factor: {sc.get('factor_score')}, Sentiment: {sc.get('sentiment_score')}
ML model (XGBoost) -> score: {sc.get('ml_score')}, signal: {sc.get('ml_signal')}, P(Buy): {sc.get('ml_buy_prob')}%, next-day up prob: {sc.get('direction_prob')}%
Piotroski F-Score: {d['piotroski']}/9
Fundamentals -> P/E: {f['pe']}, P/B: {f['pb']}, ROE: {f['roe']}%, ROCE: {f['roce']}%, D/E: {f['de']}, EPS growth: {f['eps_growth']*100:.0f}%, Profit margin: {f['profit_margin']}%
Technicals -> RSI: {d['technicals']['rsi']}, MACD hist: {d['technicals']['macd_hist']}, ADX: {d['technicals']['adx']}, SMA50: {d['technicals']['sma50']}, SMA200: {d['technicals']['sma200']}
DCF -> intrinsic: {d['dcf'].get('intrinsic')}, upside: {d['dcf'].get('upside')}% (WACC 11%, 2-stage)
Monte Carlo (126d, 1000 sims) -> expected: {d['monte_carlo']['expected']}, VaR95: {d['monte_carlo']['var95_pct']}%, P(+15%): {d['monte_carlo']['prob_up_15pct']}%
Quant factors (percentile) -> Momentum: {sc.get('momentum')}, Quality: {sc.get('quality')}, Value: {sc.get('value_score')}, LowVol: {sc.get('lowvol')}"""

    system = (
        "You are a senior quantitative equity analyst at a systematic hedge fund covering Indian equities. "
        "Write a rigorous, professional analyst note. Be quantitative and reference the actual numbers. "
        "Include explicit formulas/equations written in plain-text monospace style where relevant "
        "(e.g., Sharpe = (Rp - Rf)/sigma_p; DCF intrinsic = Sum(FCF_t/(1+WACC)^t) + TV/(1+WACC)^5; "
        "Graham/relative value, expected return via factor loadings, CAPM, VaR at 95%). "
        "Structure with these sections using '## ' headers: Thesis, Valuation (DCF + relative), "
        "Factor & Technical Read, Risk (VaR, drawdown, D/E), Verdict (rating + entry/target/stop). "
        "Keep it under 380 words. Do not give personalized financial advice disclaimers."
    )
    try:
        chat = LlmChat(api_key=key, session_id=f"analyst-{symbol}", system_message=system)
        chat.with_model("anthropic", "claude-sonnet-4-6")
        resp = await chat.send_message(UserMessage(text=f"Analyze this stock:\n{context}"))
        text = resp if isinstance(resp, str) else str(resp)
    except Exception as e:
        logger.error(f"AI analyst error: {e}")
        raise HTTPException(502, f"AI analysis failed: {e}")

    await db.ai_analysis.insert_one({"_id": f"{symbol}:{risk}", "analysis": text,
                                     "created": datetime.now(timezone.utc).isoformat()})
    return {"symbol": symbol, "analysis": text, "cached": False}


@api_router.get("/settings")
async def read_settings():
    return await get_settings()


@api_router.put("/settings")
async def update_settings(upd: SettingsUpdate):
    cur = await get_settings()
    for k, v in upd.model_dump(exclude_none=True).items():
        cur[k] = v
    await db.config.update_one({"_id": "settings"}, {"$set": cur}, upsert=True)
    cur.pop("_id", None)
    return cur


@api_router.get("/portfolio")
async def portfolio():
    p = await get_portfolio_doc()
    holdings = p["holdings"]
    detailed = []
    invested = 0.0
    market_value = 0.0
    for sym, h in holdings.items():
        if sym not in engine.UNIVERSE_MAP:
            continue
        price = engine.technicals(engine.get_bars(sym))["price"]
        cost = h["qty"] * h["avg_price"]
        mv = h["qty"] * price
        invested += cost
        market_value += mv
        detailed.append({
            "symbol": sym, "name": engine.UNIVERSE_MAP[sym]["name"], "qty": h["qty"],
            "avg_price": round(h["avg_price"], 2), "ltp": round(price, 2),
            "invested": round(cost, 2), "market_value": round(mv, 2),
            "pnl": round(mv - cost, 2),
            "pnl_pct": round((price / h["avg_price"] - 1) * 100, 2) if h["avg_price"] else 0,
            "weight": 0})
    total = p["cash"] + market_value
    for d in detailed:
        d["weight"] = round(d["market_value"] / market_value * 100, 2) if market_value else 0
    unrealized = market_value - invested
    return {
        "cash": round(p["cash"], 2), "invested": round(invested, 2),
        "market_value": round(market_value, 2), "total_value": round(total, 2),
        "unrealized_pnl": round(unrealized, 2),
        "unrealized_pnl_pct": round(unrealized / invested * 100, 2) if invested else 0,
        "total_return_pct": round((total / INITIAL_CAPITAL - 1) * 100, 2),
        "holdings": sorted(detailed, key=lambda x: x["market_value"], reverse=True),
        "transactions": p["transactions"][-30:][::-1],
        "initial_capital": INITIAL_CAPITAL,
    }


@api_router.post("/portfolio/trade")
async def trade(req: TradeRequest):
    sym = req.symbol.upper()
    if sym not in engine.UNIVERSE_MAP:
        raise HTTPException(404, "Symbol not in universe")
    if req.qty <= 0:
        raise HTTPException(400, "Quantity must be positive")
    p = await get_portfolio_doc()
    price = engine.technicals(engine.get_bars(sym))["price"]
    holdings = p["holdings"]
    cost = price * req.qty
    if req.side.upper() == "BUY":
        if cost > p["cash"]:
            raise HTTPException(400, "Insufficient cash")
        p["cash"] -= cost
        if sym in holdings:
            h = holdings[sym]
            new_qty = h["qty"] + req.qty
            h["avg_price"] = (h["avg_price"] * h["qty"] + cost) / new_qty
            h["qty"] = new_qty
        else:
            holdings[sym] = {"qty": req.qty, "avg_price": price}
    elif req.side.upper() == "SELL":
        if sym not in holdings or holdings[sym]["qty"] < req.qty:
            raise HTTPException(400, "Not enough holdings to sell")
        holdings[sym]["qty"] -= req.qty
        p["cash"] += cost
        if holdings[sym]["qty"] == 0:
            del holdings[sym]
    else:
        raise HTTPException(400, "side must be BUY or SELL")
    p["transactions"].append({
        "symbol": sym, "side": req.side.upper(), "qty": req.qty,
        "price": round(price, 2), "value": round(cost, 2),
        "time": datetime.now(timezone.utc).isoformat()})
    await db.portfolio.update_one({"_id": "paper"},
                                  {"$set": {"cash": p["cash"], "holdings": holdings,
                                            "transactions": p["transactions"]}})
    return {"ok": True, "executed_price": round(price, 2), "cash": round(p["cash"], 2)}


@api_router.post("/portfolio/reset")
async def reset_portfolio():
    await db.portfolio.delete_one({"_id": "paper"})
    await get_portfolio_doc()
    return {"ok": True}


@api_router.get("/alerts")
async def alerts(risk: str = "balanced"):
    rows = await asyncio.to_thread(engine.score_universe, risk)
    out = []
    for r in rows[:6]:
        if r["signal"] == "BUY":
            out.append({"type": "NEW_PICK", "symbol": r["symbol"], "severity": "info",
                        "message": f"New BUY pick: {r['name']} (score {r['composite']}), target Rs {r['target']}",
                        "time": datetime.now(timezone.utc).isoformat()})
    for r in rows:
        if r["rsi"] > 75:
            out.append({"type": "OVERBOUGHT", "symbol": r["symbol"], "severity": "warning",
                        "message": f"{r['name']} RSI {r['rsi']} — overbought, watch for reversal",
                        "time": datetime.now(timezone.utc).isoformat()})
        if r["signal"] == "SELL" and r["rsi"] < 35:
            out.append({"type": "STOP_LOSS", "symbol": r["symbol"], "severity": "critical",
                        "message": f"{r['name']} weak (score {r['composite']}, RSI {r['rsi']}) — stop-loss zone",
                        "time": datetime.now(timezone.utc).isoformat()})
    return {"count": len(out), "alerts": out[:12], "channels_note": "Email (Resend) & WhatsApp (Twilio) are mocked in MVP"}


# ------------------------- Watchlist & Compare -------------------------
async def _get_watchlist():
    doc = await db.watchlist.find_one({"_id": "wl"})
    return doc["symbols"] if doc else []


@api_router.get("/watchlist")
async def get_watchlist(risk: str = "balanced"):
    syms = await _get_watchlist()
    rows = await asyncio.to_thread(engine.score_universe, risk)
    by = {r["symbol"]: r for r in rows}
    return {"symbols": syms, "items": [by[s] for s in syms if s in by]}


@api_router.post("/watchlist/toggle")
async def toggle_watchlist(body: dict):
    sym = (body.get("symbol") or "").upper()
    if sym not in engine.UNIVERSE_MAP:
        raise HTTPException(404, "Symbol not in universe")
    syms = await _get_watchlist()
    syms = [s for s in syms if s != sym] if sym in syms else syms + [sym]
    await db.watchlist.update_one({"_id": "wl"}, {"$set": {"symbols": syms}}, upsert=True)
    return {"symbols": syms, "pinned": sym in syms}


@api_router.get("/compare")
async def compare(symbols: str, risk: str = "balanced"):
    reqs = [s.strip().upper() for s in symbols.split(",") if s.strip()][:5]
    rows = await asyncio.to_thread(engine.score_universe, risk)
    by = {r["symbol"]: r for r in rows}
    items = [by[s] for s in reqs if s in by]
    # normalized price series (base 100) for overlay chart
    series = {}
    for s in reqs:
        if s not in engine.UNIVERSE_MAP:
            continue
        bars = engine.get_bars(s)[-180:]
        base = bars[0]["close"] or 1
        series[s] = [{"date": b["date"], "value": round(b["close"] / base * 100, 2)} for b in bars]
    # merge into aligned chart rows by index
    chart = []
    if series:
        length = min(len(v) for v in series.values())
        keys = list(series.keys())
        for i in range(length):
            pt = {"date": series[keys[0]][i]["date"]}
            for s in keys:
                pt[s] = series[s][i]["value"]
            chart.append(pt)
    return {"items": items, "chart": chart, "symbols": reqs}


# ------------------------- Data / ML status & refresh -------------------------
@api_router.get("/data-status")
async def data_status():
    info = await db.meta_info.find_one({"_id": "data_status"}) or {}
    info.pop("_id", None)
    return {"data": info, "ml_trained": ml_engine.trained,
            "angel_configured": data_provider.angel.configured}


@api_router.post("/refresh")
async def manual_refresh():
    asyncio.create_task(_refresh_pipeline())
    return {"ok": True, "message": "Refresh started"}


async def _refresh_pipeline():
    try:
        bars_map, source, live_count = await data_provider.refresh_market_data(db, engine.UNIVERSE)
        engine.set_live_bars(bars_map)
        analytics.clear_analytics_cache()
        preds = await asyncio.to_thread(ml_engine.train_and_predict, bars_map)
        engine.set_ml_predictions(preds)
        for r in ("conservative", "balanced", "aggressive"):
            await asyncio.to_thread(engine.score_universe, r)
        await _snapshot_picks()
        logger.info(f"Refresh done: source={source} live={live_count} ml_preds={len(preds)}")
    except Exception as e:
        logger.error(f"Refresh pipeline error: {e}")


async def _snapshot_picks():
    """Record today's top picks so forward performance can be tracked over time."""
    today = datetime.now(timezone.utc).date().isoformat()
    rows = engine.score_universe("balanced")
    top = [{"symbol": r["symbol"], "signal": r["signal"], "composite": r["composite"],
            "price": r["price"], "target": r["target"]} for r in rows[:15]]
    await db.pick_snapshots.update_one({"_id": today},
        {"$set": {"date": today, "picks": top}}, upsert=True)


# ------------------------- Advanced analytics -------------------------
@api_router.get("/analytics/{symbol}")
async def analytics_endpoint(symbol: str, risk: str = "balanced"):
    symbol = symbol.upper()
    if symbol in engine.UNIVERSE_MAP:
        rm = await asyncio.to_thread(analytics.risk_metrics, symbol)
        ff = await asyncio.to_thread(analytics.fama_french, symbol)
        rows = await asyncio.to_thread(engine.score_universe, risk)
        row = next((r for r in rows if r["symbol"] == symbol), {})
    else:
        detail = await _ondemand_detail(symbol, risk)
        if not detail:
            raise HTTPException(404, "Symbol not found")
        bars_full = await asyncio.to_thread(data_provider.fetch_one_bars, symbol, detail["exchange"])
        rm = await asyncio.to_thread(analytics.risk_metrics_bars, bars_full)
        ff = await asyncio.to_thread(analytics.fama_french_bars, bars_full)
        row = detail["scored"]
    win_p = (row.get("direction_prob") or 50) / 100
    upside = max(0.01, (row.get("target", 0) / max(row.get("price", 1), 1)) - 1)
    r_ratio = upside / 0.08
    k = analytics.kelly(win_p, r_ratio)
    return {"risk_metrics": rm, "fama_french": ff,
            "kelly": {"fraction": k, "pct": round(k * 100, 2), "win_prob": round(win_p * 100, 1),
                      "win_loss_ratio": round(r_ratio, 2),
                      "note": "f* = W - (1-W)/R, capped at quarter-Kelly (25%)"}}


@api_router.get("/sector-heatmap")
async def sector_heatmap(risk: str = "balanced"):
    return {"sectors": await asyncio.to_thread(analytics.sector_heatmap, risk)}


@api_router.get("/information-metrics")
async def information_metrics(risk: str = "balanced"):
    return await asyncio.to_thread(analytics.information_metrics, risk)


@api_router.get("/search")
async def search(q: str, limit: int = 25):
    q = q.strip().upper()
    if len(q) < 1:
        return {"results": []}
    scored = {r["symbol"] for r in engine.UNIVERSE}
    prefix = await db.instruments.find({"base": {"$regex": f"^{q}"}}).limit(limit).to_list(limit)
    seen = {d["token"] for d in prefix}
    need = limit - len(prefix)
    extra = []
    if need > 0:
        extra = await db.instruments.find(
            {"name": {"$regex": q}, "token": {"$nin": list(seen)}}).limit(need).to_list(need)
    docs = prefix + extra
    docs.sort(key=lambda d: (d["base"] not in scored, len(d["base"])))
    return {"results": [{"symbol": d["base"], "name": d["name"], "exchange": d["exch"],
                         "tradingsymbol": d["tradingsymbol"], "in_universe": d["base"] in scored}
                        for d in docs]}


@api_router.get("/performance")
async def performance():
    snaps = await db.pick_snapshots.find({}).sort("date", 1).to_list(400)
    if not snaps:
        return {"tracking_days": 0, "records": [], "win_rate": None,
                "note": "Forward tracking starts now — daily pick snapshots accrue over time."}
    records = []
    wins = tot = 0
    for s in snaps:
        for p in s["picks"][:10]:
            sym = p["symbol"]
            if sym not in engine.UNIVERSE_MAP:
                continue
            cur = engine.technicals(engine.get_bars(sym))["price"]
            ret = (cur / p["price"] - 1) * 100 if p["price"] else 0
            if p["signal"] == "BUY":
                tot += 1
                if ret > 0:
                    wins += 1
            records.append({"date": s["date"], "symbol": sym, "signal": p["signal"],
                            "entry": p["price"], "current": round(cur, 2), "return_pct": round(ret, 2)})
    return {"tracking_days": len(snaps), "records": records[-60:][::-1],
            "win_rate": round(wins / tot * 100, 1) if tot else None,
            "buy_count": tot,
            "note": "Return since snapshot date, marked to latest price."}


# ------------------------- Live trading (Angel One) -------------------------
class LiveOrderRequest(BaseModel):
    symbol: str
    side: str
    qty: int
    confirm: bool = False


@api_router.get("/broker/status")
async def broker_status():
    st = {"configured": data_provider.angel.configured, "connected": False, "name": None,
          "funds": None, "tokens_loaded": len(data_provider.angel._tokens)}
    if data_provider.angel.configured:
        try:
            c = await asyncio.to_thread(data_provider.angel.session)
            st["connected"] = True
            rms = await asyncio.to_thread(c.rmsLimit)
            st["funds"] = rms.get("data", {}).get("availablecash")
        except Exception as e:
            st["error"] = str(e)[:200]
    return st


@api_router.get("/broker/server-ip")
async def broker_server_ip():
    """Return this server's public egress IP to whitelist in the Angel SmartAPI app."""
    ip = None
    try:
        import urllib.request
        ip = await asyncio.to_thread(
            lambda: urllib.request.urlopen("https://api.ipify.org", timeout=8).read().decode().strip())
    except Exception as e:
        logger.error(f"server ip: {e}")
    return {"server_ip": ip,
            "instructions": ["Go to smartapi.angelone.in/new/apps and edit your app (QuantProject).",
                             "Set the Primary Static IP (or Secondary) to the server_ip shown here.",
                             "Note: Angel allows changing the Primary IP only once per week.",
                             "After whitelisting, live orders from this server will be accepted."]}


@api_router.post("/trade/live")
async def trade_live(req: LiveOrderRequest):
    if not data_provider.angel.configured:
        raise HTTPException(400, "Angel One not configured")
    if not req.confirm:
        raise HTTPException(400, "Confirmation required for live orders")
    sym = req.symbol.upper()
    try:
        res = await asyncio.to_thread(data_provider.angel.place_order, sym, req.side, req.qty)
    except Exception as e:
        raise HTTPException(502, f"Order failed: {e}")
    data = res.get("data") if isinstance(res, dict) else None
    ok = bool(isinstance(res, dict) and res.get("status"))
    await db.live_orders.insert_one({"symbol": sym, "side": req.side.upper(), "qty": req.qty,
                                     "response": str(res)[:500],
                                     "time": datetime.now(timezone.utc).isoformat()})
    return {"ok": ok, "order_id": (data or {}).get("orderid") if data else None,
            "message": res.get("message") if isinstance(res, dict) else str(res)}
@api_router.get("/derivatives/{symbol}")
async def get_derivatives(symbol: str, strike: float = None, expiry_days: int = 30,
                          option_type: str = "call"):
    bars = engine.get_bars(symbol.upper())
    S = bars[-1]["close"]
    K = strike if strike else round(S, 0)
    T = expiry_days / 365
    r = engine.RISK_FREE
    import numpy as np
    returns = np.diff(np.log([b["close"] for b in bars]))
    sigma = float(np.std(returns) * np.sqrt(252))
    bs  = derivatives.black_scholes(S, K, T, r, sigma, option_type)
    g   = derivatives.greeks(S, K, T, r, sigma, option_type)
    bt  = derivatives.binomial_tree(S, K, T, r, sigma, option_type=option_type)
    pcp = derivatives.put_call_parity(
              derivatives.black_scholes(S, K, T, r, sigma, "call")["price"],
              derivatives.black_scholes(S, K, T, r, sigma, "put")["price"],
              S, K, T, r)
    return {"symbol": symbol, "spot": S, "strike": K, "expiry_days": expiry_days,
            "volatility_pct": round(sigma*100,2), "black_scholes": bs,
            "greeks": g, "binomial_tree": bt, "put_call_parity": pcp}
@api_router.get("/analytics/cvar/{symbol}")
async def get_cvar(symbol: str, confidence: float = 0.95, horizon: int = 1):
    return await asyncio.to_thread(analytics.cvar, symbol.upper(), confidence, horizon)

@api_router.get("/analytics/garch/{symbol}")
async def get_garch(symbol: str):
    return await asyncio.to_thread(analytics.garch_volatility, symbol.upper())

@api_router.get("/analytics/optimize")
async def get_optimize(risk: str = "balanced"):
    mvo = await asyncio.to_thread(analytics.mean_variance_optimize, risk)
    hrp = await asyncio.to_thread(analytics.hierarchical_risk_parity, risk)
    return {"mvo": mvo, "hrp": hrp}

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

scheduler = None


@app.on_event("startup")
async def startup():
    async def _boot():
        # 1) fast: warm seeded engine so UI is instant
        for r in ("conservative", "balanced", "aggressive"):
            await asyncio.to_thread(engine.score_universe, r)
        logger.info("QuantPick seeded cache warmed")
        # 2) load Angel instrument master (full NSE+BSE for search) + universe tokens
        try:
            await data_provider.load_scrip_master(db)
            await db.instruments.create_index("base")
            await db.instruments.create_index("name")
            toks = await data_provider.build_universe_tokens(db, engine.UNIVERSE)
            data_provider.angel.load_tokens(toks)
            logger.info(f"Angel tokens mapped: {len(toks)}/{len(engine.UNIVERSE)}")
        except Exception as e:
            logger.error(f"instrument load failed: {e}")
        # 3) try cached live bars for a quick real-data upgrade
        cached = await data_provider.load_cached_bars(db, engine.UNIVERSE)
        if cached:
            engine.set_live_bars(cached)
            analytics.clear_analytics_cache()
            preds = await asyncio.to_thread(ml_engine.train_and_predict, cached)
            engine.set_ml_predictions(preds)
            await asyncio.to_thread(engine.score_universe, "balanced")
            logger.info("Loaded cached live bars + ML")
        # 4) fresh live pull (incl. Angel LTP overlay) + retrain in background
        await _refresh_pipeline()
    asyncio.create_task(_boot())

    global scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        scheduler.add_job(_refresh_pipeline, CronTrigger(hour=8, minute=30),
                          id="daily_refresh", replace_existing=True)
        scheduler.start()
        logger.info("Scheduler started: daily refresh 08:30 IST")
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
