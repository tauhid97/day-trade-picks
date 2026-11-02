"""Idea from Toby Crabel's 1990 book on short-term price patterns: the 'NR7' day.
When yesterday had the narrowest range of the last 7 days, a bigger move often
follows. Long-only day-trade version: in an uptrend, buy as price breaks yesterday's high."""


def find(ctx, p):
    d = ctx.daily
    n = p["lookback"]
    if len(d) < max(n, p["trend_days"]) or ctx.rvol < p["min_rvol"] or ctx.last < ctx.vwap:
        return None
    ranges = (d["High"] - d["Low"]).iloc[-n:]
    if ranges.iloc[-1] > ranges.min():
        return None
    if float(d["Close"].iloc[-1]) <= float(d["Close"].iloc[-p["trend_days"]:].mean()):
        return None
    y_high = float(d["High"].iloc[-1])
    level = max(y_high, ctx.hod)
    if (level / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    entry = level + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.lod - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": ctx.atr / max(float(ranges.iloc[-1]), 0.01),
        "reason": f"Yesterday was its quietest day in {n} days, in an uptrend - buy if it breaks out above ${level:.2f}",
    }


SKILL = {
    "name": "NR7 Breakout",
    "kid_explainer": "Yesterday the stock barely moved - like a spring pushed down tight. "
                     "Springs jump. If the price pops above yesterday's high, we buy.",
    "weather": ["sunny", "cloudy"],
    "params": {"lookback": 7, "trend_days": 50, "min_rvol": 1.0, "max_dist_pct": 1.5,
               "stop_atr": 0.5, "target_r": 2.0},
    "tune": {"min_rvol": [0.8, 1.5], "stop_atr": [0.3, 0.8], "target_r": [1.5, 3.0]},
    "find": find,
}
