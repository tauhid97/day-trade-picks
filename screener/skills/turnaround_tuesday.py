"""An old, well-known market habit ("Turnaround Tuesday"): after the market falls on Friday AND
Monday, it often bounces on Tuesday. Our version uses QQQ (the Nasdaq-100 fund): if Friday and
Monday both closed down, buy at Monday's close and sell at Tuesday's close. Safety price 3% below.

Tested on QQQ daily prices 1999-2026 before adding: 2016+ (data it never "learned" on) gave
106 trades, 62% won, about +0.38% per trade, only one losing year (2022). Small but steady -
a past test, not a promise.

It can't run in the morning scan (it needs Monday's close), so weather is [] and main.py's
evening job calls evening() after the day's grading.
"""
import pandas as pd

TICKER = "QQQ"


def find(ctx, p):
    return None                    # never used by the morning scan - see evening()


def signal(daily, today):
    """True when `today` is the first trading day of the week and it AND the day before closed down."""
    c = daily["Close"].dropna()
    day = pd.Timestamp(today)
    day = (day.tz_localize(None) if day.tzinfo else day).normalize()   # the evening job passes New York time
    if len(c) < 3 or c.index[-1].normalize() != day:
        return False
    first_of_week = c.index[-1].weekday() < c.index[-2].weekday()   # handles Monday holidays (Tuesday counts)
    return bool(first_of_week and c.iloc[-1] < c.iloc[-2] < c.iloc[-3])


def make_pick(close, now, mode):
    p = SKILL["params"]
    entry = round(float(close), 2)
    stop = round(entry * (1 - p["stop_pct"] / 100), 2)
    return {"date": now.strftime("%Y-%m-%d"), "published_at": now.isoformat(), "mode": mode,
            "ticker": TICKER, "setup": SKILL["name"], "order_type": "at_close", "entry": entry,
            "stop": stop, "target": None, "risk_pct": p["stop_pct"],
            "reason": "QQQ fell on Friday AND today - the market often bounces the next day "
                      "(won 62% in a 10-year past test, small wins)",
            "hold_days": p["hold_days"]}


def evening(now, daily=None, send=None):
    """Evening job: on signal days, save one pick (graded tomorrow night) and tell Boss. Returns the message."""
    from .. import live, plain
    from ..bots import guard
    from ..data import get_daily
    from ..notify import to_boss
    send = send or to_boss
    if daily is None:
        daily = get_daily([TICKER], period="1mo").get(TICKER)
    if daily is None or not signal(daily, now):
        return ""
    df = live.load_picks()
    day = now.strftime("%Y-%m-%d")
    if len(df) and ((df["date"] == day) & (df["setup"] == SKILL["name"])).any():
        return ""                  # already saved tonight
    mode = guard.modes().get(SKILL["name"], "practice")
    pick = make_pick(daily["Close"].iloc[-1], now, mode)
    live.save_picks(pd.concat([df, pd.DataFrame([pick])], ignore_index=True) if len(df) else pd.DataFrame([pick]))
    msg = "\n".join([f"🔁 {plain.nick(SKILL['name'])} [{mode.upper()}]", ""] + plain.pick_lines(1, pick)
                    + ["Practice tracking uses today's close. Result comes tomorrow evening."])
    send(msg)
    return msg


SKILL = {
    "name": "Turnaround Tuesday",
    "kid_explainer": "When the whole market (QQQ) falls on Friday AND again on Monday, it often bounces back on Tuesday. "
                     "We buy QQQ at Monday's close and sell at Tuesday's close. Safety price: 3% lower. "
                     "It only happens about 10 times a year.",
    "weather": [],                 # not part of the morning scan
    "plays_on": "Monday evenings, after Friday and Monday were both red",
    "params": {"stop_pct": 3.0, "hold_days": 1},
    "tune": {},
    "find": find,
}
