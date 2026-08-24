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
- **Finnhub paywall change (2026):** Finnhub moved its economic-calendar endpoint behind a paid plan — it's no longer available on the free tier. If the live Finnhub call fails for this (or any other) reason, the app automatically falls back to a hardcoded, manually-sourced 2026 macro calendar (`data/eco_calendar_2026.py` — FOMC, CPI, NFP, PPI, GDP, PCE dates) so the panel keeps working without a paid key. The fallback is silent — the panel just keeps showing events, classified the same way as live data.
- **"This week" is always computed from today's real date**, never a hardcoded year — `_get_week_bounds()` in `data/data_fetcher.py` derives it from `datetime.date.today()`. What's fixed is the underlying *data*: the FOMC/CPI/NFP/PPI/GDP/PCE dates in `data/eco_calendar_2026.py` are real, individually-sourced release dates (not something a formula can predict for future years), and currently run through `COVERAGE_END` (derived automatically from the latest date in those lists — currently late Dec 2026). If the fallback is ever asked for a week past that, it doesn't silently look calmer than it should: the panel's headline switches to "⚠ Calendar data may be incomplete this week" and the reason text says so explicitly, while still showing the one entry that *is* computed rather than sourced (the weekly Thursday jobless-claims release). **Maintenance:** each fall, when next year's release schedules are published, extend the `*_DATES` lists in `data/eco_calendar_2026.py` and bump `LAST_VERIFIED` — `COVERAGE_END` updates itself from the new data, nothing else to change.
- **Second, independent panel:** A separate "MarketWatch (scraped)" panel (`/api/eco-calendar-scraped`, backed by `data/eco_scraper_marketwatch.py`) scrapes MarketWatch's public economic calendar as an additional cross-check. It's fully isolated from the panel above — a scrape failure there shows a quiet "unavailable" message and never affects `/api/eco-calendar`.

---

## Project Structure

```
pcs-ic-trade-decisionmaker/
├── app.py                  # Flask backend — serves UI + API routes
├── .env                    # Local config (not committed)
├── .env.example            # Template for .env — safe to share
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── start_pcs_ic.bat        # Windows: auto-start script (idempotent — safe to run anytime)
├── stop_pcs_ic.bat         # Windows: manual shutdown script (no scheduled trigger by default)
├── pcs_ic_launch.ps1       # Helper used by start_pcs_ic.bat to launch app.py hidden and capture its PID
├── pcs_ic.pid              # Auto-created/deleted at runtime — tracks the running Flask process (gitignored)
├── logs/                   # Auto-created — start/stop/app stdout+stderr logs (gitignored)
├── data/
│   ├── __init__.py
│   ├── data_fetcher.py             # Multi-source market data abstraction layer
│   ├── eco_calendar_2026.py        # Hardcoded 2026 macro calendar — fallback when Finnhub fails
│   └── eco_scraper_marketwatch.py  # MarketWatch scraper — secondary, additive eco panel
└── templates/
    └── index.html          # Single-page frontend (served by Flask) — includes the entry disclaimer modal
```

---

## Installation

**Prerequisites:** Python 3.9+

```bash
# 1. Navigate to the project folder
cd pcs-ic-trade-decisionmaker

# 2. (Recommended) Create a virtual environment
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
.venv\Scripts\activate          # Windows

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
# http://localhost:5057
```

**First run in a browser:** a disclaimer modal appears before anything else — read it and click **I understand and agree** to continue. Check **Don't show this again** first if you don't want it to reappear on future visits from the same browser (it's remembered via `localStorage`, per-browser — see "Disclaimer modal" below).

**Workflow:**
1. Pick mode — Iron Condor or Put Credit Spread.
2. Enter your ticker (SPX, SPY, NDX, QQQ, RUT, IWM, or any equity).
3. Click ↻ next to the Spot field to auto-fetch the current price (ETFs/stocks only — index tickers like SPX require manual entry on free data tiers).
4. Fill in VIX, ATR(5), and IV Rank (manual entry or fetched via `/api/market-data`).
5. Set trade parameters: DTE, trend vs 20 EMA, Monday gap observation, account size, wing widths, and credits received.
6. Read the verdict at the top. Scroll down to review each filter step, the strike map, and the expectancy table.
7. Check the economic events panel on the right. With `DATA_SOURCE=finnhub`, this shows live Finnhub events if your key has calendar access, or the hardcoded 2026 fallback calendar if not (e.g., free-tier keys, since Finnhub moved this endpoint behind a paid plan). A second "MarketWatch (scraped)" panel runs independently alongside it regardless of data source.

---

## Disclaimer modal

The tool shows a one-time "Please read before continuing" modal the first time it's opened in a given browser, gating the page until you click **I understand and agree**. This is separate from — and in addition to — the always-visible Disclaimer footer at the bottom of the page.

- **Persistence:** if you check **Don't show this again**, that choice is saved to the browser's `localStorage` (key `pcsIcTool.disclaimerAcknowledged`), scoped to `http://localhost:5057` (or whatever host/port you run this on). It's per-browser, not per-user-account — a different browser, a private/incognito window, or clearing this site's data will show the notice again.
- **What it actually claims:** the modal states that your trade parameters (account size, credits, wing widths, contracts, etc.) are evaluated entirely client-side and never leave your computer, and that only the ticker symbol is sent out — to your local Flask server, then to your configured market-data provider — to fetch a live quote. This matches how the app is actually built: `calc()` in `templates/index.html` runs the whole filter/expectancy pipeline in the browser; the only network calls are `/api/spot`, `/api/market-data` (both take just `ticker`), and `/api/eco-calendar` (no params at all).
- **Where it lives:** `templates/index.html` — the modal markup is right after `<body>`, styles are under `/* Disclaimer modal */` in the `<style>` block, and the show/dismiss logic (`showDisclaimerIfNeeded()` / `acknowledgeDisclaimer()`) is near the top of the main `<script>` block.

---

## Automation (Windows — auto start / stop)

Two scripts handle starting the app in the background, idempotently, with no visible console window — same pattern used for the summer-os project, adapted here.

| Script | Purpose |
|--------|---------|
| `start_pcs_ic.bat` | Starts the Flask app if not already running. Idempotent — safe to fire multiple times or from multiple triggers at once. |
| `stop_pcs_ic.bat` | Stops the app via its recorded PID. Manual use only — no scheduled trigger calls this by default (see below). Safe if the app is already stopped. |

Logs are written to `logs\pcs_ic_start.log`, `logs\pcs_ic_stop.log`, `logs\pcs_ic_app.log`, and `logs\pcs_ic_app_err.log` (folder auto-created).

**Detection is PID-file based** (`pcs_ic.pid`), not port-based — same reasoning as summer-os: a self-managed PID file can't be fooled by something unrelated occupying the port, whereas a port check can (that's exactly what happened with Tailscale on the summer-os project). There's no known equivalent conflict on port 5057 here, but there's no cost to using the safer mechanism regardless.

**No scheduled stop trigger.** Unlike summer-os (which has a nightly auto-stop for screen-time reasons), this tool has no natural "should stop now" moment, so only start triggers are set up below. Run `stop_pcs_ic.bat` manually any time — e.g. before pulling code changes and restarting.

### Wiring up Task Scheduler

Open **PowerShell as Administrator** and run the commands below. Replace `C:\path\to\pcs-ic-trade-decisionmaker` with your actual project folder path in each command.

**A note on quoting:** these commands are written for PowerShell, not `cmd.exe` — the two escape embedded quotes differently. `\"..\"` (cmd-style) is what you'd use in a `.bat` file or Command Prompt; typed directly into PowerShell it gets misparsed and `schtasks` reports "Invalid argument/option." Since none of the path segments below contain spaces, the simplest fix is to just not quote the `/TR` value's path at all — that's what's used below. (If you ever move this project somewhere with a space in the path, wrap it in PowerShell's own escape instead: `` /TR "`"C:\path with spaces\start_pcs_ic.bat`"" ``.)

**1 — Auto-start at system logon**
```powershell
schtasks /Create /TN "PCS-IC\Start At Logon" /TR C:\path\to\pcs-ic-trade-decisionmaker\start_pcs_ic.bat /SC ONLOGON /RU SYSTEM /F
```

**2 — Auto-start at system startup**
```powershell
schtasks /Create /TN "PCS-IC\Start At Startup" /TR C:\path\to\pcs-ic-trade-decisionmaker\start_pcs_ic.bat /SC ONSTART /RU SYSTEM /F
```

**3 — Daily fallback start (safety net)**

Logon/startup triggers only fire on an actual logon or cold boot — if the machine just sleeps/locks instead, neither refires. A daily trigger closes that gap the same way it does for summer-os:
```powershell
schtasks /Create /TN "PCS-IC\Start 6AM" /TR C:\path\to\pcs-ic-trade-decisionmaker\start_pcs_ic.bat /SC DAILY /ST 06:00 /RU SYSTEM /F
```

To verify all three tasks were created:
```powershell
schtasks /Query /TN "PCS-IC" /FO LIST
```

To remove all PCS-IC tasks if needed:
```powershell
schtasks /Delete /TN "PCS-IC" /F
```

---

## Data Source Configuration

Edit `DATA_SOURCE` in your `.env` file to switch providers. Only the API key for the selected source is required.

| Source | Key Required | Spot Price | VIX | ATR(5) | Eco Calendar | Notes |
|---|---|---|---|---|---|---|
| `yfinance` | No | ETFs/stocks | Yes (^VIX) | Yes | No | Default. Best for quick start. Index spot not available. |
| `finnhub` | Yes (free) | ETFs/stocks | Yes | Yes | **Fallback*** | Live calendar now requires a paid Finnhub plan; free-tier keys automatically get the hardcoded 2026 fallback calendar instead. |
| `alphavantage` | Yes (free) | ETFs/stocks | Yes | Yes | No | Free tier limited to 5 req/min; 25 req/day on basic. |
| `polygon` | Yes (paid) | ETFs/stocks | Yes | Yes | Paid tier only | Best data quality; economic calendar needs Starter+ plan. |

\* As of 2026, Finnhub's economic-calendar endpoint is paid-tier only. If your key doesn't have access, `/api/eco-calendar` transparently falls back to `data/eco_calendar_2026.py` instead of erroring — see "Economic calendar" under Logic Summary above. The separate `/api/eco-calendar-scraped` panel (MarketWatch) is available regardless of `DATA_SOURCE`.

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
| `/api/eco-calendar` | GET | — | `{ alertLevel, headline, reason, events[], source, timestamp }` — Finnhub if your key has calendar access, else the hardcoded 2026 fallback |
| `/api/eco-calendar-scraped` | GET | — | Same shape as above, sourced by scraping MarketWatch. Independent of `DATA_SOURCE`; never affects `/api/eco-calendar`. |
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
