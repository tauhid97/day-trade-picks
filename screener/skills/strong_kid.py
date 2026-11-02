"""Common day-trader idea: relative strength vs. the market. Most stocks follow SPY, so a
stock that is clearly up while SPY is flat or down may have big buyers behind it.
Long-only version: buy as it breaks its high of the day."""


def find(ctx, p):
    mkt = getattr(ctx, "market_chg_pct", None)
    if mkt is None or mkt > p["max_market_chg_pct"] or ctx.rvol < p["min_rvol"] or ctx.last < ctx.vwap:
        return None
    rs = ctx.day_chg_pct - mkt
    if rs < p["min_rs_pct"] or (ctx.hod / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    entry = ctx.hod + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.vwap - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": rs * ctx.rvol,
        "reason": f"Up {ctx.day_chg_pct:.1f}% while the market is {mkt:+.1f}%, on {ctx.rvol:.1f}x volume - buy if it makes a new high",
    }


SKILL = {
    "name": "Relative Strength",
    "kid_explainer": "Most stocks go up and down with the whole market. This one is going UP "
                     "while the market is not - like the one kid still running when everyone else is tired.",
    "weather": ["sunny", "cloudy", "stormy"],
    "params": {"max_market_chg_pct": 0.25, "min_rs_pct": 2.0, "min_rvol": 1.5, "max_dist_pct": 1.0,
               "stop_atr": 0.6, "target_r": 2.0},
    "tune": {"min_rs_pct": [1.5, 3.0], "min_rvol": [1.2, 2.0], "target_r": [1.5, 3.0]},
    "find": find,
}
