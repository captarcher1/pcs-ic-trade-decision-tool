"""
data/eco_calendar_2026.py — Hardcoded, sourced 2026 US economic-release calendar
=================================================================================
Fallback for data_fetcher.py's _eco_finnhub() when Finnhub's
/calendar/economic endpoint is unavailable (it moved behind a paid tier).

This module is a pure data source. It does NOT classify impact (high/med)
or format day labels — the caller (data_fetcher.py) runs the dates
returned here through the existing _classify_event() / _build_eco_response()
helpers, so there is exactly one place in the codebase that owns impact
classification and response shape.

Sources (official, primary — verified 2026-06-24):
  FOMC : https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
  CPI  : https://www.bls.gov/schedule/news_release/cpi.htm
  NFP  : https://www.bls.gov/schedule/news_release/empsit.htm   (Employment Situation)
  PPI  : https://www.bls.gov/schedule/news_release/ppi.htm
  GDP  : https://www.bea.gov/news/schedule/full
  PCE  : https://www.bea.gov/news/schedule/full                 (Personal Income and Outlays)

Initial jobless claims are NOT hardcoded. The Department of Labor / BLS
publish this figure every single Thursday, so get_events() computes the
Thursday of the requested week on the fly rather than listing 52 dates.

Maintenance: when 2027 release schedules are published (typically each
fall for the following year), extend the *_DATES lists below the same
way, re-verify against the source URLs above, and bump LAST_VERIFIED.
"""

import datetime

LAST_VERIFIED = "2026-06-24"

# ── FOMC meeting (decision day = 2nd day of the 2-day meeting) ───────────────
FOMC_DATES = [
    datetime.date(2026, 1, 28),
    datetime.date(2026, 3, 18),
    datetime.date(2026, 4, 29),
    datetime.date(2026, 6, 17),
    datetime.date(2026, 7, 29),
    datetime.date(2026, 9, 16),
    datetime.date(2026, 10, 28),
    datetime.date(2026, 12, 9),
]

# ── CPI (Consumer Price Index), 8:30 AM ET ───────────────────────────────────
CPI_DATES = [
    datetime.date(2025, 12, 18),  # Nov 2025 data (early-Jan lookback)
    datetime.date(2026, 1, 13),
    datetime.date(2026, 2, 13),
    datetime.date(2026, 3, 11),
    datetime.date(2026, 4, 10),
    datetime.date(2026, 5, 12),
    datetime.date(2026, 6, 10),
    datetime.date(2026, 7, 14),
    datetime.date(2026, 8, 12),
    datetime.date(2026, 9, 11),
    datetime.date(2026, 10, 14),
    datetime.date(2026, 11, 10),
    datetime.date(2026, 12, 10),
]

# ── Employment Situation / Nonfarm Payrolls, 8:30 AM ET ──────────────────────
NFP_DATES = [
    datetime.date(2025, 12, 16),  # Nov 2025 data (early-Jan lookback)
    datetime.date(2026, 1, 9),
    datetime.date(2026, 2, 11),
    datetime.date(2026, 3, 6),
    datetime.date(2026, 4, 3),
    datetime.date(2026, 5, 8),
    datetime.date(2026, 6, 5),
    datetime.date(2026, 7, 2),
    datetime.date(2026, 8, 7),
    datetime.date(2026, 9, 4),
    datetime.date(2026, 10, 2),
    datetime.date(2026, 11, 6),
    datetime.date(2026, 12, 4),
]

# ── PPI (Producer Price Index), 8:30 AM ET ───────────────────────────────────
# Two early-2026 releases (Jan 14 covers Nov 2025, Jan 30 covers Dec 2025) are
# not a typo — BLS was catching up a delayed release per their own schedule.
PPI_DATES = [
    datetime.date(2026, 1, 14),
    datetime.date(2026, 1, 30),
    datetime.date(2026, 2, 27),
    datetime.date(2026, 3, 18),
    datetime.date(2026, 4, 14),
    datetime.date(2026, 5, 13),
    datetime.date(2026, 6, 11),
    datetime.date(2026, 7, 15),
    datetime.date(2026, 8, 13),
    datetime.date(2026, 9, 10),
    datetime.date(2026, 10, 15),
    datetime.date(2026, 11, 13),
    datetime.date(2026, 12, 15),
]

# ── GDP (Advance / Second / Third estimates), 8:30 AM ET ─────────────────────
GDP_DATES = [
    datetime.date(2026, 1, 22),   # Q3 2025, updated estimate
    datetime.date(2026, 2, 20),   # Q4 / full-year 2025, advance
    datetime.date(2026, 3, 13),   # Q4 / full-year 2025, second
    datetime.date(2026, 4, 9),    # Q4 / full-year 2025, third
    datetime.date(2026, 4, 30),   # Q1 2026, advance
    datetime.date(2026, 5, 28),   # Q1 2026, second
    datetime.date(2026, 6, 25),   # Q1 2026, third
    datetime.date(2026, 7, 30),   # Q2 2026, advance
    datetime.date(2026, 8, 26),   # Q2 2026, second
    datetime.date(2026, 9, 30),   # Q2 2026, third
    datetime.date(2026, 10, 29),  # Q3 2026, advance
    datetime.date(2026, 11, 25),  # Q3 2026, second
    datetime.date(2026, 12, 23),  # Q3 2026, third
]

# ── PCE / Personal Income and Outlays, 8:30-10:00 AM ET ──────────────────────
PCE_DATES = [
    datetime.date(2026, 1, 22),   # Oct & Nov 2025 data
    datetime.date(2026, 2, 20),   # Dec 2025 data
    datetime.date(2026, 3, 13),   # Jan 2026 data
    datetime.date(2026, 4, 9),    # Feb 2026 data
    datetime.date(2026, 4, 30),   # Mar 2026 data
    datetime.date(2026, 5, 28),   # Apr 2026 data
    datetime.date(2026, 6, 25),   # May 2026 data
    datetime.date(2026, 7, 30),   # Jun 2026 data
    datetime.date(2026, 8, 26),   # Jul 2026 data
    datetime.date(2026, 9, 30),   # Aug 2026 data
    datetime.date(2026, 10, 29),  # Sep 2026 data
    datetime.date(2026, 11, 25),  # Oct 2026 data
    datetime.date(2026, 12, 23),  # Nov 2026 data
]

# Event-name labels are chosen so the existing HIGH_IMPACT / MED_IMPACT
# keyword lists in data_fetcher.py's _classify_event() match them correctly
# without any change to those lists:
#   FOMC -> "fomc" (high), CPI -> "cpi"/"consumer price" (high),
#   NFP -> "nonfarm" (high), PPI -> "ppi"/"producer price" (med),
#   GDP -> "gdp" (med), PCE -> "pce" (med).
_SOURCED_EVENTS = [
    (FOMC_DATES, "FOMC Rate Decision"),
    (CPI_DATES,  "CPI (Consumer Price Index)"),
    (NFP_DATES,  "Employment Situation (Nonfarm Payrolls)"),
    (PPI_DATES,  "PPI (Producer Price Index)"),
    (GDP_DATES,  "GDP Release"),
    (PCE_DATES,  "PCE (Personal Income and Outlays)"),
]

# Last date actually covered by the sourced lists above, derived from the
# data itself rather than a separate hardcoded literal — so this can never
# drift out of sync when the *_DATES lists are extended for a future year.
# data_fetcher.py compares the requested week against this to know whether
# the sourced calendar (FOMC/CPI/NFP/PPI/GDP/PCE) actually has coverage for
# that week, or whether it's silently returning nothing for those series.
COVERAGE_END = max(d for date_list, _ in _SOURCED_EVENTS for d in date_list)


def get_events(week_mon: datetime.date, week_fri: datetime.date) -> list:
    """
    Return raw sourced events for the week spanning week_mon..week_fri
    (inclusive, both should be date objects — Monday and Friday of the
    same week). Each item is { "date": date, "name": str }.

    Impact classification and day-label formatting are intentionally left
    to the caller so this stays a pure, sourced data module.

    Always appends one computed entry: Initial Jobless Claims on the
    Thursday of the given week (DOL/BLS publish this every Thursday).
    """
    events = []
    for date_list, name in _SOURCED_EVENTS:
        for d in date_list:
            if week_mon <= d <= week_fri:
                events.append({"date": d, "name": name})

    thursday = week_mon + datetime.timedelta(days=3)
    if week_mon <= thursday <= week_fri:
        events.append({"date": thursday, "name": "Initial Jobless Claims (weekly)"})

    return events
