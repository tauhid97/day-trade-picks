"""Boss's idea: keep an eye on red days and on stocks that have been down a long time.
The Study bot backs it: on the day AFTER a red market day (SPY down 1%+), stocks 25%+ below
their 6-month high rose 1%+ 42% of the time vs 30% normally (1,289 unseen examples).
So: the morning after a red day, a beaten-down stock that climbs back above its morning high
is a buy. Holds up to 2 days (4 of 5 won that way in the Nov 2026 replay - a tiny sample)."""


def find(ctx, p):
    red = getattr(ctx, "market_prev_chg", None)
    if red is None or red > -p["red_day_pct"]:
        return None
    d = ctx.daily
    if len(d) < 60 or ctx.rvol < p["min_rvol"]:
        return None
    if ctx.last >= ctx.or_high or (ctx.or_high / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    high = float(d["High"].iloc[-p["lookback_days"]:].max())
    below = (1 - float(d["Close"].iloc[-1]) / high) * 100
    if below < p["min_below_pct"]:
        return None
    entry = ctx.or_high + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.lod - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": below * ctx.rvol,
        "reason": f"Market fell {abs(red):.1f}% yesterday and this stock is {below:.0f}% below its 6-month high "
                  f"- buy only if it climbs above the morning high",
    }


SKILL = {
    "name": "Beaten-Down Turnaround",
    "kid_explainer": "Yesterday the whole market had a bad day, and this stock has been losing for months. "
                     "Those often bounce the next day. If it climbs above its morning high, we buy the comeback.",
    "weather": ["sunny", "cloudy", "stormy"],
    "params": {"red_day_pct": 1.0, "lookback_days": 126, "min_below_pct": 25.0, "min_rvol": 1.2,
               "max_dist_pct": 2.5, "stop_atr": 1.0, "target_r": 2.0, "hold_days": 2},
    "tune": {"min_below_pct": [20.0, 35.0], "red_day_pct": [0.7, 1.5], "target_r": [1.5, 3.0]},
    "find": find,
}
