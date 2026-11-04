"""WATCHLIST BOT - Boss's idea: always keep an eye on beaten-down stocks and red days.

PRACTICE ONLY: a short list in the morning message (and /watchlist on Telegram).
It never makes a pick by itself - the Underdog skill decides when one is worth buying.

beaten-down = the stocks furthest below their 6-month high (20%+ down)
red day     = the whole market (SPY) is down 1%+ this morning; then we also list
              the stocks holding up best - strong stocks on red days are worth watching
"""
import json
import os

import pandas as pd

from .. import config as C

LOOKBACK_DAYS = 126      # ~6 months of trading days
MIN_BELOW_PCT = 20.0
RED_DAY_PCT = -1.0
SHOW = 5


def build(daily, today, today_chg, market_chg=None):
    """daily: {ticker: daily bars}; today_chg: {ticker: % change today}. Saves and returns the watchlist."""
    day = pd.Timestamp(today).tz_localize(None).normalize() if pd.Timestamp(today).tzinfo else pd.Timestamp(today).normalize()
    beaten = []
    for t, d in daily.items():
        if t == C.MARKET_TICKER:
            continue
        d = d[d.index < day]
        if len(d) < 60:
            continue
        high = float(d["High"].iloc[-LOOKBACK_DAYS:].max())
        last = float(d["Close"].iloc[-1])
        below = (1 - last / high) * 100
        if below >= MIN_BELOW_PCT:
            back = d["Close"].iloc[-63] if len(d) >= 63 else d["Close"].iloc[0]
            beaten.append({"ticker": t, "below_high_pct": int(round(below)),
                           "chg_3m": round((last / float(back) - 1) * 100, 1), "today": today_chg.get(t)})
    beaten.sort(key=lambda x: -x["below_high_pct"])
    red = market_chg is not None and market_chg <= RED_DAY_PCT
    holding = sorted(({"ticker": t, "chg": round(c, 1)} for t, c in today_chg.items() if c is not None),
                     key=lambda x: -x["chg"])[:SHOW] if red else []
    w = {"date": day.strftime("%Y-%m-%d"), "market_chg": None if market_chg is None else round(market_chg, 2),
         "red_day": bool(red), "beaten": beaten[:SHOW], "holding_up": holding}
    os.makedirs(os.path.dirname(C.WATCHLIST_FILE) or ".", exist_ok=True)
    json.dump(w, open(C.WATCHLIST_FILE, "w"), indent=1)
    return w


def lines(w):
    out = ["👀 Beaten-down watchlist [practice, info only] - furthest below their 6-month high:"]
    for x in w["beaten"]:
        now = f", today {x['today']:+.1f}%" if x.get("today") is not None else ""
        out.append(f"- ${x['ticker']}: {x['below_high_pct']}% below its high (3 months: {x['chg_3m']:+.1f}%{now})")
    if not w["beaten"]:
        out.append("- none of our stocks are 20%+ below their 6-month high right now")
    if w["red_day"]:
        out += ["", f"🟥 Red day (market {w['market_chg']:+.1f}%) - holding up best:"]
        out += [f"- ${x['ticker']}: {x['chg']:+.1f}% today" for x in w["holding_up"]]
    return out


def text():
    """For the /watchlist Telegram command."""
    if not os.path.exists(C.WATCHLIST_FILE):
        return "No watchlist yet, Boss - it's made with the morning scan (about 10:40 AM ET on weekdays)."
    w = json.load(open(C.WATCHLIST_FILE))
    return f"Watchlist from {w['date']}:\n" + "\n".join(lines(w))
