"""NEWS BOT - a heads-up on each pick: earnings day, in the news, or quiet.

PRACTICE ONLY: the label is shown in Boss's message and saved with every pick,
but it never blocks a trade. After a few months we check if picks with news
win or lose more often, and only then decide whether to use it as a filter.

earnings = the company reports earnings yesterday, today or tomorrow (big jumps either way)
news     = headlines about the stock in the last 24 hours
quiet    = nothing found

Each "news" label also gets a MOOD from simple word lists: GOOD (beats, upgrade, raises
guidance...), BAD (misses, downgrade, lawsuit...), MIXED, or NEUTRAL. It's rough - a word
list, not a human reader - so the Study bot checks whether the mood actually matters.
Every evening a mood snapshot of all our stocks is saved for the Study bot.

Data (free, no key): Yahoo Finance headline feed + yfinance's earnings calendar.
Headlines are loose: a story is counted when its title names the ticker or company.
Keyword tags borrowed from Jakeschincariol/day-trader-skill (MIT).
"""
import datetime as dt
import email.utils
import os
import re
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from .. import config as C

FEED = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={}&region=US&lang=en-US"
WINDOW_HOURS = 24
KEYWORDS = [
    ("earnings", r"\bearnings\b|\bresults\b|\bEPS\b|\bguidance\b"),
    ("analyst", r"\bupgrades?\b|\bdowngrades?\b|price target"),
    ("legal", r"\blawsuit\b|\bsued\b|\bprobe\b|\binvestigation\b|\bantitrust\b"),
    ("deal", r"\bacqui(?:re|res|red|sition)\b|\bmerger\b|\bbuyout\b|\btakeover\b|\bdeal\b|\bcontract\b"),
    ("people", r"\bCEO\b|\bCFO\b|\bresign|\bsteps down\b"),
    ("risk", r"\brecall\b|\bbankrupt|\bdelist|\bhack|\bbreach\b|\boutage\b|\boffering\b"),
    ("regulatory", r"\bFDA\b|\bapproval\b|\bFTC\b|\bDOJ\b"),
]
GOOD = (r"\bbeats?\b|\btops\b|\bbetter than expected\b|\braises? (?:guidance|forecast|outlook)\b|\bupgrade[sd]?\b"
        r"|\brecord (?:revenue|sales|profit|quarter)\b|\bsurges?\b|\bsoars?\b|\bjumps?\b|\brall(?:y|ies)\b"
        r"|\bwins?\b|\bapproval\b|\bapproved\b|\bbuyback\b|\bpartnership\b|\boutperform\b|\brises?\b")
BAD = (r"\bmiss(?:es|ed)?\b|\bworse than expected\b|\bcuts? (?:guidance|forecast|outlook|jobs)\b|\bdowngrade[sd]?\b"
       r"|\bplunges?\b|\bsinks?\b|\btumbles?\b|\bslumps?\b|\bfalls?\b|\bdrops?\b|\blawsuit\b|\bsued\b"
       r"|\bprobe\b|\binvestigation\b|\brecall\b|\blayoffs?\b|\bwarns?\b|\bbankrupt|\boffering\b|\bdelay(?:s|ed)?\b")
GENERIC = {"advanced", "american", "first", "general", "united", "global", "international", "the", "national"}
WORDS = {"earnings": "⚠️ EARNINGS", "news": "IN THE NEWS", "quiet": "QUIET", "unknown": "UNKNOWN"}
SUMMARY_NAMES = [("earnings", "Earnings day"), ("news", "In the news"), ("quiet", "Quiet")]


def headlines(ticker):
    """[(UTC time, title)] from Yahoo's free headline feed."""
    r = requests.get(FEED.format(ticker.replace(".", "-")), headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        when = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
        out.append((pd.Timestamp(when).tz_convert("UTC"), (it.findtext("title") or "").strip()))
    return out


def earnings_date(ticker):
    import yfinance as yf
    dates = (yf.Ticker(ticker).calendar or {}).get("Earnings Date") or []
    return dates[0] if dates else None


def company_name(ticker):
    import yfinance as yf
    return yf.Ticker(ticker).info.get("shortName")


def mentions(title, ticker, name):
    if re.search(rf"\b{re.escape(ticker)}\b", title):
        return True
    first = (name or "").split(" ")[0].strip(",.")
    return len(first) >= 4 and first.lower() not in GENERIC and re.search(rf"\b{re.escape(first)}\b", title, re.I) is not None


def mood(titles):
    """good / bad / mixed / neutral, counting headlines that are clearly one or the other."""
    good = bad = 0
    for t in titles:
        g, b = re.search(GOOD, t, re.I) is not None, re.search(BAD, t, re.I) is not None
        good += g and not b
        bad += b and not g
    if not good and not bad:
        return "neutral"
    return "good" if good > bad else "bad" if bad > good else "mixed"


def classify(earn, heads, now):
    """(tag, note) from the earnings date and the stock's headlines, as of `now`."""
    today = now.date()
    if earn is not None and abs((earn - today).days) <= 1:
        when = {-1: "yesterday", 0: "today", 1: "tomorrow"}[(earn - today).days]
        return "earnings", f"earnings report {when} - expect big moves either way"
    start = now - pd.Timedelta(hours=WINDOW_HOURS)
    recent = [t for when, t in heads if start <= when <= now]
    if not recent:
        return "quiet", f"no headlines in the last {WINDOW_HOURS} hours"
    tags = [label for label, rx in KEYWORDS if any(re.search(rx, t, re.I) for t in recent)]
    note = f"{len(recent)} headline{'s' if len(recent) != 1 else ''} in the last {WINDOW_HOURS} hours"
    note += f", mood: {mood(recent).upper()}"
    return "news", note + (f", about: {', '.join(tags)}" if tags else "")


def check(ticker, now):
    try:
        name = company_name(ticker)
        heads = [h for h in headlines(ticker) if mentions(h[1], ticker, name)]
        return classify(earnings_date(ticker), heads, now)
    except Exception as e:
        print("News bot skipped for", ticker, e)
        return "unknown", "news check unavailable"


def snapshot(tickers, now):
    """Save tonight's headline count and mood for each of our stocks, for the Study bot."""
    start, rows = now - pd.Timedelta(hours=WINDOW_HOURS), []
    for t in tickers:
        try:
            recent = [title for when, title in headlines(t) if start <= when <= now and mentions(title, t, None)]
        except Exception as e:
            print("News snapshot skipped for", t, e)
            continue
        rows.append({"date": now.strftime("%Y-%m-%d"), "ticker": t, "headlines": len(recent),
                     "mood": mood(recent) if recent else "none"})
    path = C.NEWS_HISTORY_FILE
    old = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
    if len(old):
        old = old[old["date"] != now.strftime("%Y-%m-%d")]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pd.concat([old, pd.DataFrame(rows)], ignore_index=True).to_csv(path, index=False)
    return len(rows)


def line(tag, note):
    return f"News [practice, info only]: {WORDS.get(tag, tag.upper())} ({note})"


def summary(picks):
    """Weekly lines: how picks did, grouped by their news label."""
    from .. import plain
    if "news" not in picks:
        return []
    rows = picks[picks["status"].isin(["target", "stop", "eod", "no_fill"]) & picks["news"].notna()]
    out = []
    for tag, name in SUMMARY_NAMES:
        g = rows[rows["news"] == tag]
        if len(g):
            out.append(f"- {name}: {plain.scorecard(g.to_dict('records'))}")
    return out or ["- No graded picks with a news label yet."]
