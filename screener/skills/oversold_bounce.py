def find(ctx, p):
    if ctx.avg_dollar_vol < p["min_avg_dollar_vol"]:
        return None
    if ctx.rsi > p["max_rsi"] or ctx.day_chg_pct > -p["min_drop_pct"] or ctx.last >= ctx.or_high:
        return None
    return {
        "order_type": "buy_stop", "entry": ctx.or_high + 0.01, "stop": ctx.lod - 0.01,
        "target_r": p["target_r"], "score": (p["max_rsi"] - ctx.rsi + 1) * ctx.rvol,
        "reason": f"RSI {ctx.rsi:.0f} (oversold), down {abs(ctx.day_chg_pct):.1f}% - only buy if it bounces back above the morning high",
    }


SKILL = {
    "name": "Oversold Bounce",
    "kid_explainer": "A big, famous stock fell too far, too fast - like a ball dropped hard. "
                     "We wait until it starts bouncing back up, then buy.",
    "weather": ["sunny", "cloudy", "stormy"],
    "params": {"max_rsi": 30, "min_drop_pct": 2.0, "min_avg_dollar_vol": 50_000_000, "target_r": 1.5},
    "tune": {"max_rsi": [25, 35], "min_drop_pct": [1.5, 3.0], "target_r": [1.0, 2.0]},
    "find": find,
}
