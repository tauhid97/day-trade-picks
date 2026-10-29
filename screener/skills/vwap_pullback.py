def find(ctx, p):
    if ctx.day_chg_pct < p["min_day_chg_pct"] or ctx.rvol < p["min_rvol"]:
        return None
    ext = (ctx.last / ctx.vwap - 1) * 100
    if ext <= 0 or ext > p["max_ext_pct"]:
        return None
    vw = ctx.vwap_series.dropna()
    if len(vw) < 12 or vw.iloc[-1] <= vw.iloc[-12]:
        return None
    return {
        "order_type": "buy_limit", "entry": ctx.vwap,
        "stop": ctx.vwap - p["stop_atr"] * ctx.atr,
        "target_r": p["target_r"], "score": ctx.rvol * ctx.day_chg_pct / max(ext, 0.25),
        "reason": f"Up {ctx.day_chg_pct:.1f}% on {ctx.rvol:.1f}x volume, rising VWAP - buy the dip to VWAP",
    }


SKILL = {
    "name": "VWAP Pullback",
    "kid_explainer": "A stock is having a good day. VWAP is the 'average price' line. "
                     "When the price dips back down to that line, we buy it on sale.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_day_chg_pct": 1.0, "min_rvol": 1.3, "max_ext_pct": 2.5, "stop_atr": 0.25, "target_r": 2.0},
    "tune": {"min_rvol": [1.0, 2.0], "stop_atr": [0.15, 0.4], "target_r": [1.5, 3.0]},
    "find": find,
}
