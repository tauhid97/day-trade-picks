"""TEMPLATE - copy this file to make a new skill (e.g. my_skill.py).

A skill looks at ONE stock (ctx) and either returns None ("nothing here")
or an idea with entry / stop / target. Useful things on ctx:
  ctx.last, ctx.open, ctx.prev_close, ctx.hod, ctx.lod, ctx.vwap, ctx.atr,
  ctx.gap_pct, ctx.day_chg_pct, ctx.rvol, ctx.rsi, ctx.or_high, ctx.or_low,
  ctx.bars (today's 5-min bars so far), ctx.daily (past daily bars)
"""


def find(ctx, p):
    if ctx.rvol < p["min_rvol"]:
        return None
    return {
        "order_type": "buy_stop",          # or "buy_limit"
        "entry": ctx.hod + 0.01,
        "stop": ctx.lod - 0.01,
        "target_r": p["target_r"],         # or None to hold until the close
        "score": ctx.rvol,                 # higher = better pick
        "reason": "Explain in one short sentence why",
    }


SKILL = {
    "name": "My New Skill",
    "kid_explainer": "What this skill does, explained to a 5-year-old.",
    "weather": ["sunny", "cloudy"],        # market moods this skill is allowed to trade in
    "params": {"min_rvol": 2.0, "target_r": 2.0},
    "tune": {"min_rvol": [1.5, 3.0], "target_r": [1.5, 3.0]},   # values the Coach may try
    "find": find,
}
