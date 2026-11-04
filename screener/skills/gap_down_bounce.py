"""Boss's idea: watch the stocks that crash overnight. A liquid stock that opens 4%+ below
yesterday's close on heavy volume often bounces once the panic sellers are done.
Don't guess the bottom - only buy once it climbs back above its morning (first 30 min) high."""


def find(ctx, p):
    if ctx.gap_pct > -p["min_gap_pct"] or ctx.rvol < p["min_rvol"] or ctx.last >= ctx.or_high:
        return None
    if (ctx.or_high / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    entry = ctx.or_high + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.lod - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": abs(ctx.gap_pct) * ctx.rvol,
        "reason": f"Crashed {abs(ctx.gap_pct):.1f}% overnight on {ctx.rvol:.1f}x volume - buy only if it climbs back above the morning high",
    }


SKILL = {
    "name": "Gap-Down Bounce",
    "kid_explainer": "This stock fell off a cliff overnight and opened way lower. Lots of people panic-sold. "
                     "When the price starts climbing back above its morning high, we buy the bounce.",
    "weather": ["sunny", "cloudy", "stormy"],
    "params": {"min_gap_pct": 4.0, "min_rvol": 1.5, "max_dist_pct": 2.5, "stop_atr": 1.0, "target_r": 2.0},
    "tune": {"min_gap_pct": [3.0, 6.0], "min_rvol": [1.2, 2.0], "target_r": [1.5, 3.0]},
    "find": find,
}
