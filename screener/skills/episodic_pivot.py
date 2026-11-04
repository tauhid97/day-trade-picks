"""Adapted from Kristjan Kullamägi's (Qullamaggie) "episodic pivot", as he explains it in public:
a stock gaps up 10%+ on big news with huge volume; buy when it breaks the opening range / new
high of the day, Safety price = the low of the day (no wider than about 1 ATR), and don't sell
at a fixed Win price - hold for days and let it run. Our version holds up to 5 trading days.
Backtests have no news data, so the gap + volume stand in for "big news"."""


def find(ctx, p):
    if ctx.gap_pct < p["min_gap_pct"] or ctx.rvol < p["min_rvol"]:
        return None
    if ctx.last < ctx.vwap or (ctx.hod / ctx.last - 1) * 100 > p["max_from_hod_pct"]:
        return None
    entry = ctx.hod + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.lod - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": ctx.rvol * ctx.gap_pct,
        "reason": f"Jumped +{ctx.gap_pct:.1f}% at the open on {ctx.rvol:.1f}x normal volume (big news?) "
                  f"- buy a new high, hold up to {p['hold_days']} days",
    }


SKILL = {
    "name": "Episodic Pivot",
    "kid_explainer": "Copied from a famous trader's public rules. A stock jumps 10% or more in the morning because of big news, "
                     "and a huge crowd is buying. If it climbs to a new high, we buy and hold for up to 5 days to let it run. "
                     "Safety price: the low of the day.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_gap_pct": 10.0, "min_rvol": 3.0, "max_from_hod_pct": 3.0, "stop_atr": 1.0,
               "target_r": None, "hold_days": 5},
    "tune": {"min_gap_pct": [7.0, 15.0], "min_rvol": [2.0, 5.0], "hold_days": [1, 3]},
    "find": find,
}
