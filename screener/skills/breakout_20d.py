"""Idea borrowed from Jake Schincariol's open-source trader-scanner (MIT): the
'20-day breakout' rule. Day-trade version: buy as price breaks the 20-day high."""


def find(ctx, p):
    d = ctx.daily
    if len(d) < 20 or ctx.rvol < p["min_rvol"] or ctx.day_chg_pct <= 0 or ctx.last < ctx.vwap:
        return None
    high20 = float(d["High"].iloc[-20:].max())
    level = max(high20, ctx.hod)
    if (level / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    entry = level + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.lod - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": ctx.rvol * ctx.day_chg_pct,
        "reason": f"Knocking on its 20-day high (${high20:.2f}) on {ctx.rvol:.1f}x volume",
    }


SKILL = {
    "name": "20-Day Breakout",
    "kid_explainer": "The stock is about to jump over the highest price it reached in a whole month. "
                     "Breaking that ceiling often brings new buyers.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_rvol": 1.3, "max_dist_pct": 1.5, "stop_atr": 0.5, "target_r": 2.0},
    "tune": {"min_rvol": [1.0, 2.0], "stop_atr": [0.3, 0.8], "target_r": [1.5, 3.0]},
    "find": find,
}
