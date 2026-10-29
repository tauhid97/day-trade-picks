"""SCOUT BOT - looks at every stock and asks every skill: 'see anything?'"""
import pandas as pd

from . import config as C
from .bots import weather as weather_bot
from .setups import Context, make_pick, rank_and_cap


def build_contexts(day, scan_ts, intraday, daily):
    cut = scan_ts.strftime("%H:%M")
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
            out.append(pick)
    return out


def picks_for_day(day, scan_ts, intraday, daily, skills, status=None):
    """Returns (live_picks, practice_picks, weather, weather_note)."""
    status = status or {}
    w, note = weather_bot.check(day, scan_ts, intraday, daily)
    ctxs = build_contexts(day, scan_ts, intraday, daily)
    live, practice = [], []
    for sk in skills:
        found = ideas(ctxs, sk, weather=w)
        (live if status.get(sk["name"], "live") == "live" else practice).extend(found)
    return rank_and_cap(live), rank_and_cap(practice), w, note
