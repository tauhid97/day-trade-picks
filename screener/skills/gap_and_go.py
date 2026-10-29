def find(ctx, p):
    if ctx.gap_pct < p["min_gap_pct"] or ctx.rvol < p["min_rvol"]:
        return None
    if ctx.last < ctx.vwap or (ctx.hod / ctx.last - 1) * 100 > p["max_from_hod_pct"]:
        return None
    entry = ctx.hod + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.or_low, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": ctx.rvol * ctx.gap_pct,
        "reason": f"Gapped +{ctx.gap_pct:.1f}%, {ctx.rvol:.1f}x normal volume, holding above VWAP",
    }


SKILL = {
    "name": "Gap & Go",
    "kid_explainer": "A stock jumped up this morning and lots of people are buying. "
                     "If it climbs above today's highest point, we hop on for the ride.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_gap_pct": 3.0, "min_rvol": 2.0, "max_from_hod_pct": 3.0, "stop_atr": 0.5, "target_r": 2.0},
    "tune": {"min_gap_pct": [2.0, 5.0], "min_rvol": [1.5, 3.0], "stop_atr": [0.3, 0.8], "target_r": [1.5, 3.0]},
    "find": find,
}
