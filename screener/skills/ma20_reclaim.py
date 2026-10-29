"""Idea borrowed from Jake Schincariol's open-source trader-scanner (MIT): the
'reclaimed the 20-day average' rule. Day-trade version: yesterday closed below
the 20-day average, today is back above it and pushing to a new high of day."""


def find(ctx, p):
    d = ctx.daily
    if len(d) < 21 or ctx.rvol < p["min_rvol"] or ctx.last < ctx.vwap:
        return None
    sma20 = float(d["Close"].iloc[-20:].mean())
    if not (ctx.prev_close < sma20 < ctx.last):
        return None
    if (ctx.hod / ctx.last - 1) * 100 > p["max_from_hod_pct"]:
        return None
    entry = ctx.hod + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(sma20 - p["stop_atr"] * ctx.atr, entry - 0.8 * ctx.atr),
        "target_r": p["target_r"], "score": ctx.rvol * ctx.day_chg_pct,
        "reason": f"Climbed back above its 20-day average (${sma20:.2f}) and pushing new highs",
    }


SKILL = {
    "name": "MA20 Reclaim",
    "kid_explainer": "The 20-day average is like the stock's 'normal' line. It slipped under it yesterday, "
                     "and today it jumped back above. That often means buyers are back.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_rvol": 1.2, "max_from_hod_pct": 1.5, "stop_atr": 0.15, "target_r": 2.0},
    "tune": {"min_rvol": [1.0, 2.0], "stop_atr": [0.05, 0.3], "target_r": [1.5, 3.0]},
    "find": find,
}
