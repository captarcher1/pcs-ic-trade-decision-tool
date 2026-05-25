# Put Credit Spread / Iron Condor Trade Decisioning Tool

A local web app that validates whether an Iron Condor (IC) or Put Credit Spread (PCS) trade meets a structured set of pre-trade filters before you enter. It fetches live market data via a Python Flask backend and renders an interactive go/no-go dashboard in your browser.

---

## Purpose

This tool applies a systematic, rule-based checklist to your options trade setup — replacing gut-feel with a repeatable framework. Each time you're considering an IC or PCS, you enter the market inputs and trade parameters; the tool evaluates each filter in sequence and returns a clear GO / CAUTION / NO-GO verdict with per-step detail.

The core philosophy: defined-risk premium selling has a structural edge, but that edge disappears fast when you trade in the wrong volatility regime, at the wrong strike distance, or with the wrong sizing. This tool is the guardrail.

---

## Logic Summary

The tool evaluates a trade through 10+ sequential checks, organized into market-level and trade-level filters:

**Market regime filters (hard stops)**
- Monday gap check: today's open must be inside Friday's high-low range. Outside gap = regime shift signal, skip the trade.
- VIX regime: VIX ≥ 30 is a hard stop. VIX 20–25 triggers a size-reduction warning.
- IV Rank (IVR): IVR < 15% means premium is too cheap to sell profitably (no edge). 15–29% is a soft warning. ≥ 30% passes.

**Strike placement**
- Short strikes are placed using an ATR-based distance formula:  
  `distance = ATR(5) × multiplier × DTE_weeks`
- The multiplier is 1.5× if price is above the 20 EMA (bullish bias) or 2.0× if below (more cushion needed).
- An additional +0.5 boost applies at 1-week DTE and +0.3 at 2-week DTE to account for elevated gamma risk.
- Strike rounding is ticker-aware: SPX rounds to $5, NDX to $10, ETFs and stocks to $1.

**DTE window**
- Optimal range: 21–35 days (3–5 weeks). Outside this window triggers a warning.

**Credit quality**
- For Iron Condors: combined credit must be ≥ 10% of average wing width.
- For Put Credit Spreads: put credit must be ≥ 10% of put wing width.
- A large imbalance between put and call credits on an IC triggers a wing-symmetry warning.

**Position sizing**
- Maximum risk per trade is capped at 5% of account size.
- The tool calculates the maximum allowed contracts and warns if you exceed the limit.

**Expectancy**
- Computed as: `POP × max_profit − (1 − POP) × max_risk`
- Assumed POP: 72% for Iron Condors, 85% for Put Credit Spreads.
- Negative expectancy is a hard no-go. Thin positive expectancy (< $25/contract) triggers a warning.

**Economic calendar**
- When Finnhub is set as the data source, the sidebar fetches this week's US macro events (FOMC, CPI, NFP, PPI, PCE, etc.) and classifies them by impact. High-impact weeks show a red ALERT banner; moderate weeks show WARN.

---

## Project Structure

```
pcs-ic-trade-decisionmaker/
├── app.py                  # Flask backend — serves UI + API routes
├── .env                    # Local config (not committed)
├── .env.example            # Template for .env — safe to share
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── data/
│   ├── __init__.py
│   └── data_fetcher.py     # Multi-source market data abstraction layer
└── templates/
    └── index.html          # Single-page frontend (served by Flask)
```

---

## Installation

**Prerequisites:** Python 3.9+

```bash
# 1. Navigate to the project folder
cd pcs-ic-trade-decisionmaker

# 2. (Recommended) Create a virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your data source
cp .env.example .env
# Open .env in a text editor and set DATA_SOURCE and any required API keys
```

---

## Usage

```bash
# Start the Flask server
python app.py

# Open your browser to:
# http://localhost:5000
```

**Workflow:**
1. Pick mode — Iron Condor or Put Credit Spread.
2. Enter your ticker (SPX, SPY, NDX, QQQ, RUT, IWM, or any equity).
3. Click ↻ next to the Spot field to auto-fetch the current price (ETFs/stocks only — index tickers like SPX require manual entry on free data tiers).
4. Fill in VIX, ATR(5), and IV Rank (manual entry or fetched via `/api/market-data`).
5. Set trade parameters: DTE, trend vs 20 EMA, Monday gap observation, account size, wing widths, and credits received.
6. Read the verdict at the top. Scroll down to review each filter step, the strike map, and the expectancy table.
7. Check the economic events panel on the right (requires Finnhub as data source).

---

## Data Source Configuration

Edit `DATA_SOURCE` in your `.env` file to switch providers. Only the API key for the selected source is required.

| Source | Key Required | Spot Price | VIX | ATR(5) | Eco Calendar | Notes |
|---|---|---|---|---|---|---|
| `yfinance` | No | ETFs/stocks | Yes (^VIX) | Yes | No | Default. Best for quick start. Index spot not available. |
| `finnhub` | Yes (free) | ETFs/stocks | Yes | Yes | **Yes** | Only source with free economic calendar. |
| `alphavantage` | Yes (free) | ETFs/stocks | Yes | Yes | No | Free tier limited to 5 req/min; 25 req/day on basic. |
| `polygon` | Yes (paid) | ETFs/stocks | Yes | Yes | Paid tier only | Best data quality; economic calendar needs Starter+ plan. |

**Index tickers (SPX, XSP, NDX, RUT):** Real-time index quotes are not available on any free data tier. Enter the spot price manually for these tickers regardless of data source.

**IV Rank:** IVR is not computed automatically — this requires a full year of historical options implied volatility data, which is unavailable on free APIs. Enter IVR manually (your broker platform will show it). A future enhancement could source this from a paid options data provider.

### Getting API Keys

- **Finnhub:** [finnhub.io](https://finnhub.io) — register for a free account, copy your key from the dashboard.
- **Alpha Vantage:** [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) — free key, instant.
- **Polygon.io:** [polygon.io/dashboard](https://polygon.io/dashboard) — paid plans start at $29/month.

---

## API Reference

The Flask backend exposes the following endpoints (useful for scripting or integration):

| Endpoint | Method | Params | Returns |
|---|---|---|---|
| `/` | GET | — | HTML UI |
| `/api/spot` | GET | `ticker` | `{ price, change_pct, source, timestamp }` |
| `/api/market-data` | GET | `ticker` | `{ spot, vix, atr5, source, timestamp }` |
| `/api/eco-calendar` | GET | — | `{ alertLevel, headline, reason, events[], source, timestamp }` |
| `/api/config` | GET | — | `{ data_source, eco_calendar_available }` |

---

## Limitations

**This tool is a pre-trade filter, not a trading system.** It evaluates structure and regime — it does not account for:

- **Real-time bid-ask spreads:** The credits you enter are assumed to be mid-price fills. Actual fills on wide-spread tickers may be worse, eroding the stated credit.
- **IV Rank accuracy:** IVR is manually entered. Inaccurate IVR inputs (particularly underestimating) can produce false GO verdicts.
- **Liquidity depth:** Open interest, volume, and slippage are not modeled. Always check order book depth, especially for single-stock options or less liquid ETF strikes.
- **Greeks:** Delta, Theta, Vega, and Gamma exposure are not calculated. The tool uses a simplified POP heuristic (72% for IC, 85% for PCS); actual POP varies by strike selection and volatility surface shape.
- **Earnings and corporate events:** The economic calendar only covers macro events. For single-stock options, always manually check earnings dates before entering.
- **Early assignment risk:** For American-style options (SPY, QQQ, IWM, single stocks), early assignment risk is flagged in the footnote but not modeled.
- **Tax treatment:** The footnote explains general principles. Individual tax situations vary. Consult a tax professional.
- **Data latency:** yfinance and free-tier APIs may have 15-minute delays. For real-time accuracy, use a paid data source or verify spot/VIX from your broker before trading.
- **IVR not auto-computed:** IV Rank requires 52 weeks of historical options IV data. This is not available on any free API and must be entered manually from your broker platform.

---

## Extending the Tool

**Add a new data source:** Implement `_spot_<name>`, `_market_data_<name>`, and `_eco_<name>` functions in `data/data_fetcher.py`, add the entry to `_DISPATCH`, and add the corresponding key to `.env.example`.

**Add auto-IVR computation:** Source historical IV from a paid provider (e.g., CBOE DataShop, Orats, or Polygon options chain), compute `(current_IV − 52w_low) / (52w_high − 52w_low) × 100`, and wire it into `/api/market-data`.

**Add broker integration:** Many brokers expose REST APIs (Tradier, TD Ameritrade/Schwab, Interactive Brokers). You could wire order placement or live position data directly into the backend.

---

## Disclaimer

This tool is provided strictly for informational and educational purposes only. It does not constitute financial, investment, tax, legal, or trading advice. No part of it should be relied upon as a recommendation to buy, sell, or hold any security or to engage in any trading strategy. Options trading involves substantial risk of loss and is not suitable for all investors. Past performance, model outputs, and hypothetical results do not guarantee future results. You are solely responsible for your own trading decisions. Always consult a qualified financial advisor, tax professional, or licensed broker before acting on any information shown here.
