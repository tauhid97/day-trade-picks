"""SCOUT BOT - looks at every stock and asks every skill: 'see anything?'"""
import pandas as pd

from . import config as C
from .bots import hype
from .bots import weather as weather_bot
from .setups import Context, make_pick, rank_and_cap


def market_change(day, scan_ts, intraday, daily):
    """SPY's % change today at scan time, or None if the data is missing."""
    t = C.MARKET_TICKER
    if t not in intraday or t not in daily:
        return None
    b = intraday[t]
    b = b[(b.index.normalize() == day) & (b.index < scan_ts)]
    d = daily[t][daily[t].index < day.tz_localize(None)]
    if b.empty or d.empty:
        return None
    return (float(b["Close"].iloc[-1]) / float(d["Close"].iloc[-1]) - 1) * 100


def market_prev_change(day, daily):
    """SPY's % change on the last full day before `day` (was yesterday a red day?), or None."""
    spy = daily.get(C.MARKET_TICKER)
    if spy is None:
        return None
    c = spy["Close"][spy.index < day.tz_localize(None)]
    return (float(c.iloc[-1]) / float(c.iloc[-2]) - 1) * 100 if len(c) >= 2 else None


def build_contexts(day, scan_ts, intraday, daily):
    cut = scan_ts.strftime("%H:%M")
    mkt = market_change(day, scan_ts, intraday, daily)
    mkt_prev = market_prev_change(day, daily)
    out = []
    for t, bars in intraday.items():
        if t == C.MARKET_TICKER or t not in daily:
            continue
        dates = bars.index.normalize()
        today = bars[(dates == day) & (bars.index < scan_ts)]
        if len(today) < 6:
            continue
        d = daily[t]
        d = d[d.index < day.tz_localize(None)]
        if len(d) < 30:
            continue
        prior_days = sorted(set(dates[dates < day]))[-C.RVOL_LOOKBACK_DAYS:]
        if len(prior_days) < 3:
            continue
        vols = [bars[dates == pd_][lambda x: x.index.strftime("%H:%M") < cut]["Volume"].sum() for pd_ in prior_days]
        try:
            ctx = Context(t, today, d, float(pd.Series(vols).mean()))
        except Exception:
            continue
        if ctx.last >= C.MIN_PRICE and ctx.avg_dollar_vol >= C.MIN_AVG_DOLLAR_VOL:
            ctx.market_chg_pct, ctx.market_prev_chg = mkt, mkt_prev
            out.append(ctx)
    return out


def ideas(contexts, skill, params=None, weather="cloudy"):
    """All picks one skill finds today (respecting the weather)."""
    if weather not in skill["weather"]:
        return []
    p = params or skill["params"]
    out = []
    for ctx in contexts:
        try:
            idea = skill["find"](ctx, p)
        except Exception as e:
            print(f"skill {skill['name']} failed on {ctx.ticker}: {e}")
            continue
        if idea and (pick := make_pick(ctx, skill["name"], idea)):
            pick["hold_days"] = int(p.get("hold_days", 1))      # 1 = day trade, 2 = may hold overnight
            out.append(pick)
    return out


def add_hype(contexts):
    """Live scans only: tell each stock its Reddit hype level (the past has no hype data)."""
    for ctx in contexts:
        try:
            ctx.hype = hype.check(ctx.ticker)[0]
        except Exception as e:
            print("Hype check skipped for", ctx.ticker, e)
            ctx.hype = "unknown"


def picks_for_day(day, scan_ts, intraday, daily, skills, status=None):
    """Returns (live_picks, practice_picks, weather, weather_note)."""
    status = status or {}
    w, note = weather_bot.check(day, scan_ts, intraday, daily)
    ctxs = build_contexts(day, scan_ts, intraday, daily)
    add_hype(ctxs)
    live, practice = [], []
    for sk in skills:
        found = ideas(ctxs, sk, weather=w)
        (live if status.get(sk["name"], "practice") == "live" else practice).extend(found)   # new skills start in practice
    return rank_and_cap(live), rank_and_cap(practice), w, note
