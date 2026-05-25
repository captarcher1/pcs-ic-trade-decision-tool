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
GET  /api/eco-calendar              → This week's US economic events

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

from data.data_fetcher import get_spot, get_market_data, get_eco_calendar

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


@app.route("/api/config")
def api_config():
    """
    GET /api/config

    Returns safe, non-sensitive config info so the frontend can
    display which data source is active.
    """
    return jsonify({
        "data_source": os.getenv("DATA_SOURCE", "yfinance"),
        "eco_calendar_available": os.getenv("DATA_SOURCE", "yfinance") == "finnhub",
    })


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"\n  PCS / IC Trade Tool  →  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
