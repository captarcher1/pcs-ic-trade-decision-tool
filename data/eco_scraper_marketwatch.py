"""
data/eco_scraper_marketwatch.py — MarketWatch economic-calendar scraper
========================================================================
Secondary, ADDITIVE data source for the economic-calendar panel. This is
deliberately isolated from data_fetcher.py / _eco_finnhub() / the hardcoded
2026 fallback (eco_calendar_2026.py) — a scrape failure here must never
affect the primary calendar panel.

Source page: https://www.marketwatch.com/economy-politics/calendar

Design constraints (per explicit decision):
  - requests + BeautifulSoup (lxml parser) first; this module assumes a
    server-rendered HTML table. If live testing (see README / Task #7
    in project notes) shows the table is JS-rendered and this returns no
    events, the escalation path is Playwright/headless browser — swap
    the fetch+parse internals below, keep get_mw_eco_calendar()'s
    signature and always-safe-return contract unchanged.
  - Never raises. Every failure mode (network error, HTTP error, layout
    change, empty table) is caught internally and turned into a quiet
    "unavailable" response in the same shape _build_eco_response()
    produces elsewhere in this app, so the frontend can render it with
    the exact same renderEco() JS function used for the primary panel.
  - No retry loop and no aggressive polling — one request per call, short
    timeout, fail quiet. The route that calls this should be hit at the
    same cadence as /api/eco-calendar (on page load / manual refresh),
    not on a timer, to avoid hammering MarketWatch.

NOTE: Cowork's own web-fetch tooling has MarketWatch on a domain
blocklist, so the exact current table markup could not be inspected
ahead of time. The parsing logic below tries several reasonably generic
strategies (MarketWatch has used a `calendar__table` / `calendar__row`
structure historically) and degrades to "unavailable" rather than
guessing wrong. Re-check the selectors against the live DOM the first
time this runs against a real network (see verification step) and adjust
_parse_calendar_html() if the table classes have changed.
"""

import re
import datetime

_URL = "https://www.marketwatch.com/economy-politics/calendar"
_TIMEOUT = 8

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

# Matches date-header rows like "Monday, June 22, 2026" or "Mon, Jun 22"
_DATE_RE = re.compile(
    r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})",
    re.IGNORECASE,
)
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date_header(text, ref_year):
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    month = _MONTH_MAP.get(m.group(2).lower()[:3])
    day = int(m.group(3))
    if not month:
        return None
    try:
        return datetime.date(ref_year, month, day)
    except ValueError:
        return None


def _row_is_date_header(row_text):
    # Date-header rows are short and contain a weekday name; data rows
    # contain numeric forecast/actual figures and are typically longer.
    return bool(_DATE_RE.search(row_text)) and len(row_text) < 60


def _parse_calendar_html(html, ref_year):
    """
    Returns a list of {"date": date, "name": str} for events found on the
    page, or [] if the table couldn't be located / parsed. Never raises —
    callers should still wrap this defensively in case bs4/lxml itself
    misbehaves on malformed input.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    rows = soup.find_all("tr")
    if not rows:
        return []

    events = []
    current_date = None

    for row in rows:
        row_text = row.get_text(" ", strip=True)
        if not row_text:
            continue

        if _row_is_date_header(row_text):
            parsed = _parse_date_header(row_text, ref_year)
            if parsed:
                current_date = parsed
            continue

        if current_date is None:
            continue

        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        # MarketWatch's report-name cell historically carries a class like
        # "calendar__report"; fall back to "the longest text cell" if the
        # class name has changed, since the report name is reliably the
        # longest piece of text in an economic-calendar row.
        name_cell = row.find(class_=re.compile("report", re.I))
        if name_cell is not None:
            name = name_cell.get_text(strip=True)
        else:
            texts = [c.get_text(strip=True) for c in cells]
            texts = [t for t in texts if t]
            if not texts:
                continue
            name = max(texts, key=len)

        if not name or len(name) < 3:
            continue

        events.append({"date": current_date, "name": name})

    return events


def _unavailable(reason):
    """
    Build a response in the same shape as data_fetcher._build_eco_response(),
    so the frontend's existing renderEco() works unmodified against this
    second panel too.
    """
    return {
        "alertLevel": "calm",
        "headline": "MarketWatch data unavailable",
        "reason": reason,
        "events": [],
        "source": "marketwatch-scrape",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }


def get_mw_eco_calendar() -> dict:
    """
    Scrape https://www.marketwatch.com/economy-politics/calendar for this
    week's US economic events. Always returns a dict in the standard
    { alertLevel, headline, reason, events[], source, timestamp } shape —
    on any failure it returns a quiet "unavailable" response rather than
    raising, so this can never break the primary eco-calendar panel.
    """
    try:
        import requests
        from data.data_fetcher import _classify_event, _build_eco_response, DAY_LABELS, _get_week_bounds
    except Exception as e:
        return _unavailable(f"Scraper dependencies unavailable: {e}")

    try:
        resp = requests.get(_URL, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        return _unavailable(f"Could not reach MarketWatch: {e}")

    try:
        today = datetime.date.today()
        raw_events = _parse_calendar_html(resp.text, today.year)
    except Exception as e:
        return _unavailable(f"Could not parse MarketWatch page: {e}")

    if not raw_events:
        return _unavailable(
            "MarketWatch's calendar table returned no rows — the page "
            "may require JavaScript rendering, or its layout changed."
        )

    mon_str, fri_str = _get_week_bounds()
    week_mon = datetime.date.fromisoformat(mon_str)
    week_fri = datetime.date.fromisoformat(fri_str)

    events = []
    for e in raw_events:
        d = e["date"]
        if not (week_mon <= d <= week_fri):
            continue
        imp = _classify_event(e["name"])
        if not imp:
            continue
        events.append({"day": DAY_LABELS[d.weekday() + 1], "name": e["name"], "impact": imp})

    if not events:
        return _unavailable(
            "MarketWatch page parsed but no classifiable US events were "
            "found for this week."
        )

    return _build_eco_response(events, "marketwatch-scrape")
