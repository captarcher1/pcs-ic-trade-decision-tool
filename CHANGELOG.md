# Changelog

All notable changes to the PCS / Iron Condor Trade Decisioning Tool.
Format: newest first. Dates are US Eastern. The detailed save-point log (decisions, rollback notes, open items) is in `PROJECT_STATE.md`.

## 2026-10-20 — Live strike candidates, auto spot/IV rank, UI overhaul

### Added
- **Strike candidates table** built from the real option chain: short-strike |delta| between 7 and 15 (hard cap 15), closest to the 15/13/11/9/7 tiers, using your wing width and the listed expiry nearest your DTE (within 5 days; SPXW weeklies preferred for SPX).
  - Put credit spread: put rows. Iron condor: put and call rows with the same wing width on both sides.
  - Iron condor pairing switch: **Equal distance from spot** (default; call delta may go down to 1) or **Equal delta tier**. Points from spot shown under each short strike.
  - Columns: Put Δ, Long Put, Short Put, Call Δ, Short Call, Long Call, Bid, Mid, Ask, **Net credit $**, **Max risk $**, **Credit / max risk**.
  - Click a row to fill strikes and credits (mid); bid / mid / ask show under the credit boxes; the ATR strikes stay as reference text in the checks.
  - Source label and pull / quote time (Eastern) under the table; banners for fallback source, market closed and hidden strikes.
- **Data sources:** Cboe delayed quotes (primary, has delta) → yfinance bid/ask + Cboe delta when Cboe has no usable quotes (e.g. SPY) → yfinance alone with Black-Scholes delta marked "est." if Cboe is down.
- **IV rank auto-fill** from the 52-week VIX rank (proxy) for SPX / XSP / SPY; editable.
- **Automatic spot for SPX, XSP, NDX, RUT** (delayed, via Yahoo `^GSPC`, `^XSP`, `^NDX`, `^RUT`).
- **Economic calendar for 2027** (FOMC, CPI, NFP, PPI, GDP, PCE from the Fed, BLS and BEA schedules) and a "calendar data ends" warning near the end of the data.
- **Two POPs side by side** in the expectancy card (hard-coded 72% IC / 85% PCS, and delta-implied); you choose which one drives the numbers.
- **Light / dark theme toggle** (remembered in the browser), **Eastern date-time with Market is open / closed** (NYSE holidays 2026–2027 built in), darker box outlines, black / white headings, multi-column layout for validation, expectancy and leg details, and a "Built by Pranay Srivastava" footer.
- New API routes `GET /api/option-candidates` and `GET /api/iv-rank`.
- `data/option_chain.py`, `tests/test_option_chain.py` (17 offline tests), `PROJECT_STATE.md`, `CHANGELOG.md`, `scratch/test_chain_sources.py` (live source test) and `scratch/sim_skew.py` (skew simulation).
- New `.env` settings: `CHAIN_MAX_SPREAD_PCT`, `CHAIN_MIN_SPREAD_ABS`, `CHAIN_MIN_OPEN_INTEREST`, `CHAIN_IC_CALL_DELTA_FLOOR`.

### Changed
- **Credit quality check** is now credit ≥ 10% of max risk (was 10% of wing width).
- **Step 12 (expectancy) is a warning only** and can no longer cause a NO-GO.
- "How to use this tool" rewritten (6 steps) and its definitions corrected to match the real rules (NO-GO: VIX ≥ 25, IV rank < 15, Monday gap outside Friday's range, DTE outside 2–6 weeks). The VIX fail message now says "NO-GO (25 or above)" instead of "HARD STOP above 30".
- Economic-events panel now uses the sourced calendar for every `DATA_SOURCE`.
- README rewritten for non-technical readers, with install and run steps.
- Liquidity filter: short leg needs a bid and a spread ≤ 25% of mid, or ≤ $0.10; single stocks also need open interest ≥ 100.

### Removed
- **Finnhub**: all code, the config flag, UI text and docs. Note: `.env` had `DATA_SOURCE=finnhub`, so stock / ETF spot was coming from Finnhub; it now uses yfinance. An unsupported `DATA_SOURCE` falls back to yfinance with a console warning. Remove `FINNHUB_API_KEY` from your `.env` (it is no longer read).

### Known limitations
- Option data is delayed and comes from an unofficial Cboe feed; yfinance is the backup. Check live prices at your broker.
- Live results for the new IC pairing, single stocks and the hybrid source were only partly verified (SPX and SPY tested on 2026-10-20; everything else offline with sample data).
- The Cboe quote timestamp is assumed to be UTC.
- Not built: earnings-date warning for single stocks, "show hidden strikes" list, early-close (1 PM) handling.
- 2027 FOMC dates are tentative per the Fed; BLS dates can move.
- Open question: whether Equal distance or Equal delta tier should be the default IC pairing.

## Earlier history
See `git log` (baseline before this entry: `d42e5bc`).
