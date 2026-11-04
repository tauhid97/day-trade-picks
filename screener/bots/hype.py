"""HYPE BOT - how much people on Reddit are talking about a stock (r/wallstreetbets, r/stocks, ...).

PRACTICE ONLY: the label is shown on each pick and saved, but it never blocks a trade.
Hype can push a stock up - and often ends in a drop - so the Study bot checks which way
it really goes. There's no free history, so every evening we save a snapshot and the
Study bot learns from those as they pile up.

hype  = 20+ mentions today and at least 2x as many as 24 hours ago
buzz  = 20+ mentions today (lots of talk, but not rising fast)
quiet = few or no mentions

Data (free, no key): apewisdom.io, which counts stock mentions on Reddit.
"""
import os

import pandas as pd
import requests

from .. import config as C

FEED = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/{}"
MAX_PAGES = 7          # ~100 stocks per page
MIN_MENTIONS = 20
HYPE_RATIO = 2.0
WORDS = {"hype": "🔥 HYPE", "buzz": "💬 BUZZ", "quiet": "QUIET", "unknown": "UNKNOWN"}

_cache = {}


def fetch():
    """{ticker: {"mentions": today, "mentions_24h_ago": yesterday}} for every stock the feed lists."""
    out = {}
    for page in range(1, MAX_PAGES + 1):
        r = requests.get(FEED.format(page), headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        d = r.json()
        for row in d.get("results", []):
            out[row["ticker"].upper()] = {"mentions": row.get("mentions"), "mentions_24h_ago": row.get("mentions_24h_ago")}
        if page >= int(d.get("pages") or 1):
            break
    return out


def _data():
    if "d" not in _cache:
        _cache["d"] = fetch()
    return _cache["d"]


def level(mentions, before):
    m, b = int(mentions or 0), int(before or 0)
    if m >= MIN_MENTIONS and m >= HYPE_RATIO * max(b, 1):
        return "hype"
    return "buzz" if m >= MIN_MENTIONS else "quiet"


def check(ticker):
    """(tag, note) for one stock right now."""
    try:
        row = _data().get(ticker.upper().replace("-", "."))
    except Exception as e:
        print("Hype bot skipped:", e)
        return "unknown", "Reddit data unavailable"
    if not row:
        return "quiet", "hardly mentioned on Reddit"
    m, b = int(row["mentions"] or 0), int(row["mentions_24h_ago"] or 0)
    tag = level(m, b)
    trend = f"{m / b:.0f}x yesterday" if b and m >= 2 * b else f"yesterday: {b}"
    return tag, f"{m} Reddit mentions in 24 hours, {trend}"


def line(tag, note):
    return f"Hype [practice, info only]: {WORDS.get(tag, tag.upper())} ({note})"


def snapshot(tickers, date):
    """Save tonight's mention counts for our stocks (one row per stock per day) for the Study bot."""
    data = _data()
    rows = [{"date": date, "ticker": t, "mentions": int(r["mentions"] or 0),
             "mentions_24h_ago": int(r["mentions_24h_ago"] or 0),
             "level": level(r["mentions"], r["mentions_24h_ago"])}
            for t in tickers if (r := data.get(t.upper().replace("-", ".")))]
    _append(C.HYPE_HISTORY_FILE, pd.DataFrame(rows), date)
    return len(rows)


def _append(path, new, date):
    old = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
    if len(old):
        old = old[old["date"] != date]          # running twice in one evening keeps one copy
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pd.concat([old, new], ignore_index=True).to_csv(path, index=False)
