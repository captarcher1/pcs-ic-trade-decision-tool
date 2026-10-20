# PCS / Iron Condor Trade Decisioning Tool

A small web page that helps you decide whether to open a **put credit spread (PCS)** or an **iron condor (IC)** — and which strikes to use.
You type in a few market numbers, and the tool gives you a clear **GO / CAUTION / NO-GO**, a list of real option strikes to pick from,
and the money maths (credit, max risk, breakeven, expected value).

> **Not financial advice.** This is a decision aid. Data is delayed and can be wrong. You are responsible for every trade.

---

## What it does (in plain words)

1. **Checks the market** — VIX, IV rank, trend, the Monday gap, and this week's big economic releases.
2. **Suggests strikes from the live option chain** — a short table of real strikes you can click. No guessing prices.
3. **Does the maths** — credit, max risk, breakeven, how many contracts your account allows (5% rule), and expected value.
4. **Gives a verdict** — GO, CAUTION or NO-GO, with each check listed so you can see *why*.

---

## What's new (and how the logic changed)

| Before | Now |
|---|---|
| Strikes came only from an ATR formula, often far from what you actually trade | **Strike candidates table** built from the real option chain, **short delta 15 or lower** |
| Credits typed by hand | **Click a row** and the strikes and credits fill in automatically (bid / mid / ask shown next to the credit boxes) |
| Credit check = 10% of the wing width | Credit check = **credit ≥ 10% of max risk** |
| IV rank typed by hand | **Auto-filled** from the VIX 52-week rank for SPX / XSP / SPY (a proxy), still editable |
| SPX spot typed by hand | **SPX, XSP, NDX, RUT spot fetched automatically** (delayed) |
| Economic calendar was 2026 only | **2026 and 2027** release dates (Fed, BLS, BEA), with a warning when the data is about to run out |
| Expectancy hard-stopped the trade | **Warning only** — it can no longer cause a NO-GO |
| One fixed win-rate (POP) | **Two POPs side by side** — you choose which one drives the numbers |
| Finnhub data source | **Removed** (yfinance is the default) |

### How the strike candidates are chosen

- The tool finds the option expiry **closest to your DTE (weeks)**, within 5 days. For SPX it prefers the **SPXW weekly** options.
- It keeps short strikes with **delta between 7 and 15** (never above 15). Delta is roughly "the market's chance this strike gets hit".
- It builds each spread with **your wing width**.
- It shows up to 5 rows, closest to **15 / 13 / 11 / 9 / 7 delta**.
- **Put credit spread:** put rows only.
- **Iron condor:** put and call rows together, same wing width on both sides. You choose how the two short strikes are paired:
  - **Equal distance from spot** (default): both short strikes are about the same number of points from the current price.
    Calls are cheaper than puts, so the call side has a lower delta (the tool allows down to 1). Fewer rows may qualify.
  - **Equal delta tier:** both short strikes have a similar delta. You always get more rows, but the call is closer to the price than the put.
- Strikes are **hidden** if the short leg has no bid, a wide bid-ask spread (more than 25% of the mid, unless the spread is $0.10 or less),
  no usable long leg at your wing width, or (single stocks) open interest below 100.
- Each row shows **Bid / Mid / Ask**, **Net credit $** (mid × 100 × contracts), **Max risk $** (PCS: (wing width − credit) × 100 × contracts; IC: the larger of the put side and the call side) and **Credit / max risk** (net credit ÷ max risk, green at 10% or more).

### Where the data comes from

| What | Source |
|---|---|
| Option chain, bid/ask, delta | **Cboe delayed quotes** (primary). Free, but unofficial, so it could change without notice. |
| If Cboe has no usable quotes (seen with SPY) | **yfinance bid/ask + Cboe delta** ("hybrid") |
| If Cboe is down | **yfinance** with delta estimated by a standard formula, marked "est." |
| Spot price | yfinance (SPX uses `^GSPC`) |
| IV rank | 52-week VIX rank (a proxy, not a true per-ticker IV rank) |
| Economic events | Fixed, official release dates stored in `data/eco_calendar_2026.py` (covers 2026–2027) |

The source and the time the data was pulled are shown **under the table**. Quotes are delayed by a few minutes, and after hours they can be stale.

---

## How to read the verdict

| Check | What it looks at |
|---|---|
| Monday gap | Inside Friday's range = OK. Outside = skip. |
| VIX | Calm is fine. 20–25 = caution. 25 or higher = fail. |
| IV rank | 30 or more is healthy. 15–30 = thin edge (caution). Under 15 = fail. |
| Trend / ATR | Above the 20 EMA uses a 1.5× ATR distance; below uses 2.0× (plus a small boost for 1–2 week DTE). Used for the reference strikes. |
| DTE | 3–5 weeks is the sweet spot. |
| Strike placement | Shows your chosen strikes versus the ATR reference strikes. |
| Credit quality | **Credit ≥ 10% of max risk.** Below = caution. |
| Wing symmetry (IC) | Put and call credits within $1.50 of each other. |
| Position size | Max risk of the trade must be within **5% of your account**. |
| Expectancy | **Warning only.** Win rate × profit minus loss rate × risk. |

**Max risk:** PCS = (wing width − credit) × 100. IC = the larger of the put side and call side.

**Two POPs (probability of profit):**
- **Hard-coded (recommended):** 85% for a PCS, 72% for an IC. A fixed assumption, not calculated from data.
- **Delta-implied (calculated):** PCS = 1 − short put delta. IC = 1 − (put delta + call delta). Needs a selected row.

---

## Install and run

You need **Python 3.10 or newer** (https://www.python.org/downloads/). On Windows, tick "Add Python to PATH" when installing.

**1. Download**
- With Git: `git clone https://github.com/captarcher1/pcs-ic-trade-decision-tool.git`
- Or on GitHub click **Code → Download ZIP** and unzip it.

**2. Open a terminal in the project folder**, then create a private Python environment and install the packages:

Windows (Command Prompt or PowerShell):
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```
Mac / Linux:
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**3. Create your settings file.** Copy `.env.example` to `.env`. The defaults work as they are (no API key needed).

**4. Start the app**

Windows: `.venv\Scripts\python.exe app.py`
Mac / Linux: `.venv/bin/python app.py`

**5. Open** http://localhost:5057 in your browser. Stop the app with Ctrl+C.

**Windows shortcut:** double-click `start_pcs_ic.bat` to start it in the background and `stop_pcs_ic.bat` to stop it.
After changing any code, stop and start the app again, then refresh the browser with Ctrl+F5.
If the page looks old, another copy may still be running — check with `netstat -ano | findstr :5057` and stop it.

### Using it

1. Pick **Put credit spread** or **Iron condor**.
2. Enter the **ticker** (spot fills in by itself), **VIX**, **ATR(5)**, **DTE (weeks)**, trend, Monday gap, account size, wing width and contracts.
3. Look at the **Strike candidates** table. Click a row to fill in the strikes and credits.
4. Read the verdict, the strike map and the check list. Change the POP choice if you want to compare.

VIX and ATR(5) are typed in by you. Spot, IV rank (SPX / XSP / SPY) and the option chain fill in by themselves.

---

## Settings (`.env`)

| Setting | Meaning | Default |
|---|---|---|
| `DATA_SOURCE` | Where stock/ETF spot comes from: `yfinance`, `alphavantage` or `polygon` | `yfinance` |
| `ALPHA_VANTAGE_API_KEY`, `POLYGON_API_KEY` | Only needed if you choose those sources | empty |
| `FLASK_PORT` | Port the page runs on | `5057` |
| `CHAIN_MAX_SPREAD_PCT` | Hide strikes whose bid-ask spread is wider than this % of mid | `25` |
| `CHAIN_MIN_SPREAD_ABS` | Spread in $ that is always allowed (cheap far strikes) | `0.10` |
| `CHAIN_MIN_OPEN_INTEREST` | Minimum open interest for single stocks | `100` |
| `CHAIN_IC_CALL_DELTA_FLOOR` | Lowest call delta used in "equal distance" iron condors | `0.01` |

Never share your `.env` file — it can hold API keys.

---

## Limits to keep in mind

- All option data is **delayed** and comes from a free, **unofficial** Cboe feed. Check your broker's live prices before trading.
- Right after the open, spreads are wide and many strikes can be hidden. Quotes are better after about 10:00 AM ET.
- IV rank for non-S&P tickers is manual. Single stocks often have few liquid strikes.
- The "market closed" banner uses the clock only; it does not know exchange holidays.
- Economic dates for 2027 are tentative (the Fed and BLS can change them). The tool warns you when the date data is running out.
- Not built: earnings-date warning for single stocks, and a "show hidden strikes" list.

---

## For developers

```
app.py                      Flask server and API routes
data/option_chain.py        Option chain, strike candidates, delta, VIX rank
data/data_fetcher.py        Spot price and economic-calendar routing
data/eco_calendar_2026.py   Official release dates (2026-2027)
templates/index.html        The whole page (HTML, CSS, JavaScript)
tests/                      Offline unit tests
PROJECT_STATE.md            Save-point log: what changed, decisions, open items, rollback notes
start_pcs_ic.bat / stop_pcs_ic.bat   Windows start / stop helpers
```

| Route | Returns |
|---|---|
| `GET /api/spot?ticker=SPY` | Price and % change |
| `GET /api/option-candidates?ticker=SPX&weeks=4&put_width=25&call_width=25` | Strike candidate rows, source, pull time |
| `GET /api/iv-rank?ticker=SPX` | VIX 52-week rank (S&P tickers only) |
| `GET /api/eco-calendar` | This week's economic events |
| `GET /api/config` | Active data source |

Run the tests (no internet needed): `python -m unittest discover tests`
