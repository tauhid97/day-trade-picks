"""Adapted from public research: Zarattini, Barbon & Aziz, "A Profitable Day Trading
Strategy for the U.S. Equity Market" (2024) - Opening Range Breakout on "Stocks in Play".

Paper (5-min version): trade only the stocks with the highest opening volume vs. normal,
go in the direction of the first candle, stop = 10% of ATR, exit at the close.
Our free data/scheduler can't post at 9:35, so this version uses the 9:30-10:00 range.
"""


def find(ctx, p):
    if ctx.atr < p["min_atr"] or ctx.rvol < p["min_rvol"]:
        return None
    if ctx.or_close <= ctx.or_open or ctx.last >= ctx.or_high:   # need a green opening range, not yet broken
        return None
    entry = ctx.or_high + 0.01
    return {
        "order_type": "buy_stop", "entry": entry, "stop": entry - p["stop_atr"] * ctx.atr,
        "target_r": p["target_r"], "score": ctx.rvol,
        "reason": f"Stock in play: {ctx.rvol:.1f}x normal volume, green opening range - buy the breakout",
    }


SKILL = {
    "name": "ORB Stocks in Play",
    "kid_explainer": "Copied from a research paper. We find the stocks everyone is crowding into today. "
                     "If the price breaks above its first-30-minute high, we buy and usually hold until the end of the day.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_rvol": 2.0, "min_atr": 0.5, "stop_atr": 0.15, "target_r": None},
    "tune": {"min_rvol": [1.5, 3.0], "stop_atr": [0.1, 0.25], "target_r": [None, 3.0]},
    "find": find,
}
