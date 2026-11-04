"""Boss's idea: join the hype. A stock that Reddit is suddenly talking about (Hype bot says
HYPE), trading on heavy volume and moving up today - don't be scared, buy as it makes a new
high of the day. There's no free Reddit history, so this can't be tested on the past: it
has to prove itself live in practice (backtests skip it)."""


def find(ctx, p):
    if getattr(ctx, "hype", None) != "hype":
        return None
    if ctx.rvol < p["min_rvol"] or ctx.day_chg_pct < p["min_day_chg_pct"] or ctx.last < ctx.vwap:
        return None
    if (ctx.hod / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    entry = ctx.hod + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.vwap - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": ctx.rvol * ctx.day_chg_pct,
        "reason": f"🔥 Reddit hype + up {ctx.day_chg_pct:.1f}% on {ctx.rvol:.1f}x volume - buy if it makes a new high",
    }


SKILL = {
    "name": "Hype Breakout",
    "kid_explainer": "Everyone on Reddit is suddenly talking about this stock, lots of people are buying, "
                     "and it's going up. We jump on the ride when it makes a new high.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_rvol": 1.5, "min_day_chg_pct": 2.0, "max_dist_pct": 1.5, "stop_atr": 0.6, "target_r": 2.0},
    "tune": {"min_rvol": [1.2, 2.0], "min_day_chg_pct": [1.0, 3.0], "target_r": [1.5, 3.0]},
    "find": find,
}
