"""
data_fetcher.py — Multi-source market data abstraction layer
============================================================
Routes all external data calls based on DATA_SOURCE in .env.

Supported sources:
  yfinance      — Free, no API key. Covers ETFs/stocks + VIX (^VIX).
  finnhub       — Free tier key required. Real-time quotes + economic calendar.
  alphavantage  — Free API key required. Quotes + VIX via TIME_SERIES_DAILY.
  polygon       — Paid key required. Real-time quotes, options data.

Outputs (all functions return dicts with a 'source' and 'timestamp' field):
  get_spot(ticker)          → { price, change_pct, source, timestamp }
  get_market_data(ticker)   → { spot, vix, atr5, source, timestamp }
  get_eco_calendar()        → { events, alertLevel, headline, reason, source, timestamp }
"""

import os
import time
import datetime
from dotenv import load_dotenv

load_dotenv()

DATA_SOURCE       = os.getenv("DATA_SOURCE", "yfinance").lower().strip()
FINNHUB_KEY       = os.getenv("FINNHUB_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
POLYGON_KEY       = os.getenv("POLYGON_API_KEY", "")

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _ts():
    """ISO timestamp string for now."""
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _round_atr(df):
    """
    Calculate 5-day ATR from an OHLC DataFrame (columns: High, Low, Close).
    Returns a float rounded to 2 decimal places.
    """
    import pandas as pd
    if len(df) < 2:
        return 0.0
    high = df["High"]
    low  = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    atr5 = tr.iloc[-5:].mean()
    return round(float(atr5), 2)


# ─────────────────────────────────────────────
# Economic calendar classification (shared)
# ─────────────────────────────────────────────

HIGH_IMPACT = ["fomc", "federal funds", "cpi", "consumer price",
               "nonfarm", "non-farm", "payroll", "unemployment rate"]
MED_IMPACT  = ["ppi", "producer price", "pce", "jobless claims",
               "initial claims", "gdp", "retail sales", "housing starts",
               "existing home", "new home", "fed speak", "powell",
               "fed chair", "ism manufactur", "ism services",
               "durable goods", "trade balance", "michigan"]
DAY_LABELS  = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

def _classify_event(name):
    n = name.lower()
    if any(k in n for k in HIGH_IMPACT):
        return "high"
    if any(k in n for k in MED_IMPACT):
        return "med"
    return None

def _build_eco_response(events, source):
    """
    Given a list of { day, name, impact } dicts, build the standard
    eco-calendar response dict consumed by the Flask route and frontend.
    """
    # Sort: high first, then by weekday order
    day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4}
    imp_order = {"high": 0, "med": 1}
    events.sort(key=lambda e: (imp_order.get(e["impact"], 9),
                               day_order.get(e["day"], 9)))

    has_high = any(e["impact"] == "high" for e in events)
    has_med  = any(e["impact"] == "med"  for e in events)
    alert    = "alert" if has_high else ("warn" if has_med else "calm")

    high_names = [e["name"] for e in events if e["impact"] == "high"]
    if alert == "alert":
        headline = "⚠ High-impact events this week — trade with caution"
        reason   = ("Major market-moving releases ahead: "
                    + ", ".join(high_names[:3])
                    + ". Expect elevated volatility and wider spreads "
                    "around release times.")
    elif alert == "warn":
        headline = "Moderate events this week — stay alert"
        reason   = ("Several medium-impact releases scheduled. Monitor "
                    "intraday volatility around release times and keep "
                    "position size conservative.")
    else:
        headline = "Quiet macro week — favorable for premium selling"
        reason   = ("No major high-impact reports scheduled. Calm backdrop "
                    "supports defined-risk premium strategies.")

    return {
        "alertLevel": alert,
        "headline": headline,
        "reason": reason,
        "events": events[:8],
        "source": source,
        "timestamp": _ts(),
    }

def _get_week_bounds():
    """Return (from_date_str, to_date_str) for Mon–Fri of the current week."""
    today = datetime.date.today()
    day   = today.weekday()  # Mon=0, Sun=6
    mon   = today - datetime.timedelta(days=day)
    fri   = mon   + datetime.timedelta(days=4)
    return mon.isoformat(), fri.isoformat()


# ─────────────────────────────────────────────
# yfinance
# ─────────────────────────────────────────────

def _spot_yfinance(ticker):
    import yfinance as yf
    t = yf.Ticker(ticker)
    info = t.fast_info
    price      = round(float(info.last_price or 0), 2)
    prev_close = float(getattr(info, "previous_close", None) or price)
    change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
    return {"price": price, "change_pct": change_pct, "source": "yfinance", "timestamp": _ts()}


def _market_data_yfinance(ticker):
    import yfinance as yf
    # Spot
    spot_data = _spot_yfinance(ticker)
    spot = spot_data["price"]

    # VIX
    vix_df = yf.download("^VIX", period="2d", interval="1d", progress=False)
    vix = round(float(vix_df["Close"].iloc[-1]), 2) if not vix_df.empty else 0.0

    # ATR(5) for the requested ticker
    hist = yf.download(ticker, period="15d", interval="1d", progress=False)
    atr5 = _round_atr(hist) if not hist.empty else 0.0

    return {
        "spot": spot,
        "vix":  vix,
        "atr5": atr5,
        "source": "yfinance",
        "timestamp": _ts(),
    }


def _eco_yfinance():
    """
    yfinance has no economic calendar API. Return a static 'unavailable'
    response so the frontend can fall back gracefully.
    """
    return {
        "alertLevel": "calm",
        "headline": "Economic calendar not available via yfinance",
        "reason": ("yfinance does not provide an economic calendar. "
                   "Switch DATA_SOURCE to 'finnhub' in .env to enable "
                   "live economic event data."),
        "events": [],
        "source": "yfinance",
        "timestamp": _ts(),
    }


# ─────────────────────────────────────────────
# Finnhub
# ─────────────────────────────────────────────

def _fh_get(path, params=None):
    import requests
    base = "https://finnhub.io/api/v1"
    p = params or {}
    p["token"] = FINNHUB_KEY
    resp = requests.get(base + path, params=p, timeout=8)
    resp.raise_for_status()
    return resp.json()


def _spot_finnhub(ticker):
    data       = _fh_get("/quote", {"symbol": ticker})
    price      = round(float(data.get("c", 0)), 2)
    change_pct = round(float(data.get("dp", 0)), 2)
    return {"price": price, "change_pct": change_pct, "source": "finnhub", "timestamp": _ts()}


def _market_data_finnhub(ticker):
    spot_data  = _spot_finnhub(ticker)
    spot       = spot_data["price"]

    # VIX via Finnhub quote (uses symbol CBOE:VIX or ^VIX depending on subscription)
    try:
        vix_data = _fh_get("/quote", {"symbol": "^VIX"})
        vix      = round(float(vix_data.get("c", 0)), 2)
    except Exception:
        vix = 0.0

    # ATR(5) via candles (resolution=D, last 15 days)
    try:
        now  = int(time.time())
        then = now - 86400 * 20  # 20 days back
        candles = _fh_get("/stock/candle",
                          {"symbol": ticker, "resolution": "D",
                           "from": then, "to": now})
        if candles.get("s") == "ok":
            import pandas as pd
            df = pd.DataFrame({
                "High":  candles["h"],
                "Low":   candles["l"],
                "Close": candles["c"],
            })
            atr5 = _round_atr(df)
        else:
            atr5 = 0.0
    except Exception:
        atr5 = 0.0

    return {"spot": spot, "vix": vix, "atr5": atr5,
            "source": "finnhub", "timestamp": _ts()}


def _eco_finnhub():
    """
    Finnhub's /calendar/economic endpoint moved behind a paid tier and now
    returns a 402 (or similar) for free-tier keys. Any failure here —
    HTTP error, timeout, malformed response — falls back to the hardcoded,
    sourced 2026 calendar in eco_calendar_2026.py rather than propagating
    a 502 up to the frontend.
    """
    try:
        from_date, to_date = _get_week_bounds()
        data = _fh_get("/calendar/economic",
                       {"from": from_date, "to": to_date})
        raw = data.get("economicCalendar", [])
        events = []
        for e in raw:
            if (e.get("country") or "").upper() != "US":
                continue
            imp = _classify_event(e.get("event", ""))
            if not imp:
                continue
            d   = datetime.datetime.fromisoformat(
                (e.get("time") or e.get("date") or "")[:10]
            )
            events.append({"day": DAY_LABELS[d.weekday() + 1 if d.weekday() < 6 else 0],
                           "name": e["event"], "impact": imp})
        return _build_eco_response(events, "finnhub")
    except Exception:
        return _eco_hardcoded_2026()


def _eco_hardcoded_2026():
    """
    Fallback economic calendar: hardcoded, sourced 2026 US macro release
    dates (FOMC, CPI, NFP, PPI, GDP, PCE) plus a computed weekly Thursday
    jobless-claims entry. See data/eco_calendar_2026.py for sources.

    Reuses _classify_event() / _build_eco_response() so the output shape
    and impact rules are identical to every other source in this file.
    """
    from data.eco_calendar_2026 import get_events

    mon_str, fri_str = _get_week_bounds()
    week_mon = datetime.date.fromisoformat(mon_str)
    week_fri = datetime.date.fromisoformat(fri_str)

    raw = get_events(week_mon, week_fri)
    events = []
    for e in raw:
        imp = _classify_event(e["name"])
        if not imp:
            continue
        d = e["date"]
        events.append({"day": DAY_LABELS[d.weekday() + 1], "name": e["name"], "impact": imp})

    return _build_eco_response(events, "hardcoded-2026")


# ─────────────────────────────────────────────
# Alpha Vantage
# ─────────────────────────────────────────────

def _av_get(params):
    import requests
    p = dict(params)
    p["apikey"] = ALPHA_VANTAGE_KEY
    resp = requests.get("https://www.alphavantage.co/query", params=p, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _spot_alphavantage(ticker):
    data  = _av_get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    quote = data.get("Global Quote", {})
    price      = round(float(quote.get("05. price", 0)), 2)
    change_pct = round(float(quote.get("10. change percent", "0").replace("%", "")), 2)
    return {"price": price, "change_pct": change_pct,
            "source": "alphavantage", "timestamp": _ts()}


def _market_data_alphavantage(ticker):
    spot_data = _spot_alphavantage(ticker)
    spot      = spot_data["price"]

    # VIX
    try:
        vix_data   = _av_get({"function": "GLOBAL_QUOTE", "symbol": "^VIX"})
        vix_quote  = vix_data.get("Global Quote", {})
        vix        = round(float(vix_quote.get("05. price", 0)), 2)
    except Exception:
        vix = 0.0

    # ATR(5) via daily OHLCV
    try:
        import pandas as pd
        ohlcv = _av_get({"function": "TIME_SERIES_DAILY", "symbol": ticker,
                         "outputsize": "compact"})
        ts    = ohlcv.get("Time Series (Daily)", {})
        rows  = []
        for date_str in sorted(ts.keys(), reverse=True)[:15]:
            v = ts[date_str]
            rows.append({"High":  float(v["2. high"]),
                         "Low":   float(v["3. low"]),
                         "Close": float(v["4. close"])})
        df   = pd.DataFrame(rows[::-1])
        atr5 = _round_atr(df)
    except Exception:
        atr5 = 0.0

    return {"spot": spot, "vix": vix, "atr5": atr5,
            "source": "alphavantage", "timestamp": _ts()}


def _eco_alphavantage():
    """Alpha Vantage has no economic calendar endpoint on free tier."""
    return {
        "alertLevel": "calm",
        "headline": "Economic calendar not available via Alpha Vantage",
        "reason": ("Alpha Vantage does not provide a free economic calendar. "
                   "Switch DATA_SOURCE to 'finnhub' in .env for live event data."),
        "events": [],
        "source": "alphavantage",
        "timestamp": _ts(),
    }


# ─────────────────────────────────────────────
# Polygon.io
# ─────────────────────────────────────────────

def _poly_get(path, params=None):
    import requests
    base = "https://api.polygon.io"
    p    = params or {}
    p["apiKey"] = POLYGON_KEY
    resp = requests.get(base + path, params=p, timeout=8)
    resp.raise_for_status()
    return resp.json()


def _spot_polygon(ticker):
    data       = _poly_get(f"/v2/last/trade/{ticker}")
    price      = round(float(data.get("results", {}).get("p", 0)), 2)
    # Polygon snapshot for change %
    try:
        snap  = _poly_get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
        day   = snap.get("ticker", {}).get("day", {})
        prev  = snap.get("ticker", {}).get("prevDay", {})
        p_c   = day.get("c", price)
        p_o   = prev.get("c", price)
        change_pct = round((p_c - p_o) / p_o * 100, 2) if p_o else 0.0
    except Exception:
        change_pct = 0.0
    return {"price": price, "change_pct": change_pct,
            "source": "polygon", "timestamp": _ts()}


def _market_data_polygon(ticker):
    spot_data = _spot_polygon(ticker)
    spot      = spot_data["price"]

    # VIX — Polygon uses index tickers like I:VIX
    try:
        vix_data = _poly_get("/v2/aggs/ticker/I:VIX/range/1/day/",
                             {"from": (datetime.date.today() - datetime.timedelta(3)).isoformat(),
                              "to": datetime.date.today().isoformat(),
                              "adjusted": "true", "sort": "desc", "limit": 1})
        vix = round(float(vix_data["results"][0]["c"]), 2)
    except Exception:
        vix = 0.0

    # ATR(5)
    try:
        import pandas as pd
        from_d = (datetime.date.today() - datetime.timedelta(20)).isoformat()
        to_d   = datetime.date.today().isoformat()
        aggs   = _poly_get(f"/v2/aggs/ticker/{ticker}/range/1/day/{from_d}/{to_d}",
                           {"adjusted": "true", "sort": "asc", "limit": 20})
        rows   = [{"High": r["h"], "Low": r["l"], "Close": r["c"]}
                  for r in aggs.get("results", [])]
        df     = pd.DataFrame(rows)
        atr5   = _round_atr(df)
    except Exception:
        atr5 = 0.0

    return {"spot": spot, "vix": vix, "atr5": atr5,
            "source": "polygon", "timestamp": _ts()}


def _eco_polygon():
    """Polygon economic calendar requires paid tier."""
    return {
        "alertLevel": "calm",
        "headline": "Economic calendar requires Polygon Starter+ plan",
        "reason": ("The economic calendar endpoint is available on Polygon.io "
                   "paid plans. Switch DATA_SOURCE to 'finnhub' for free "
                   "economic event data."),
        "events": [],
        "source": "polygon",
        "timestamp": _ts(),
    }


# ─────────────────────────────────────────────
# Public API — dispatch by DATA_SOURCE
# ─────────────────────────────────────────────

_DISPATCH = {
    "yfinance":     (_spot_yfinance,     _market_data_yfinance,     _eco_yfinance),
    "finnhub":      (_spot_finnhub,      _market_data_finnhub,      _eco_finnhub),
    "alphavantage": (_spot_alphavantage, _market_data_alphavantage, _eco_alphavantage),
    "polygon":      (_spot_polygon,      _market_data_polygon,      _eco_polygon),
}


def _get_handlers():
    handlers = _DISPATCH.get(DATA_SOURCE)
    if handlers is None:
        raise ValueError(
            f"Unknown DATA_SOURCE='{DATA_SOURCE}'. "
            f"Choose from: {', '.join(_DISPATCH.keys())}"
        )
    return handlers


def get_spot(ticker: str) -> dict:
    """Fetch current spot price and % change for a ticker."""
    fn, _, _ = _get_handlers()
    return fn(ticker.upper())


def get_market_data(ticker: str) -> dict:
    """Fetch spot price, VIX, and ATR(5) for a ticker."""
    _, fn, _ = _get_handlers()
    return fn(ticker.upper())


def get_eco_calendar() -> dict:
    """Fetch this week's US economic events, classified by impact."""
    _, _, fn = _get_handlers()
    return fn()
