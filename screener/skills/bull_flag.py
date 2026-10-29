"""Idea borrowed from Jake Schincariol's open-source trader-scanner (MIT): the daily
'bull flag' rule (a 10%+ run-up, then 5 quiet days in a tight range). Rewritten
here as a day trade: buy when today breaks above the top of the flag."""


def find(ctx, p):
    d = ctx.daily
    if len(d) < 16 or ctx.rvol < p["min_rvol"] or ctx.last < ctx.vwap:
        return None
    c = d["Close"]
    pole = c.iloc[-6] / c.iloc[-16] - 1
    flag = c.iloc[-5:]
    if pole * 100 < p["min_pole_pct"] or (flag.max() / flag.min() - 1) * 100 > p["max_flag_pct"]:
        return None
    level = max(float(d["High"].iloc[-5:].max()), ctx.hod)
    if (level / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    entry = level + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.lod - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": ctx.rvol * pole * 10,
        "reason": f"Bull flag: ran up {pole*100:.0f}%, rested 5 days, now pushing the top of the flag on {ctx.rvol:.1f}x volume",
    }


SKILL = {
    "name": "Bull Flag",
    "kid_explainer": "The stock ran up fast like a rocket (the flagpole), then rested for a few days (the flag). "
                     "When it breaks above the top of the flag, the rocket often takes off again.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_pole_pct": 10.0, "max_flag_pct": 5.0, "max_dist_pct": 2.0, "min_rvol": 1.2,
               "stop_atr": 0.5, "target_r": 2.0},
    "tune": {"min_pole_pct": [7.0, 15.0], "max_flag_pct": [4.0, 7.0], "stop_atr": [0.3, 0.8], "target_r": [1.5, 3.0]},
    "find": find,
}
