"""BREADTH BOT - how many S&P 500 stocks are in an uptrend (above their 200-day average).

PRACTICE ONLY: the reading is shown in Boss's message and saved with every pick,
but it never blocks a trade. After a few months we check if picks do better
on healthy days, and only then decide whether to use it as a filter.

Uses yesterday's close (the free data updates once a day), so there is no peeking ahead.
Data: free public CSV from tradermonty.github.io (same source as the market-breadth-analyzer skill).

strong   = 70%+ of stocks in uptrends (8-day average)
healthy  = 60-70%
neutral  = 50-60%
weak     = 40-50%
very weak = under 40%
"""
import io

import pandas as pd
import requests

from .. import config as C

_cache = {}


def load():
    if "df" not in _cache:
        r = requests.get(C.BREADTH_URL, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"]).set_index("Date").sort_index()
        _cache["df"] = df
    return _cache["df"]


def zone(level):
    for cut, name in [(0.70, "strong"), (0.60, "healthy"), (0.50, "neutral"), (0.40, "weak")]:
        if level >= cut:
            return name
    return "very weak"


def check(day):
    """Returns (zone, note) using the last reading before `day`."""
    try:
        df = load()
        df = df[df.index < pd.Timestamp(day).tz_localize(None).normalize()]
        if df.empty:
            return "unknown", "Breadth data unavailable"
        row = df.iloc[-1]
        level = float(row["Breadth_Index_8MA"])
        trend = "rising" if int(row["Breadth_200MA_Trend"]) == 1 else "falling"
        return zone(level), f"{level:.0%} of S&P 500 stocks in uptrends, long-term trend {trend}"
    except Exception as e:
        print("Breadth bot skipped:", e)
        return "unknown", "Breadth data unavailable"
