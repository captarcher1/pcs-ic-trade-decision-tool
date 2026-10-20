"""
app.py — Flask backend for Put Credit Spread / Iron Condor Trade Decisioning Tool
==================================================================================
Serves the HTML frontend and proxies all market data calls through
the data_fetcher abstraction layer, keeping API keys off the client.

Routes
------
GET  /                              → Render templates/index.html
GET  /api/spot?ticker=SPY           → Spot price + % change
GET  /api/market-data?ticker=SPY    → Spot + VIX + ATR(5)
GET  /api/eco-calendar              → This week's US economic events (sourced Fed/BLS/BEA release dates, 2026-2027)

Configuration
-------------
All settings live in .env — see .env.example for the full list.
"""

import os
import sys

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

# Ensure the project root is on sys.path so 'data' package is importable
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

from data.data_fetcher import get_spot, get_market_data, get_eco_calendar, ACTIVE_SOURCE
from data import option_chain

app = Flask(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _error(msg: str, status: int = 400):
    return jsonify({"error": msg}), status


def _require_ticker():
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return None, _error("'ticker' query param is required")
    return ticker, None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main HTML tool."""
    return render_template("index.html")


@app.route("/api/spot")
def api_spot():
    """
    GET /api/spot?ticker=SPY

    Returns:
        { price, change_pct, source, timestamp }
    """
    ticker, err = _require_ticker()
    if err:
        return err
    try:
        data = get_spot(ticker)
        return jsonify(data)
    except Exception as e:
        return _error(str(e), 502)


@app.route("/api/market-data")
def api_market_data():
    """
    GET /api/market-data?ticker=SPY

    Returns:
        { spot, vix, atr5, source, timestamp }

    Note: For index tickers like SPX, XSP, NDX, RUT the spot field will
    be 0 via yfinance (no free real-time feed). Users should enter these
    manually in the tool.
    """
    ticker, err = _require_ticker()
    if err:
        return err
    try:
        data = get_market_data(ticker)
        return jsonify(data)
    except Exception as e:
        return _error(str(e), 502)


@app.route("/api/eco-calendar")
def api_eco_calendar():
    """
    GET /api/eco-calendar

    Returns:
        { alertLevel, headline, reason, events[], source, timestamp }

    alertLevel: 'alert' | 'warn' | 'calm'
    events[]:   { day, name, impact }  — up to 8 items
    """
    try:
        data = get_eco_calendar()
        return jsonify(data)
    except Exception as e:
        return _error(str(e), 502)


@app.route("/api/option-candidates")
def api_option_candidates():
    """
    GET /api/option-candidates?ticker=SPX&weeks=4&put_width=25&call_width=25

    Strike candidates (|short delta| 7-15) for PCS and Iron Condor from the
    option chain. Cboe delayed quotes primary, yfinance fallback.
    """
    ticker, err = _require_ticker()
    if err:
        return err
    try:
        weeks = int(request.args.get("weeks", 4))
        put_width = float(request.args.get("put_width", 0))
        call_width = float(request.args.get("call_width", put_width))
    except ValueError:
        return _error("weeks must be an integer; widths must be numbers")
    if weeks < 1 or weeks > 52 or put_width <= 0 or call_width <= 0:
        return _error("weeks 1-52 and positive wing widths are required")
    try:
        return jsonify(option_chain.get_candidates(ticker, weeks, put_width, call_width))
    except option_chain.ChainError as e:
        return _error(str(e), 502)
    except Exception as e:
        return _error("Unexpected error: %s" % e, 500)


@app.route("/api/iv-rank")
def api_iv_rank():
    """GET /api/iv-rank?ticker=SPX -- 52-week VIX rank proxy (S&P-linked tickers only)."""
    ticker, err = _require_ticker()
    if err:
        return err
    try:
        return jsonify(option_chain.get_vix_rank(ticker))
    except option_chain.ChainError as e:
        return _error(str(e), 502)


@app.route("/api/config")
def api_config():
    """
    GET /api/config

    Returns safe, non-sensitive config info so the frontend can
    display which data source is active.
    """
    return jsonify({
        "data_source": ACTIVE_SOURCE,
    })


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.getenv("FLASK_PORT", 5057))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"\n  PCS / IC Trade Tool  ->  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
