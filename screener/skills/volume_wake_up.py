"""Boss's idea: watch the beaten-down list, and buy as soon as volume wakes up.

A stock on the top-5 beaten-down watchlist (furthest below its 6-month high, 20%+ down)
whose volume this morning is 1.5x its normal amount by this time = buyers are showing up.
Nov 2026 replay (178 stocks, 2 years hourly, 6% safety, hold 3 days): 411 trades, 47% won,
avg +1.17% a trade (older half +0.88%, newer half +1.69%); worst -25% (an overnight gap).
Checking volume first and THEN picking beaten stocks made nothing - the list must come first.
The bot's own 2-year test (hourly prices split into guessed 5-min steps, top 3 a day) was weaker:
443 trades, 42% won, avg +0.30% a trade (older +0.19%, newer +0.56%; 2024 lost a little). Practice first.
"""


def find(ctx, p):
    rank = getattr(ctx, "beaten_rank", None)
    if rank is None or rank > p["top_n"] or ctx.rvol < p["min_rvol"]:
        return None
    entry = ctx.last + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": entry * (1 - p["stop_pct"] / 100),
        "target_r": None,                                  # no target: sell at the close on the last day
        "score": ctx.below_high_pct,                       # most beaten-down first
        "reason": f"#{rank} on the beaten-down list ({ctx.below_high_pct:.0f}% below its 6-month high) "
                  f"and volume woke up ({ctx.rvol:.1f}x normal) - hold up to 3 days",
    }


SKILL = {
    "name": "Beaten-Down Volume",
    "kid_explainer": "These stocks fell a lot and everyone forgot them. When lots of people suddenly start "
                     "trading one again, it often climbs for a few days. We buy right away and hold up to 3 days.",
    "weather": ["sunny", "cloudy", "stormy"],
    "params": {"top_n": 5, "min_rvol": 1.5, "stop_pct": 5.9, "hold_days": 3},
    "tune": {"min_rvol": [1.2, 2.0]},
    "find": find,
}
