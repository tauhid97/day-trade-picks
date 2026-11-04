"""Adapted from public research: Zarattini, Barbon & Aziz, "A Profitable Day Trading
Strategy for the U.S. Equity Market" (2024) - Opening Range Breakout on "Stocks in Play".

Paper (5-min version): trade only the stocks with the highest opening volume vs. normal,
go in the direction of the first candle, stop = 10% of ATR, exit at the close.
Our free data/scheduler can't post at 9:35, so this version uses the 9:30-10:00 range.

Stop changed 2026-11-03 from 15% of ATR to the middle of the opening range: the tight stop
lost -15.9R in the backtest (28% wins); the midpoint stop was about break-even (54% wins).
Idea from two YouTube backtests of the opening-range breakout (Trading Steady, Ironclad Trading).
"""


def find(ctx, p):
    if ctx.atr < p["min_atr"] or ctx.rvol < p["min_rvol"]:
        return None
    if ctx.or_close <= ctx.or_open or ctx.last >= ctx.or_high:   # need a green opening range, not yet broken
        return None
    entry = ctx.or_high + 0.01
    return {
        "order_type": "buy_stop", "entry": entry, "stop": (ctx.or_high + ctx.or_low) / 2,
        "target_r": p["target_r"], "score": ctx.rvol,
        "reason": f"Stock in play: {ctx.rvol:.1f}x normal volume, green opening range - buy the breakout",
    }


SKILL = {
    "name": "ORB Stocks in Play",
    "kid_explainer": "Copied from a research paper. We find the stocks everyone is crowding into today. "
                     "If the price breaks above its first-30-minute high, we buy and usually hold until the end of the day. "
                     "Safety price: the middle of that first 30 minutes.",
    "weather": ["sunny", "cloudy"],
    "params": {"min_rvol": 2.0, "min_atr": 0.5, "target_r": None},
    "tune": {"min_rvol": [1.5, 3.0], "target_r": [None, 1.5]},
    "find": find,
}
