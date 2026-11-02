"""Boss's idea: a stock that has been falling for months suddenly wakes up -
big volume, a much wider range than normal, and a strong move UP. Buy as it
breaks its high of the day, hoping the sellers are finally done."""


def find(ctx, p):
    d = ctx.daily
    n = p["lookback_days"]
    if len(d) < max(n, 50) or ctx.rvol < p["min_rvol"] or ctx.day_chg_pct < p["min_day_chg_pct"]:
        return None
    c = d["Close"]
    drop = (float(c.iloc[-1]) / float(c.iloc[-n]) - 1) * 100
    if drop > -p["min_drop_pct"] or float(c.iloc[-1]) >= float(c.iloc[-50:].mean()):
        return None
    if (ctx.hod - ctx.lod) < p["min_range_atr"] * ctx.atr or ctx.last < ctx.vwap:
        return None
    if (ctx.hod / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    entry = ctx.hod + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.vwap - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": ctx.rvol * ctx.day_chg_pct,
        "reason": f"Down {abs(drop):.0f}% in {n} days, now up {ctx.day_chg_pct:.1f}% on {ctx.rvol:.1f}x volume - buy if it makes a new high",
    }


SKILL = {
    "name": "Downtrend Reversal",
    "kid_explainer": "This stock has been sliding down for months. Today it suddenly woke up and is "
                     "jumping on lots of buying. If it keeps climbing to a new high, we buy.",
    "weather": ["sunny", "cloudy"],
    "params": {"lookback_days": 60, "min_drop_pct": 15, "min_rvol": 2.0, "min_day_chg_pct": 3.0,
               "min_range_atr": 1.0, "max_dist_pct": 1.0, "stop_atr": 0.8, "target_r": 2.0},
    "tune": {"min_rvol": [1.5, 3.0], "stop_atr": [0.5, 1.2], "target_r": [1.5, 3.0]},
    "find": find,
}
