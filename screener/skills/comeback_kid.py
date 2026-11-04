"""Boss's idea + a Study bot lesson: stocks that just got knocked down often bounce.
The Study bot found that after a big down day into oversold, the next day rose 1%+ more
often than normal (39% vs 30% on unseen days). Day-trade version: wait for proof - only
buy once today's price climbs back above the morning high."""
from ..indicators import rsi


def find(ctx, p):
    d = ctx.daily
    if len(d) < 20 or ctx.rvol < p["min_rvol"] or ctx.last >= ctx.or_high:
        return None
    y_chg = (float(d["Close"].iloc[-1]) / float(d["Close"].iloc[-2]) - 1) * 100
    y_rsi = rsi(d["Close"])
    if y_chg > -p["min_drop_pct"] or y_rsi > p["max_rsi"]:
        return None
    if (ctx.or_high / ctx.last - 1) * 100 > p["max_dist_pct"]:
        return None
    entry = ctx.or_high + 0.01
    return {
        "order_type": "buy_stop", "entry": entry,
        "stop": max(ctx.lod - 0.01, entry - p["stop_atr"] * ctx.atr),
        "target_r": p["target_r"], "score": (p["max_rsi"] - y_rsi + 1) * abs(y_chg),
        "reason": f"Fell {abs(y_chg):.1f}% yesterday into oversold (RSI {y_rsi:.0f}) - buy only if it climbs back above the morning high",
    }


SKILL = {
    "name": "Oversold Comeback",
    "kid_explainer": "Yesterday this stock got knocked down hard. Stocks like that often bounce back. "
                     "We don't guess - we only buy once it starts climbing again today.",
    "weather": ["sunny", "cloudy", "stormy"],
    "params": {"min_drop_pct": 3.0, "max_rsi": 30, "min_rvol": 1.0, "max_dist_pct": 2.0,
               "stop_atr": 1.0, "target_r": 2.0},
    "tune": {"min_drop_pct": [2.0, 4.0], "max_rsi": [25, 35], "target_r": [1.5, 3.0]},
    "find": find,
}
