"""Live market data layer: Angel One SmartAPI (optional) + yfinance, with
MongoDB day-cache and graceful fallback to the deterministic seeded engine."""
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger("quantpick.data")

# ---------------------------------------------------------------------------
# Angel One SmartAPI adapter (activates only when all creds are configured)
# ---------------------------------------------------------------------------
class AngelAdapter:
    def __init__(self):
        self._client = None
        self._tokens = {}   # symbol -> {token, tradingsymbol, exch}

    @property
    def api_key(self):
        return os.environ.get("ANGEL_API_KEY")

    @property
    def configured(self):
        return all((os.environ.get("ANGEL_API_KEY"), os.environ.get("ANGEL_CLIENT_CODE"),
                    os.environ.get("ANGEL_PIN"), os.environ.get("ANGEL_TOTP_SECRET")))

    def session(self):
        if self._client:
            return self._client
        import pyotp
        from SmartApi import SmartConnect
        c = SmartConnect(api_key=os.environ.get("ANGEL_API_KEY"))
        totp = pyotp.TOTP(os.environ.get("ANGEL_TOTP_SECRET")).now()
        res = c.generateSession(os.environ.get("ANGEL_CLIENT_CODE"), os.environ.get("ANGEL_PIN"), totp)
        if not res.get("status"):
            raise RuntimeError(f"Angel login failed: {res.get('message')}")
        self._client = c
        return c

    def _reset(self):
        self._client = None

    def load_tokens(self, instruments_by_sym):
        self._tokens = instruments_by_sym or {}

    def batch_ltp(self, universe):
        """Return {symbol: ltp} using Angel getMarketData (LTP mode), batched by exchange."""
        if not self.configured or not self._tokens:
            return {}
        try:
            c = self.session()
        except Exception as e:
            logger.error(f"Angel session: {e}")
            self._reset()
            return {}
        by_exch = {"NSE": [], "BSE": []}
        tok_to_sym = {}
        for st in universe:
            sym = st["symbol"]
            info = self._tokens.get(sym)
            if not info:
                continue
            by_exch.setdefault(info["exch"], []).append(info["token"])
            tok_to_sym[(info["exch"], info["token"])] = sym
        out = {}
        for exch, toks in by_exch.items():
            for i in range(0, len(toks), 45):
                chunk = toks[i:i + 45]
                try:
                    r = c.getMarketData("LTP", {exch: chunk})
                    for d in r.get("data", {}).get("fetched", []):
                        key = (d["exchange"], str(d["symbolToken"]))
                        if key in tok_to_sym:
                            out[tok_to_sym[key]] = float(d["ltp"])
                except Exception as e:
                    logger.error(f"Angel batch_ltp {exch}: {e}")
                    self._reset()
                    return out
        return out

    def place_order(self, symbol, side, qty, order_type="MARKET", price=0, product="DELIVERY"):
        if not self.configured:
            raise RuntimeError("Angel One not configured")
        info = self._tokens.get(symbol)
        if not info:
            raise RuntimeError(f"No instrument token for {symbol}")
        c = self.session()
        params = {
            "variety": "NORMAL", "tradingsymbol": info["tradingsymbol"],
            "symboltoken": info["token"], "transactiontype": side.upper(),
            "exchange": info["exch"], "ordertype": order_type,
            "producttype": product, "duration": "DAY",
            "price": str(price), "squareoff": "0", "stoploss": "0", "quantity": str(qty),
        }
        res = c.placeOrderFullResponse(params) if hasattr(c, "placeOrderFullResponse") else c.placeOrder(params)
        return res


angel = AngelAdapter()


async def load_scrip_master(db):
    """Download Angel instrument master once and store NSE-EQ + BSE equities for search."""
    count = await db.instruments.count_documents({})
    if count > 1000:
        return count
    import urllib.request, json
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=80).read())
    except Exception as e:
        logger.error(f"scrip master download failed: {e}")
        return 0
    docs = []
    for d in data:
        exch = d.get("exch_seg")
        sym = d.get("symbol", "")
        name = d.get("name", "")
        if exch == "NSE" and sym.endswith("-EQ"):
            docs.append({"token": d["token"], "tradingsymbol": sym, "name": name,
                         "base": sym[:-3], "exch": "NSE"})
        elif exch == "BSE" and d.get("instrumenttype", "") == "" and name and d["token"].isdigit():
            docs.append({"token": d["token"], "tradingsymbol": sym, "name": name,
                         "base": sym, "exch": "BSE"})
    if docs:
        await db.instruments.delete_many({})
        for i in range(0, len(docs), 5000):
            await db.instruments.insert_many(docs[i:i + 5000], ordered=False)
    logger.info(f"instruments loaded: {len(docs)}")
    return len(docs)


async def build_universe_tokens(db, universe):
    """Map each universe symbol to its Angel token (prefer NSE-EQ, else BSE)."""
    out = {}
    for st in universe:
        sym = st["symbol"]
        doc = await db.instruments.find_one({"base": sym, "exch": "NSE"})
        if not doc:
            doc = await db.instruments.find_one({"$or": [{"base": sym}, {"name": sym}], "exch": "BSE"})
        if doc:
            out[sym] = {"token": doc["token"], "tradingsymbol": doc["tradingsymbol"], "exch": doc["exch"]}
    return out


def fetch_one_bars(symbol, exch, period="2y"):
    """Daily OHLCV for a single symbol via yfinance. Returns [] on failure."""
    import yfinance as yf
    try:
        df = yf.Ticker(_yf_ticker(symbol, exch)).history(period=period, auto_adjust=True)
    except Exception as e:
        logger.error(f"fetch_one_bars {symbol}: {e}")
        return []
    if df is None or len(df) < 60:
        return []
    bars = []
    for idx, row in df.iterrows():
        try:
            bars.append({"date": idx.date().isoformat(),
                         "open": round(float(row["Open"]), 2), "high": round(float(row["High"]), 2),
                         "low": round(float(row["Low"]), 2), "close": round(float(row["Close"]), 2),
                         "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0})
        except Exception:
            continue
    return bars


def fetch_fundamentals(symbol, exch):
    """Best-effort fundamentals from yfinance .info. Returns {} if unavailable."""
    import yfinance as yf
    try:
        info = yf.Ticker(_yf_ticker(symbol, exch)).info
    except Exception:
        return {}
    if not info or not info.get("trailingPE"):
        return {}
    def g(k, d=0):
        v = info.get(k)
        return v if isinstance(v, (int, float)) else d
    shares = g("sharesOutstanding") / 1e7 if g("sharesOutstanding") else 0  # crore
    fcf = g("freeCashflow") / 1e7 if g("freeCashflow") else 0               # crore
    return {"pe": round(g("trailingPE"), 2), "pb": round(g("priceToBook") or 1, 2),
            "roe": round(g("returnOnEquity") * 100, 2), "roce": round(g("returnOnAssets") * 100, 2),
            "de": round((g("debtToEquity") or 0) / 100, 2),
            "eps_growth": round(g("earningsGrowth") or g("revenueGrowth") or 0.05, 3),
            "div_yield": round((g("dividendYield") or 0) * 100, 2),
            "profit_margin": round((g("profitMargins") or 0) * 100, 2),
            "current_ratio": round(g("currentRatio") or 1.2, 2),
            "eps": round(g("trailingEps") or 1, 2), "fcf_cr": round(fcf, 0),
            "shares_cr": round(shares, 2), "growth": round(g("earningsGrowth") or 0.08, 3),
            "name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector") or "—"}




# ---------------------------------------------------------------------------
# yfinance batch download
# ---------------------------------------------------------------------------
def _yf_ticker(symbol, exchange):
    return f"{symbol}.NS" if exchange == "NSE" else f"{symbol}.BO"


def fetch_yfinance(universe, period="2y"):
    """Batch-download daily OHLCV for the whole universe. Returns {symbol: bars}."""
    import yfinance as yf
    ticker_map = {_yf_ticker(s["symbol"], s["exchange"]): s["symbol"] for s in universe}
    tickers = list(ticker_map.keys())
    out = {}
    try:
        df = yf.download(tickers, period=period, interval="1d", group_by="ticker",
                         threads=True, progress=False, auto_adjust=True)
    except Exception as e:
        logger.error(f"yfinance batch failed: {e}")
        return out
    for tk, sym in ticker_map.items():
        try:
            sub = df[tk].dropna() if len(tickers) > 1 else df.dropna()
            if sub is None or len(sub) < 60:
                continue
            bars = []
            for idx, row in sub.iterrows():
                bars.append({
                    "date": idx.date().isoformat(),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                })
            if len(bars) >= 60:
                out[sym] = bars
        except Exception:
            continue
    logger.info(f"yfinance: fetched {len(out)}/{len(tickers)} symbols")
    return out


# ---------------------------------------------------------------------------
# Orchestration + Mongo day-cache
# ---------------------------------------------------------------------------
async def refresh_market_data(db, universe):
    """Fetch live bars (yfinance primary, seeded fallback), cache in Mongo,
    return {symbol: bars} for every universe symbol (never empty)."""
    import engine
    live = fetch_yfinance(universe)
    source = "yfinance"
    if not live:
        source = "seeded"
    # persist whatever live data we got
    today = datetime.now(timezone.utc).date().isoformat()
    if live:
        try:
            await db.ohlcv_cache.delete_many({})
            docs = [{"symbol": s, "bars": b, "date": today, "source": "yfinance"}
                    for s, b in live.items()]
            if docs:
                await db.ohlcv_cache.insert_many(docs, ordered=False)
        except Exception as e:
            logger.error(f"cache write failed: {e}")
    # fill gaps with seeded synthetic bars so scoring always has full universe
    bars_map = {}
    for st in universe:
        sym = st["symbol"]
        bars_map[sym] = live.get(sym) or engine.generate_ohlcv(sym)
    # Angel One real-time LTP overlay: overwrite latest close with live quote
    angel_ltps = {}
    if angel.configured and angel._tokens:
        try:
            angel_ltps = await __import__("asyncio").to_thread(angel.batch_ltp, universe)
        except Exception as e:
            logger.error(f"angel ltp overlay: {e}")
    for sym, ltp in angel_ltps.items():
        if sym in bars_map and bars_map[sym] and ltp:
            bars_map[sym] = bars_map[sym][:]
            last = dict(bars_map[sym][-1]); last["close"] = round(float(ltp), 2)
            bars_map[sym][-1] = last
    if angel_ltps:
        source = "angelone+yfinance"
    await db.meta_info.update_one(
        {"_id": "data_status"},
        {"$set": {"source": source, "live_count": len(live),
                  "angel_ltp": len(angel_ltps),
                  "total": len(universe), "updated": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    return bars_map, source, len(live)


async def load_cached_bars(db, universe):
    """Load bars from Mongo cache if present, else return None."""
    import engine
    docs = await db.ohlcv_cache.find({}).to_list(1000)
    if not docs:
        return None
    cached = {d["symbol"]: d["bars"] for d in docs}
    bars_map = {}
    for st in universe:
        sym = st["symbol"]
        bars_map[sym] = cached.get(sym) or engine.generate_ohlcv(sym)
    return bars_map
