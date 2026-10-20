r"""
scratch/test_chain_sources.py -- READ-ONLY connectivity/quality test (v2).
Does not import or modify the app. Tests free option-chain sources
(yfinance and Cboe delayed JSON) and writes a report to
scratch/chain_test_results.txt.

Run from the project folder (best at ~10:30 AM ET on a trading day):
    .venv\Scripts\python.exe scratch\test_chain_sources.py
Optional: choose your own stocks/ETFs to test:
    .venv\Scripts\python.exe scratch\test_chain_sources.py AAPL ROKU XLU
"""
import datetime, io, json, os, re, statistics, sys, traceback

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_test_results.txt")
DEFAULT_EXTRA = ["AAPL", "ROKU", "XLU"]   # mega-cap, mid-cap, thinner ETF
INDEX_MAP = {"^SPX": "_SPX"}               # yfinance symbol -> Cboe symbol
lines = []

def log(s=""):
    print(s); lines.append(str(s))

def parse_utc(ts):
    try:
        return datetime.datetime.fromisoformat(str(ts)).astimezone(datetime.timezone.utc)
    except Exception:
        return None

def pick_expiry(exps, min_days=21):
    today = datetime.date.today()
    return next((e for e in exps if (datetime.date.fromisoformat(e) - today).days >= min_days), exps[-1])

def third_friday_expiry(exps, min_days=21):
    today = datetime.date.today()
    for e in exps:
        d = datetime.date.fromisoformat(e)
        if (d - today).days >= min_days and d.weekday() == 4 and 15 <= d.day <= 21:
            return e
    return None

def prefix_counts(symbols):
    out = {}
    for s in symbols:
        m = re.match(r"^([A-Z]+)\d", s)
        k = m.group(1) if m else "?"
        out[k] = out.get(k, 0) + 1
    return out

def quality(label, rows, spot):
    """rows: list of dicts with strike,bid,ask,volume,oi. Puts 3%-10% below spot."""
    band = [r for r in rows if spot and 0.90 * spot <= r["strike"] <= 0.97 * spot]
    zero = [r for r in band if not r["bid"] and not r["ask"]]
    no_bid = [r for r in band if not r["bid"]]
    spreads = [(r["ask"] - r["bid"]) / ((r["ask"] + r["bid"]) / 2) * 100
               for r in band if r["bid"] and r["ask"] and r["ask"] >= r["bid"]]
    med = f"{statistics.median(spreads):.1f}%" if spreads else "n/a"
    worst = f"{max(spreads):.1f}%" if spreads else "n/a"
    log(f"    [{label}] puts 3-10% below spot: n={len(band)}, both-zero={len(zero)}, "
        f"zero-bid={len(no_bid)}, median spread={med}, worst spread={worst}")

def yf_rows(df):
    out = []
    for _, r in df.iterrows():
        out.append({"sym": r["contractSymbol"], "strike": float(r["strike"]),
                    "bid": float(r["bid"] or 0), "ask": float(r["ask"] or 0),
                    "iv": float(r.get("impliedVolatility") or 0),
                    "last_ts": r.get("lastTradeDate")})
    return out

_cboe_cache = {}
def fetch_cboe(sym):
    if sym in _cboe_cache:
        return _cboe_cache[sym]
    import requests
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    _cboe_cache[sym] = r.json()
    return _cboe_cache[sym]

def test_ticker(yf_sym):
    cboe_sym = INDEX_MAP.get(yf_sym, yf_sym)
    log("")
    log(f"=== {yf_sym}  (Cboe symbol: {cboe_sym}) ===")
    spot = None
    cboe = None
    try:
        cboe = fetch_cboe(cboe_sym)
        d = cboe.get("data", {})
        spot = d.get("current_price")
        log(f"  Cboe: OK, rows={len(d.get('options', []))}, file timestamp={cboe.get('timestamp')}, "
            f"spot={spot}, underlying bid/ask={d.get('bid')}/{d.get('ask')}")
    except Exception as e:
        log(f"  Cboe: ERROR {type(e).__name__}: {str(e)[:200]}")

    try:
        import yfinance as yf
        t = yf.Ticker(yf_sym)
        exps = t.options
        log(f"  yfinance: {len(exps)} expirations; first 5: {list(exps[:5])}")
        if not exps:
            log("  yfinance: NO EXPIRATIONS"); return
        if not spot:
            try:
                spot = float(t.fast_info.last_price)
            except Exception:
                spot = None
        log(f"  spot used for banding: {spot}")
        expiry = pick_expiry(exps)
        log(f"  testing expiry {expiry} (first >= 21 days out)")
        ch = t.option_chain(expiry)
        rows = yf_rows(ch.puts)
        quality("yfinance", rows, spot)

        # staleness of last trades in the band
        now = datetime.datetime.now(datetime.timezone.utc)
        ages = []
        for r in rows:
            ts = parse_utc(r["last_ts"])
            if ts and spot and 0.90 * spot <= r["strike"] <= 0.97 * spot:
                ages.append((now - ts).total_seconds() / 3600)
        if ages:
            log(f"    yfinance last-trade age (hours) in band: min={min(ages):.1f}, "
                f"median={statistics.median(ages):.1f}, max={max(ages):.1f}")

        # Cboe same expiry
        if cboe:
            tag = datetime.date.fromisoformat(expiry).strftime("%y%m%d")
            crow = []
            for o in cboe["data"]["options"]:
                s = o.get("option", "")
                m = re.match(r"^([A-Z]+)(\d{6})([CP])(\d{8})$", s)
                if m and m.group(2) == tag and m.group(3) == "P":
                    crow.append({"sym": s, "strike": int(m.group(4)) / 1000.0,
                                 "bid": float(o.get("bid") or 0), "ask": float(o.get("ask") or 0),
                                 "iv": float(o.get("iv") or 0), "delta": o.get("delta"),
                                 "last_ts": o.get("last_trade_time")})
            quality("Cboe    ", crow, spot)

            # head-to-head on one contract near 3% OTM
            if rows and crow and spot:
                target = 0.97 * spot
                pick = min(rows, key=lambda r: abs(r["strike"] - target))
                match = next((c for c in crow if c["sym"] == pick["sym"]), None)
                log(f"  Head-to-head put {pick['sym']} (strike {pick['strike']}):")
                log(f"    yfinance: bid={pick['bid']} ask={pick['ask']} mid={(pick['bid']+pick['ask'])/2:.2f} iv={pick['iv']:.4f}")
                if match:
                    log(f"    Cboe    : bid={match['bid']} ask={match['ask']} mid={(match['bid']+match['ask'])/2:.2f} "
                        f"iv={match['iv']:.4f} delta={match['delta']}")
                else:
                    log("    Cboe    : contract symbol NOT FOUND (symbol formats differ?)")

        # SPX only: do monthly (SPX) and weekly (SPXW) contracts mix?
        if yf_sym == "^SPX":
            log(f"  Symbol prefixes at {expiry}: {prefix_counts([r['sym'] for r in rows])}")
            tf = third_friday_expiry(exps)
            if tf:
                chm = t.option_chain(tf)
                log(f"  Third-Friday expiry {tf}: puts prefixes {prefix_counts(list(chm.puts['contractSymbol']))}")
            else:
                log("  No third-Friday expiry >= 21 days found to test SPX vs SPXW")
    except Exception as e:
        log(f"  yfinance: ERROR {type(e).__name__}: {str(e)[:300]}")
        log(traceback.format_exc()[-500:])

if __name__ == "__main__":
    extra = [a.upper() for a in sys.argv[1:]] or DEFAULT_EXTRA
    now_local = datetime.datetime.now()
    log(f"Run at local {now_local.isoformat(timespec='seconds')} (UTC {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')})  python {sys.version.split()[0]}")
    open_window = now_local.weekday() < 5 and (9, 30) <= (now_local.hour, now_local.minute) < (16, 0)
    log("Market-hours check (assumes this PC is on Eastern time): " +
        ("INSIDE regular hours" if open_window else "OUTSIDE regular hours -> zero bids/stale quotes expected"))
    for sym in ["^SPX", "SPY"] + extra:
        test_ticker(sym)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved to {OUT}")
