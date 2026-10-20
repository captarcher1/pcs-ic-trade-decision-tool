"""
data/option_chain.py -- Strike-candidate picker for PCS / Iron Condor
=====================================================================
Primary source : Cboe delayed-quotes JSON (has bid/ask, IV and delta).
Fallback source: yfinance option chain (no delta -> estimated with Black-Scholes).

What it does
------------
For a ticker and a DTE (in weeks) it:
  1. picks the listed expiry nearest to today + 7*weeks (within +/- EXPIRY_TOLERANCE_DAYS),
  2. keeps short strikes whose |delta| is between DELTA_FLOOR and DELTA_CAP (hard cap),
  3. builds each vertical with the wing width you supplied,
  4. returns up to len(TIER_TARGETS) candidates per side (closest to 15/13/11/9/7 delta),
  5. pairs put and call candidates at the same tier for iron condors.

Settings (module constants; a few can be overridden in .env):
  CHAIN_MAX_SPREAD_PCT   max short-leg bid-ask spread as % of mid   (default 25)
  CHAIN_MIN_SPREAD_ABS   a spread up to this many $ is always OK     (default 0.10)
  CHAIN_IC_CALL_DELTA_FLOOR  lowest call |delta| used when pairing an IC by distance (default 0.01)
  CHAIN_MIN_OPEN_INTEREST min open interest, non-index tickers      (default 100)
  RISK_FREE_RATE         used only for the yfinance delta estimate  (default 0.04)
  DIV_YIELD              used only for the yfinance delta estimate  (default 0.0;
                         SPX/XSP/SPY use ~1.3%)

Nothing here places orders. All data is delayed / indicative.
"""

import datetime
import math
import os
import re
import threading
import time
from collections import namedtuple


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
DELTA_CAP = 0.15                       # hard cap on |delta| of the short strike
DELTA_FLOOR = 0.07                     # floor on |delta| of the short strike (puts, and PCS)
IC_CALL_DELTA_FLOOR = _env_float("CHAIN_IC_CALL_DELTA_FLOOR", 0.01)   # call side of an IC may sit lower (skew)
TIER_TARGETS = (0.15, 0.13, 0.11, 0.09, 0.07)
EXPIRY_TOLERANCE_DAYS = 5              # expiry must be within +/- N days of the DTE target
MAX_SPREAD_PCT = _env_float("CHAIN_MAX_SPREAD_PCT", 25.0)
MIN_SPREAD_ABS = _env_float("CHAIN_MIN_SPREAD_ABS", 0.10)      # $ spread always allowed (cheap far-OTM strikes)
MIN_OPEN_INTEREST = int(_env_float("CHAIN_MIN_OPEN_INTEREST", 100))
RISK_FREE_RATE = _env_float("RISK_FREE_RATE", 0.04)
DIV_YIELD_DEFAULT = _env_float("DIV_YIELD", 0.0)
DIV_YIELD_BY_TICKER = {"SPX": 0.013, "XSP": 0.013, "SPY": 0.013}
CACHE_TTL_SEC = 60
MIN_QUOTED_FRACTION = 0.05             # below this share of strikes with a bid, treat the Cboe expiry as unquoted
VIX_CACHE_TTL_SEC = 1800

INDEX_TICKERS = {"SPX", "XSP", "NDX", "RUT"}
VIX_RANK_TICKERS = {"SPX", "XSP", "SPY"}      # VIX is S&P-specific
ROOT_PREFERENCE = {"SPX": ("SPXW", "SPX")}    # prefer PM-settled weeklies, fall back to monthly SPX

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json"

Contract = namedtuple("Contract", "root expiry cp strike bid ask delta iv oi volume")
_OCC = re.compile(r"^([A-Z][A-Z0-9.]*?)(\d{6})([CP])(\d{8})$")


class ChainError(Exception):
    """Raised when a source cannot supply a usable chain."""


class CboeNoQuotes(ChainError):
    """Cboe loaded but carries (almost) no bid/ask for the chosen expiry. Keeps the contracts so
    their delta can still be used with yfinance bid/ask (hybrid)."""
    def __init__(self, msg, contracts=None):
        ChainError.__init__(self, msg)
        self.contracts = contracts


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(v) else v


def _fnone(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _key(strike):
    return int(round(strike * 1000))


_cache = {}
_lock = threading.Lock()


def _cached(key, loader, ttl=CACHE_TTL_SEC):
    """Return (value, fetched_epoch_seconds); reload when older than ttl."""
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1], hit[0]
    val = loader()
    ts = time.time()
    with _lock:
        _cache[key] = (ts, val)
    return val, ts


def clear_cache():
    with _lock:
        _cache.clear()


def _iso_utc(epoch):
    return (datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc)
            .isoformat(timespec="seconds").replace("+00:00", "Z"))


# ---------------------------------------------------------------------------
# Black-Scholes delta (only used for the yfinance fallback; labelled "est.")
# ---------------------------------------------------------------------------
def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_delta(spot, strike, t_years, r, q, sigma, is_call):
    if spot <= 0 or strike <= 0 or t_years <= 0 or sigma <= 0:
        return None
    d1 = (math.log(spot / strike) + (r - q + 0.5 * sigma * sigma) * t_years) / (sigma * math.sqrt(t_years))
    disc = math.exp(-q * t_years)
    return disc * _ncdf(d1) if is_call else disc * (_ncdf(d1) - 1.0)


# ---------------------------------------------------------------------------
# Expiry choice
# ---------------------------------------------------------------------------
def choose_expiry(available, weeks, today=None, preferred_roots=None):
    """
    available: iterable of (root, date). Returns (root, date) or None.
    Nearest expiry to today + 7*weeks within +/- EXPIRY_TOLERANCE_DAYS; ties go to
    the earlier date. Roots are tried in preferred order (e.g. SPXW before SPX).
    """
    today = today or datetime.date.today()
    target = today + datetime.timedelta(days=7 * int(weeks))
    by_root = {}
    for root, d in available:
        by_root.setdefault(root, set()).add(d)
    pref = list(preferred_roots or [])
    roots = pref + [r for r in sorted(by_root) if r not in pref]
    for root in roots:
        ds = [d for d in by_root.get(root, ()) if d >= today and abs((d - target).days) <= EXPIRY_TOLERANCE_DAYS]
        if ds:
            return root, min(ds, key=lambda d: (abs((d - target).days), d))
    return None


# ---------------------------------------------------------------------------
# Candidate building (pure functions -- unit tested)
# ---------------------------------------------------------------------------
def _short_leg_ok(c, is_index):
    if c.bid <= 0 or c.ask < c.bid or c.iv <= 0:
        return False
    mid = (c.bid + c.ask) / 2.0
    spread = c.ask - c.bid
    if mid <= 0 or (spread / mid * 100.0 > MAX_SPREAD_PCT and spread > MIN_SPREAD_ABS + 1e-9):
        return False
    if not is_index and c.oi < MIN_OPEN_INTEREST:
        return False
    return True


def _make_row(tier, c, lg):
    return {
        "tier": int(round(tier * 100)),
        "short_strike": c.strike,
        "long_strike": lg.strike,
        "delta": round(abs(c.delta), 4),
        "bid": round(c.bid - lg.ask, 2),                                     # natural credit
        "mid": round((c.bid + c.ask) / 2.0 - (lg.bid + lg.ask) / 2.0, 2),
        "ask": round(c.ask - lg.bid, 2),
        "short_bid": c.bid, "short_ask": c.ask,
        "long_bid": lg.bid, "long_ask": lg.ask,
        "iv": round(c.iv, 4), "oi": c.oi, "volume": c.volume,
    }


def _eligible(contracts, cp, width, is_index, floor=None):
    """(list of (short, long) Contract pairs in the delta band that pass all filters, hidden count)."""
    floor = DELTA_FLOOR if floor is None else floor
    side = {_key(c.strike): c for c in contracts if c.cp == cp}
    eligible, hidden = [], 0
    for c in side.values():
        if c.delta is None:
            continue
        ad = abs(c.delta)
        if not (floor - 1e-9 <= ad <= DELTA_CAP + 1e-9):
            continue
        long_strike = c.strike - width if cp == "P" else c.strike + width
        lg = side.get(_key(long_strike))
        if (not _short_leg_ok(c, is_index)) or lg is None or lg.ask <= 0 or lg.ask < lg.bid:
            hidden += 1
            continue
        if (c.bid + c.ask) / 2.0 - (lg.bid + lg.ask) / 2.0 <= 0:
            hidden += 1
            continue
        eligible.append((c, lg))
    return eligible, hidden


def build_all(contracts, cp, width, is_index, floor=None):
    """Every eligible in-band vertical (not just tier picks), sorted by |delta| descending."""
    eligible, _ = _eligible(contracts, cp, width, is_index, floor)
    rows = [_make_row(abs(c.delta), c, lg) for c, lg in eligible]
    rows.sort(key=lambda r: -r["delta"])
    return rows


def build_rows(contracts, cp, width, is_index):
    """
    contracts: Contract list for ONE root + expiry. cp: 'P' or 'C'.
    Returns (rows, hidden) -- tier picks sorted by |delta| descending, hidden = number of
    in-band short strikes dropped (liquidity filter, missing/zero-ask long leg, non-positive credit).
    """
    eligible, hidden = _eligible(contracts, cp, width, is_index)
    rows, used = [], set()
    for tier in TIER_TARGETS:
        best = None
        for c, lg in eligible:
            if _key(c.strike) in used:
                continue
            dist = abs(abs(c.delta) - tier)
            if best is None or (dist, abs(c.delta)) < (best[0], abs(best[1].delta)):
                best = (dist, c, lg)
        if best:
            used.add(_key(best[1].strike))
            rows.append(_make_row(tier, best[1], best[2]))
    rows.sort(key=lambda r: -r["delta"])
    return rows, hidden


def pair_ic_distance(put_rows, call_all, spot):
    """
    Iron-condor candidates where the two SHORT strikes are (about) the same distance from spot.
    For each put tier row, pick the call (from every eligible in-band call) whose distance above spot
    is closest to the put's distance below spot. A call is used at most once. Pairs whose mismatch is
    more than 2x the typical strike spacing are skipped. Returns (pairs, unpaired_count).
    """
    strikes = sorted({r["short_strike"] for r in call_all})
    gaps = sorted(b - a for a, b in zip(strikes, strikes[1:]))
    tol = 2 * gaps[len(gaps) // 2] if gaps else 0.0
    used, out, unpaired = set(), [], 0
    for p in sorted(put_rows, key=lambda r: -r["delta"]):
        dp = spot - p["short_strike"]
        best = None
        for c in call_all:
            if _key(c["short_strike"]) in used:
                continue
            dc = c["short_strike"] - spot
            gap = abs(dc - dp)
            cand = (gap, abs(c["delta"] - p["delta"]))
            if best is None or cand < best[0]:
                best = (cand, c, dc)
        if best is None or best[0][0] > tol + 1e-9:
            unpaired += 1
            continue
        used.add(_key(best[1]["short_strike"]))
        out.append({"tier": p["tier"], "put": p, "call": best[1], "dist_put": round(dp, 2),
                    "dist_call": round(best[2], 2), "dist_gap": round(abs(best[2] - dp), 2)})
    return out, unpaired


def pair_ic(put_rows, call_rows, spot=None):
    """Iron-condor candidates: put and call rows that share the same delta tier (distances can differ)."""
    calls = {r["tier"]: r for r in call_rows}
    out = []
    for p in put_rows:
        c = calls.get(p["tier"])
        if c:
            row = {"tier": p["tier"], "put": p, "call": c}
            if spot and spot > 0:
                row["dist_put"] = round(spot - p["short_strike"], 2)
                row["dist_call"] = round(c["short_strike"] - spot, 2)
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# Cboe
# ---------------------------------------------------------------------------
def _parse_cboe(payload):
    data = (payload or {}).get("data") or {}
    opts = data.get("options") or []
    if not opts:
        raise ChainError("Cboe returned no option rows")
    out = []
    for o in opts:
        m = _OCC.match(o.get("option", "") or "")
        if not m:
            continue
        root, ymd, cp, k = m.groups()
        try:
            expiry = datetime.datetime.strptime(ymd, "%y%m%d").date()
        except ValueError:
            continue
        out.append(Contract(root, expiry, cp, int(k) / 1000.0,
                            _f(o.get("bid")), _f(o.get("ask")), _fnone(o.get("delta")),
                            _f(o.get("iv")), int(_f(o.get("open_interest"))), int(_f(o.get("volume")))))
    if not out:
        raise ChainError("Cboe rows could not be parsed")
    return out, {"spot": _fnone(data.get("current_price")), "quote_timestamp": payload.get("timestamp")}


def _load_cboe(ticker):
    import requests
    sym = ("_" + ticker) if ticker in INDEX_TICKERS else ticker

    def loader():
        try:
            r = requests.get(CBOE_URL.format(sym=sym), headers={"User-Agent": "Mozilla/5.0"}, timeout=(5, 45))
        except Exception as e:
            raise ChainError("Cboe request failed: %s" % e)
        if r.status_code != 200:
            raise ChainError("Cboe HTTP %s for %s" % (r.status_code, sym))
        try:
            contracts, meta = _parse_cboe(r.json())
        except ChainError:
            raise
        except Exception as e:
            raise ChainError("Cboe response not understood: %s" % e)
        return {"contracts": contracts, "meta": meta}

    return _cached(("cboe", sym), loader)


# ---------------------------------------------------------------------------
# yfinance (fallback)
# ---------------------------------------------------------------------------
def _yf_symbol(ticker):
    return ("^" + ticker) if ticker in INDEX_TICKERS else ticker


def _load_yf_expiries(ticker):
    try:
        import yfinance as yf
    except Exception as e:
        raise ChainError("yfinance not installed: %s" % e)
    sym = _yf_symbol(ticker)

    def loader():
        try:
            t = yf.Ticker(sym)
            exps = list(t.options or [])
        except Exception as e:
            raise ChainError("yfinance failed for %s: %s" % (sym, e))
        if not exps:
            raise ChainError("yfinance returned no expirations for %s" % sym)
        try:
            spot = float(t.fast_info.last_price)
        except Exception:
            spot = None
        return {"exps": exps, "spot": spot}

    return _cached(("yf-exp", sym), loader)


def _load_yf_chain(ticker, expiry_str):
    import yfinance as yf
    sym = _yf_symbol(ticker)

    def loader():
        try:
            ch = yf.Ticker(sym).option_chain(expiry_str)
        except Exception as e:
            raise ChainError("yfinance chain failed for %s %s: %s" % (sym, expiry_str, e))
        rows = []
        for cp, df in (("C", ch.calls), ("P", ch.puts)):
            for rec in df.to_dict("records"):
                m = _OCC.match(str(rec.get("contractSymbol", "")))
                root = m.group(1) if m else sym
                rows.append({"root": root, "cp": cp, "strike": _f(rec.get("strike")),
                             "bid": _f(rec.get("bid")), "ask": _f(rec.get("ask")),
                             "iv": _f(rec.get("impliedVolatility")),
                             "oi": int(_f(rec.get("openInterest"))), "volume": int(_f(rec.get("volume")))})
        return rows

    return _cached(("yf-chain", sym, expiry_str), loader)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _result(source, label, delta_est, pulled_ts, quote_ts, ticker, weeks, root, expiry, today,
            spot, put_width, call_width, put_rows, call_rows, hidden_put, hidden_call, call_all=None):
    unpaired = 0
    if spot and spot > 0 and call_all is not None:
        ic, unpaired = pair_ic_distance(put_rows, call_all, spot)
        pairing = "distance"
    else:
        ic = pair_ic(put_rows, call_rows)
        pairing = "tier"
    ic_delta = pair_ic(put_rows, call_rows, spot)
    msg = None
    if expiry is None:
        msg = "No listed expiry within %d days of your %d-week DTE target." % (EXPIRY_TOLERANCE_DAYS, weeks)
    elif not put_rows and not call_rows:
        msg = "No strikes between %d and %d delta passed the liquidity and wing-width checks for this expiry." % (
            round(DELTA_FLOOR * 100), round(DELTA_CAP * 100))
    return {
        "ok": True, "ticker": ticker, "source": source, "source_label": label,
        "delta_estimated": delta_est, "pulled_at": _iso_utc(pulled_ts), "quote_timestamp": quote_ts,
        "root": root, "expiry": expiry.isoformat() if expiry else None,
        "dte": (expiry - today).days if expiry else None, "target_dte": 7 * int(weeks),
        "spot": spot, "delta_cap": round(DELTA_CAP * 100), "delta_floor": round(DELTA_FLOOR * 100),
        "put_width": put_width, "call_width": call_width,
        "put_rows": put_rows, "call_rows": call_rows, "ic_rows": ic,
        "ic_rows_delta": ic_delta,
        "ic_pairing": pairing, "ic_unpaired": unpaired, "ic_call_floor": round(IC_CALL_DELTA_FLOOR * 100),
        "hidden": {"put": hidden_put, "call": hidden_call},
        "limits": {"max_spread_pct": MAX_SPREAD_PCT, "min_spread_abs": MIN_SPREAD_ABS, "min_open_interest": MIN_OPEN_INTEREST,
                   "expiry_tolerance_days": EXPIRY_TOLERANCE_DAYS},
        "message": msg,
    }


def _from_cboe(ticker, weeks, put_width, call_width, is_index, today):
    data, ts = _load_cboe(ticker)
    contracts = data["contracts"]
    pick = choose_expiry([(c.root, c.expiry) for c in contracts], weeks, today, ROOT_PREFERENCE.get(ticker))
    if pick is None:
        return _result("cboe", "Cboe delayed quotes (primary)", False, ts, data["meta"]["quote_timestamp"],
                       ticker, weeks, None, None, today, data["meta"]["spot"], put_width, call_width, [], [], 0, 0)
    root, expiry = pick
    chain = [c for c in contracts if c.root == root and c.expiry == expiry]
    quoted = sum(1 for c in chain if c.bid > 0)
    if chain and quoted < MIN_QUOTED_FRACTION * len(chain):
        # seen live for SPY: Cboe's delayed file carried zero bid/ask on every strike
        raise CboeNoQuotes("Cboe has no usable bid/ask for %s %s (%d of %d strikes quoted)" % (
            ticker, expiry.isoformat(), quoted, len(chain)), contracts)
    put_rows, hp = build_rows(chain, "P", put_width, is_index)
    call_rows, hc = build_rows(chain, "C", call_width, is_index)
    call_all = build_all(chain, "C", call_width, is_index, IC_CALL_DELTA_FLOOR)
    return _result("cboe", "Cboe delayed quotes (primary)", False, ts, data["meta"]["quote_timestamp"],
                   ticker, weeks, root, expiry, today, data["meta"]["spot"], put_width, call_width,
                   put_rows, call_rows, hp, hc, call_all)


def _from_yfinance(ticker, weeks, put_width, call_width, is_index, today, cboe_contracts=None):
    """yfinance bid/ask. Delta: taken from matching Cboe contracts when supplied (hybrid), else Black-Scholes."""
    info, ts_exp = _load_yf_expiries(ticker)
    spot = info["spot"]
    avail = [("*", datetime.date.fromisoformat(e)) for e in info["exps"]]
    pick = choose_expiry(avail, weeks, today)
    if pick is None:
        return _result("yfinance", "yfinance (fallback)", True, ts_exp, None, ticker, weeks, None, None,
                       today, spot, put_width, call_width, [], [], 0, 0)
    expiry = pick[1]
    raw, ts = _load_yf_chain(ticker, expiry.isoformat())
    if not spot or spot <= 0:
        raise ChainError("yfinance: spot price unavailable, cannot estimate delta")
    # SPX: Yahoo can mix SPX (monthly) and SPXW (weekly) rows on one date -- prefer the weekly root
    roots = {r["root"] for r in raw}
    root = next((r for r in ROOT_PREFERENCE.get(ticker, ()) if r in roots), None)
    rows_raw = [r for r in raw if root is None or r["root"] == root]
    t_years = max((expiry - today).days, 1) / 365.0
    q = DIV_YIELD_BY_TICKER.get(ticker, DIV_YIELD_DEFAULT)
    cboe_delta = {}
    for c in (cboe_contracts or []):
        if c.expiry == expiry and c.delta is not None:
            cboe_delta[(c.cp, _key(c.strike))] = c.delta
    chain, n_cboe, n_est = [], 0, 0
    for r in rows_raw:
        delta = cboe_delta.get((r["cp"], _key(r["strike"])))
        if delta is not None:
            n_cboe += 1
        elif r["iv"] >= 0.01:
            delta = bs_delta(spot, r["strike"], t_years, RISK_FREE_RATE, q, r["iv"], r["cp"] == "C")
            n_est += 1 if delta is not None else 0
        chain.append(Contract(r["root"], expiry, r["cp"], r["strike"], r["bid"], r["ask"], delta,
                              r["iv"], r["oi"], r["volume"]))
    if n_cboe and not n_est:
        src, label, est = "hybrid", "yfinance bid/ask + Cboe delta (hybrid)", False
    elif n_cboe:
        src, label, est = "hybrid", "yfinance bid/ask + Cboe delta (hybrid; some delta est.)", True
    else:
        src, label, est = "yfinance", "yfinance (fallback)", True
    put_rows, hp = build_rows(chain, "P", put_width, is_index)
    call_rows, hc = build_rows(chain, "C", call_width, is_index)
    call_all = build_all(chain, "C", call_width, is_index, IC_CALL_DELTA_FLOOR)
    return _result(src, label, est, ts, None, ticker, weeks,
                   root or (rows_raw[0]["root"] if rows_raw else None), expiry, today, spot,
                   put_width, call_width, put_rows, call_rows, hp, hc, call_all)


def get_candidates(ticker, weeks, put_width, call_width, today=None):
    """Main entry point used by the Flask route."""
    ticker = (ticker or "").upper().strip()
    if not ticker:
        raise ChainError("ticker is required")
    weeks = max(1, int(weeks))
    put_width, call_width = float(put_width), float(call_width)
    if put_width <= 0 or call_width <= 0:
        raise ChainError("wing widths must be positive")
    today = today or datetime.date.today()
    is_index = ticker in INDEX_TICKERS
    try:
        return _from_cboe(ticker, weeks, put_width, call_width, is_index, today)
    except ChainError as cboe_err:
        try:
            res = _from_yfinance(ticker, weeks, put_width, call_width, is_index, today,
                                 getattr(cboe_err, "contracts", None))
        except ChainError as yf_err:
            raise ChainError("Cboe: %s | yfinance: %s" % (cboe_err, yf_err))
        res["fallback_reason"] = str(cboe_err)
        return res


# ---------------------------------------------------------------------------
# IV rank proxy from VIX history
# ---------------------------------------------------------------------------
def get_vix_rank(ticker):
    """
    52-week VIX rank = (current - 52wk low) / (52wk high - 52wk low) * 100, from daily
    closes of ^VIX via yfinance. A PROXY for S&P-linked tickers only (SPX, XSP, SPY).
    """
    t = (ticker or "").upper().strip()
    if t not in VIX_RANK_TICKERS:
        return {"applicable": False,
                "reason": "VIX-based rank only applies to S&P-linked tickers (%s)" % ", ".join(sorted(VIX_RANK_TICKERS))}

    def loader():
        try:
            import yfinance as yf
            hist = yf.Ticker("^VIX").history(period="1y", interval="1d")
            closes = [float(x) for x in hist["Close"].dropna().tolist()]
        except Exception as e:
            raise ChainError("VIX history failed: %s" % e)
        if len(closes) < 120:
            raise ChainError("VIX history too short (%d days)" % len(closes))
        return closes

    closes, ts = _cached(("vix-1y",), loader, ttl=VIX_CACHE_TTL_SEC)
    cur, lo, hi = closes[-1], min(closes), max(closes)
    rank = 0.0 if hi == lo else (cur - lo) / (hi - lo) * 100.0
    return {"applicable": True, "rank": round(rank, 1), "vix": round(cur, 2), "low": round(lo, 2),
            "high": round(hi, 2), "days": len(closes), "pulled_at": _iso_utc(ts),
            "label": "VIX 52-wk rank (proxy)"}
