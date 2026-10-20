# PROJECT_STATE — PCS / IC Trade Decisioning Tool

Save-point log (Oracle-style): each save point (SP) is a named, dated marker of a known state, with what changed,
decisions made, what is verified vs. not, and how to roll back. Newest at the bottom. Add a new SP at every milestone;
never edit an old SP except to correct a factual error (note the correction).

**Current state:** SP-012 (uncommitted work on top of git `d42e5bc`)
**Owner:** Pranay · **Stack:** Flask (`app.py`, `data/`), single-file UI `templates/index.html`, `.env` config
**Run:** `start_pcs_ic.bat` (stop: `stop_pcs_ic.bat`). Restart the app after any change. Tests: `python -m unittest discover tests`

---

## Open items (live list — update at each SP)
| # | Item | Status |
|---|------|--------|
| O1 | Live source test run 2026-10-20 09:41 ET (see SP-006). SPX good; SPY Cboe zero quotes (fixed by fallback); single stocks inconclusive (spreads wide right after open) — re-run after ~10:30 | PARTIAL |
| O2 | Eco-calendar data is fixed 2026 data (`data/eco_calendar_2026.py`, ends 2026-12-23). Choose: extend 2027 / year-neutral file / live source | DONE in SP-004 (2027 dates added; data-ends warning) |
| O3 | POP is hardcoded (IC 72%, PCS 85%); delta-based POP gives negative expectancy on sample rows. Not changed. | DONE in SP-004 (both POPs shown side by side; user picks; default hard-coded) |
| O4 | Liquidity thresholds are defaults (max spread 25% of mid; min OI 100 for non-index). Tunable via `.env` `CHAIN_MAX_SPREAD_PCT`, `CHAIN_MIN_OPEN_INTEREST` | CONFIRMED by user 2026-10-20 |
| O5 | SPXW (PM-settled weeklies) preferred over SPX (AM monthly) | CONFIRMED by user 2026-10-20 |
| O6 | IC candidates pair put and call rows at the same delta tier (15/13/11/9/7) | REVISED in SP-005 (equal distance of short strikes from spot, same wing width) |
| O7 | "Net credit $" = mid × 100 × contracts entered | CONFIRMED by user 2026-10-20 |
| O8 | Earnings-in-window banner (single stocks) — designed in prototype, NOT built (no earnings data source) | NOT BUILT |
| O9 | "Show hidden strikes" link — NOT built; UI shows a count only | NOT BUILT |
| O10 | Market-closed banner uses clock only (9:30–16:00 ET Mon–Fri); exchange holidays not detected | KNOWN LIMIT |
| O11 | Cboe delayed JSON is unofficial/undocumented; terms of use not reviewed | RISK |
| O12 | README still has inaccurate claims about `/api/eco-calendar-scraped` | TO FIX |
| O13 | SPX/XSP/NDX/RUT spot now auto-fetched via Yahoo (^GSPC, ^XSP, ^NDX, ^RUT; delayed). Mapping verified with a stub only; live Yahoo response NOT yet verified | VERIFY |
| O14 | Expectancy gate (Step 12) uses max risk = larger side and POP 72%/85%; with realistic 7–15Δ credits it computes NEGATIVE expectancy on both POP bases (sample IC: −$173 hard-coded, −$225 delta-implied) so Step 12 will show No-Go. Formula unchanged pending user decision | RESOLVED in SP-005 (Step 12 is now a warning, never a hard stop; formula unchanged) |
| O15 | 2027 FOMC dates are tentative per the Fed; BLS dates can shift. Re-verify each quarter. BEA 2027 read from bea.gov/news/schedule/next-year | KNOWN LIMIT |

---

## SP-000 — Baseline (before this session's enhancements)
- Git HEAD `d42e5bc`. Strikes from ATR × multiplier × weeks; credits entered by hand; IV rank manual; credit check was ≥ 10% of wing width.
- **Rollback:** `git checkout d42e5bc -- .` (discards everything below — only after copying anything you want to keep).

## SP-001 — Credit quality = credit ≥ 10% of max risk
- `templates/index.html`: Step 9 now uses `credRiskPct = maxProfit / maxRisk × 100` (both $ per contract); amber flag below 10%; "strong" ≥ 15%, "excellent" ≥ 20%.
- Max risk rule unchanged: PCS (width − credit) × 100; IC = max(put risk, call risk).
- `README.md` credit-quality lines updated.
- **Verified:** read through + rendered via jsdom in SP-002 (Step 9 text shows "% of max risk").
- **Rollback:** `git checkout d42e5bc -- templates/index.html README.md`

## SP-002 — Strike candidates from the live option chain (Cboe primary, yfinance fallback)
**Decisions locked (from user):** Cboe primary / yfinance secondary (Cboe supplies delta); |short delta| cap 15, floor 7; tiers 15/13/11/9/7;
wing width = the width inputs; expiry nearest today + 7×weeks within ±5 days; IV rank = VIX 52-week rank proxy (S&P-linked tickers only, manual override);
yfinance delta = Black-Scholes estimate labelled "est."; show source label + pulled timestamp under the table; show bid/mid/ask next to autofilled credits; net $ column per row; IC table columns Long Put | Short Put | Short Call | Long Call.

**Added**
- `data/option_chain.py` — fetch, cache (60 s; VIX 30 min), expiry choice, candidate build, IC pairing, Black-Scholes delta, VIX rank.
- `app.py` — `GET /api/option-candidates?ticker&weeks&put_width&call_width`, `GET /api/iv-rank?ticker`.
- `templates/index.html` — "Strike candidates" panel, row select (fills strikes + credits at mid, overrides ATR strikes in `calc()`; ATR strike kept as reference text in Step 5–6), bid/mid/ask under credit boxes, IV rank auto-fill, Refresh button, fallback/market-closed/hidden-count banners, mode switch clears selection.
- `tests/test_option_chain.py` — 11 offline tests (delta band, credit math, liquidity filters, expiry choice, Cboe parse, fallback, BS delta).
- `scratch/` — `test_chain_sources.py` (live source test), `index.html.pre-candidates.bak` (UI before this SP), `patch_ui.py`, `ui_script.js` (helper copies; safe to delete).

**Verified offline:** 11/11 unit tests pass; JS syntax check; jsdom smoke test (rows render, selection fills credits/quotes/strikes, IV rank fills, mode switch, banners).
**NOT verified:** any live Cboe/yfinance response in the real app; behaviour for single stocks; 13 MB SPX download time; yfinance on `^SPX`. (→ O1)

**Rollback:** `git checkout d42e5bc -- app.py templates/index.html` and delete `data/option_chain.py`, `tests/`. Or restore only the UI: copy `scratch/index.html.pre-candidates.bak` over `templates/index.html` (keeps SP-001).

**Next steps:** run O1; settle O2–O7; then commit (not done — Claude commits only when asked).

## SP-003 — Auto spot for index tickers
- `data/data_fetcher.py`: `get_spot()` maps SPX→^GSPC, XSP→^XSP, NDX→^NDX, RUT→^RUT and uses yfinance regardless of `DATA_SOURCE`; source shown as "yfinance (index, delayed)".
- `templates/index.html`: removed the "manual entry required" block in `fetchSpot()`; spot is fetched on page load and when the ticker changes (800 ms debounce). The spot box stays editable.
- **Verified:** JS syntax, 11 unit tests, symbol mapping with a stubbed yfinance. **Not verified:** live Yahoo response.
- **Rollback:** `git checkout d42e5bc -- data/data_fetcher.py` and restore the `fetchSpot` index block from `scratch/index.html.pre-candidates.bak`.

### Decision log
- 2026-10-20: User confirmed defaults — SPXW preferred over SPX (O5); liquidity filter = bid > 0, spread ≤ 25% of mid, OI ≥ 100 for single stocks, tunable in `.env` (O4); Net credit $ = mid × 100 × contracts (O7).

## SP-004 — Calendar 2027, POP side by side, IC layout
- **O2:** `data/eco_calendar_2026.py` now holds 2026 + 2027 (FOMC, CPI, NFP, PPI, GDP, PCE) from Fed/BLS/BEA pages read 2026-10-20 (weekdays checked); `COVERAGE_END` = 2027-12-22. API returns `coverage_end`; eco panel footer shows "⚠ calendar data ends <date>" within 45 days of the end (existing in-panel warning still fires once the week is past it). File name kept as `eco_calendar_2026.py`.
- **O3:** Expectancy card shows two POP boxes side by side — Hard-coded (recommended; IC 72% / PCS 85%) and Delta-implied (calculated: PCS 1 − put Δ; IC 1 − (put Δ + call Δ); needs a selected row). Radio picks which drives Step 12 and the expectancy; default hard-coded.
- **O6:** IC rows: same delta tier on both sides and the same wing width on both sides (put wing width box drives both; selecting a row sets the call wing width box to match). Columns: Long Put | Short Put | Put Δ | Short Call | Call Δ | Long Call | Bid | Mid | Ask | Net credit $ | Credit / max risk.
- **Verified:** JS syntax, 11 unit tests, jsdom smoke (columns, equal-wing request, POP boxes, eco footer). **Not verified:** live behaviour.
- **Rollback:** UI before this SP: `scratch/index.html.pre-sp004.bak`; calendar: `git checkout d42e5bc -- data/eco_calendar_2026.py data/data_fetcher.py` (also reverts SP-003 spot change).

## SP-005 — IC pairing by equal distance from spot; Step 12 is a warning
- **O6 revised (user):** IC columns now Put Δ | Long Put | Short Put | Call Δ | Short Call | Long Call | Bid | Mid | Ask | Net credit $ | Credit / max risk. Pairing = short strikes at (about) the same distance from spot, same wing width both sides. Each row starts from a put delta tier (15/13/11/9/7), then picks the unused call (any eligible 7–15Δ call) whose distance above spot is closest. Pairs off by more than 2× typical strike spacing are skipped (count shown). Points-from-spot shown under each short strike. Call delta is therefore NOT forced to equal the put delta. Falls back to same-tier pairing only if spot is unavailable (banner says so).
- **O14:** Step 12 now `pass: true`, warns when expectancy < $25/contract (negative shows "warning only, not a stop"). No-Go can no longer come from Step 12.
- **Code:** `data/option_chain.py` (`build_all`, `pair_ic_distance`; response adds `ic_pairing`, `ic_unpaired`, per-row `dist_put/dist_call/dist_gap`); `templates/index.html`; 2 new tests (13 total).
- **Verified:** 13/13 tests, JS syntax, jsdom smoke. **Not verified:** live chain; how often skew leaves a put tier unpaired (call at equal distance may fall below 7Δ).
- **Rollback:** `scratch/option_chain.pre-sp005.bak`, `scratch/index.html.pre-sp005.bak`.

## SP-006 — First live source test (2026-10-20 09:41 ET) and Cboe zero-quote fallback
- **Results:** SPX — Cboe OK (30,004 rows, spot 7690.73; puts 3–10% below spot: n=31, zero-bid 0, median spread 3.3%, worst 4.5%); yfinance agrees (n=27, 3.2%); head-to-head SPXW 7460 put: yf 42.5/43.4 vs Cboe 42.1/43.1; Cboe delta −0.2226. Both SPX and SPXW roots exist (SPXW preferred). SPY — Cboe delta/IV present but bid/ask = 0 on all 33 in-band puts; yfinance had live quotes (4.83/4.88). AAPL — Cboe and yfinance quotes identical but spreads ~134% right after the open. ROKU/XLU — thin, many zero bids on both sources.
- **Observation:** Cboe file timestamps were ~1–5 min behind the run time, not 15 min (one morning sample).
- **Fix:** `_from_cboe` raises when fewer than 5% of strikes in the chosen expiry have a bid, so `get_candidates` falls back to yfinance (banner: "Using yfinance fallback (Cboe had no usable quotes)"). 14 tests pass.
- **Idea not built:** hybrid for ETFs/stocks — yfinance bid/ask with Cboe delta/IV (Cboe delta exists even when its quotes are zero).
- **Rollback:** `scratch/option_chain.pre-sp005.bak` predates this SP too (also reverts SP-005).

## SP-007 — Hybrid source: yfinance bid/ask + Cboe delta
- When Cboe loads but has no usable quotes for the expiry (seen live for SPY), `_from_cboe` raises `CboeNoQuotes` carrying the Cboe contracts; `_from_yfinance` then takes bid/ask from yfinance and delta from the matching Cboe contract (same expiry, put/call, strike). Strikes without a Cboe delta use Black-Scholes (labelled est.).
- Result `source` = `hybrid` (label "yfinance bid/ask + Cboe delta (hybrid)"; "some delta est." if any strike fell back to Black-Scholes) or `yfinance` (no Cboe delta at all). If Cboe fails outright (network/HTTP), it is plain yfinance with estimated delta as before.
- UI banner: "Using yfinance bid/ask (Cboe had no usable quotes). Delta is taken from Cboe." (or estimated where missing).
- **Verified:** 15/15 tests (new hybrid test: Cboe delta used, yfinance mid used, no-Cboe case estimated), JS syntax. **Not verified live** — SPY is the case to try.
- **Rollback:** `scratch/option_chain.pre-sp007.bak`, `scratch/index.html.pre-sp007.bak`.

## SP-008 — Why only 1 IC row; Finnhub removed; README rewritten
- **Why one IC row (live 2026-10-20 10:01 ET, SPX):** with equal-distance pairing, a put at the 7–15Δ tiers sits ~420–720 pts below spot, but a call that far above spot has far lower delta (skew: puts carry higher IV). The call side was limited to 7–15Δ, so only the 14.4Δ put (−419) found a call (8050, 7.0Δ, +381); 4 of 5 put tiers were unpaired.
- **Fix:** IC call side may go down to `CHAIN_IC_CALL_DELTA_FLOOR` (default 1Δ); a spread of ≤ $0.10 is always allowed (`CHAIN_MIN_SPREAD_ABS`) so cheap far strikes are not dropped by the 25% rule (deviation from the confirmed liquidity rule, needed for far-OTM calls); UI toggle **Equal distance from spot** (default) / **Equal delta tier** (always up to 5 rows; distances shown). Simulated skewed SPX chain (scratch/sim_skew.py): call floor 7% → 0 pairs, 3% → 1, 1% → 3. Real chain may differ.
- **Open question for user:** equal-distance gives ~3 rows max with very low call credits (Δ 1–5); equal-delta gives 5 rows but unequal distances. Which should be default?
- **Spot mismatch seen:** app spot (Yahoo ^GSPC) 7705.35 at 10:01 vs Cboe chain spot 7669.19 (quote time 10:00:06). Distances use the CHAIN spot. Verify against broker which is right. Not resolved.
- **Finnhub removed:** `.env` had `DATA_SOURCE=finnhub`, so stock/ETF spot WAS coming from Finnhub (also the title badge). Removed all Finnhub code (`_fh_get`, `_spot/_market_data/_eco_finnhub`), config flag `eco_calendar_available`, UI help text, `.env.example`, docs. Eco panel now always uses the sourced calendar for every DATA_SOURCE. Unknown `DATA_SOURCE` values fall back to yfinance with a console warning. `.env` DATA_SOURCE line changed to `yfinance` (only that line); `FINNHUB_API_KEY` line left in `.env` (no longer read — delete it if you want).
- **README.md** rewritten for non-technical readers: what it does, what changed, data sources, how to read the verdict, install/run steps, settings, limits. GitHub clone URL taken from `github_deployment_instructions.txt` (not re-verified).
- **Verified:** 17 unit tests; JS syntax; jsdom smoke (toggle, rows, selection); data_fetcher import with `DATA_SOURCE=finnhub` falls back and returns the calendar. **Not verified live:** the new IC row counts.
- **Rollback:** `scratch/sp008_backup/` holds the pre-SP-008 copies of app.py, data_fetcher.py, option_chain.py, eco files, index.html, .env.example, requirements.txt, README.md, github_deployment_instructions.txt. (`.env` was edited in place: set DATA_SOURCE back if needed.)

## SP-009 — "How to use this tool" brought in line with the current app
- 6 steps now: pick mode/ticker; market inputs; trade parameters (credits no longer typed); **pick strikes from the Strike candidates table** (IC pairing choice, click a row; PCS click a put row); verdict + POP choice; economic events.
- "More details": verdict text corrected to the real logic (NO-GO = VIX ≥ 25, IVR < 15, gap outside, DTE outside 2–6 weeks; expectancy removed from NO-GO and listed under CAUTION); input definitions updated (IV rank auto/proxy, DTE → expiry within 5 days, wing width shared by both IC sides, credits filled from row, ATR strikes are reference); new "Strike candidates table" section (rows, columns, pairing, hidden strikes, source label, selection cleared on change, POP choice).
- VIX fail message changed from "HARD STOP above 30" to "NO-GO (25 or above)" so it matches the actual rule (pass < 25).
- Rollback: `scratch/index.html.pre-howto.bak`. JS syntax checked; not re-run in a browser.

## SP-010 — UI enhancements (outlines, grids, theme toggle, clock, headings, footnote)
1. **Outlines:** new `--outline` variable (light `#2b2b28`, dark `rgba(255,255,255,.55)`) used on input cards, leg cards, strike-candidate card/rows, step checks, expectancy tiles, strike map card, footnote, disclaimer, mode buttons. Thin inner dividers keep the light `--border`.
2. **Layout:** step-by-step validation = 3 columns (2 on medium, 1 on phone); expectancy = 4-column tiles (2 / 1 on smaller screens); leg cards auto-fit side by side (IC: put | call | combined).
3. **Theme toggle:** button top-right ("🌙 Dark theme" / "☀ Light theme"); choice saved in `localStorage` (`pcsIcTool.theme`); with no saved choice it follows the system theme; strike-map SVG redraws on toggle.
4. **Clock + market status** on the subtitle line: Eastern time with seconds, "Market is open" / "Market is closed" (Mon–Fri 9:30–16:00 ET; NYSE full-day holidays 2026–2027 built in; early 1 PM closes not tracked). The strike-candidate "Market closed" banner now uses the same function.
5. **Headings** (`--heading`): black in light theme, white in dark theme — section labels, h1, card titles, how-to, footnote and disclaimer titles. Input labels and secondary text darkened slightly for contrast.
6. **Footer line** under the disclaimer: "Built by Pranay Srivastava"
- **Verified:** JS syntax; jsdom (toggle, clock, holiday logic, grids); Chromium screenshots of light and dark themes with sample data (not live data). Not checked on a phone-size screen.
- **Rollback:** `scratch/index.html.pre-sp010.bak`.

## SP-011 — "Max risk $" column in Strike candidates
- New column between "Net credit $ (×N)" and "Credit / max risk": Max risk $ (×N) = risk per contract × 100 × contracts, where risk = wing width − mid credit (PCS) or the larger of the put-side and call-side risk (IC) — same rule as the checks. Credit / max risk = Net credit ÷ Max risk (independent of contracts). Table note, how-to text and README updated.
- **Verified:** JS syntax; see report. Rollback: `scratch/index.html.pre-maxrisk.bak`.

## SP-012 — Packaged, change log written, pushed
- `CHANGELOG.md` added (2026-10-20 entry). Work committed on branch `feature/strike-candidates-ui-overhaul` (not on `main`) and pushed to origin; merge via pull request when ready.
- `.gitignore`: `scratch/` ignored except `test_chain_sources.py` and `sim_skew.py`. Rollback from now on = git (baseline `d42e5bc`); the local `scratch/*.bak` files are not committed.
- `.env` is untracked and ignored; a secret scan of the committed files found nothing.
