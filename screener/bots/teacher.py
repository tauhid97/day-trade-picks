"""TEACHER BOT - the Coach's teaching side. It explains, it never trades or changes settings.

 1. Ranks the skills doing best, using real picks (live + practice) AND the past-days test.
 2. Explains each skill in plain words: what it looks for, when it plays, when it usually fails.
 3. Gives one tip every evening: lessons from the bot's own trades, or a basic safety rule.
Type /teach on Telegram for a full lesson. Info only - not advice, no profit promises.
"""
import os

import pandas as pd

from .. import config as C
from .. import plain
from ..skills import load_skills

MIN_TRADES = 8          # a skill needs this many finished trades before it's ranked
MIN_EDGE_R = 0.05       # and must average at least this much per trade to be called "best"
FILLED = ["target", "stop", "eod"]

WATCH_OUT = {
    "VWAP Pullback": "If the price slices through the average line instead of bouncing, the good day is over.",
    "Oversold Bounce": "Sometimes a falling stock keeps falling - bad news can push it lower for days.",
    "Gap & Go": "Morning jumps often fade by lunch when early buyers cash out.",
    "ORB Stocks in Play": "Fake breakouts: it pokes above the morning high, then drops right back.",
    "Bull Flag": "If the 'rest' turns into a slide, the rocket isn't coming.",
    "20-Day Breakout": "Many breakouts fail on the first try and fall back under the old high.",
    "MA20 Reclaim": "In a weak market it can slip back under its normal line the same day.",
    "NR7 Breakout": "The spring can pop DOWN instead of up - that's what the Safety price is for.",
    "Relative Strength": "If the whole market drops hard, even strong kids get dragged down.",
    "Downtrend Reversal": "One good day after months of falling is often just a breather, not a turn.",
    "Oversold Comeback": "A stock knocked down by real bad news may not come back soon.",
    "Hype Breakout": "Reddit crowds leave as fast as they come - hype stocks can crash quickly.",
    "Gap-Down Bounce": "Panic can keep going; only buy once it climbs back above the morning high.",
    "Beaten-Down Turnaround": "Cheap stocks can get cheaper - most turnarounds take many tries.",
    "Episodic Pivot": "Big jumps can fade back down; holding for days means overnight news can hit you too.",
}

RULES = [
    "Never move your Safety price lower to 'give it room'. That's how small losses become big ones.",
    "Decide your Buy, Safety and Win prices BEFORE you buy. Don't make them up while the price is moving.",
    "If the price never reaches the Buy price, there is no trade. Missing a trade costs nothing.",
    "Don't chase. If a stock already ran far past the Buy price, let it go - another one comes tomorrow.",
    "Risk the same small amount on every trade. One bad trade should never hurt much.",
    "Losing trades are normal. Even good skills lose 4 or 5 times out of 10.",
    "After 2 losses in a row, take a break. Angry trades ('revenge trades') are usually bad trades.",
    "Stormy market days (market falling) are harder. Fewer trades is fine on those days.",
    "Big news like earnings can make a stock jump or crash overnight. Know the dates.",
    "Judge a skill on many trades, not one. 5 trades is luck, 50 trades starts to tell you something.",
    "Practice money first. Real money only after the record looks good for 2-3 months.",
    "Write down why you took a trade. Later you'll see which reasons actually worked.",
]


def _real(df):
    if df is None or not len(df):
        return pd.DataFrame(columns=["setup", "r_multiple"])
    f = df[df["status"].isin(FILLED)].copy()
    f["r_multiple"] = pd.to_numeric(f["r_multiple"], errors="coerce").fillna(0.0)
    return f


def _past():
    if not os.path.exists(C.BACKTEST_TRADES_FILE):
        return pd.DataFrame(columns=["setup", "r_multiple", "weather"])
    t = pd.read_csv(C.BACKTEST_TRADES_FILE)
    return t[t["status"].isin(FILLED)]


def rank(df):
    """Every skill with enough trades, best average first: (setup, avg_R, real trades, past-test trades, real total R)."""
    real, past = _real(df), _past()
    rows = []
    for name in {s["name"] for s in load_skills()}:
        r = pd.concat([real.loc[real["setup"] == name, "r_multiple"], past.loc[past["setup"] == name, "r_multiple"]])
        if len(r) >= MIN_TRADES:
            rows.append((name, round(float(r.mean()), 3), int((real["setup"] == name).sum()), int((past["setup"] == name).sum()),
                         round(float(real.loc[real["setup"] == name, "r_multiple"].sum()), 2)))
    return sorted(rows, key=lambda x: -x[1])


def explain(skill):
    w = ", ".join(plain.MOOD[x][0] for x in skill["weather"] if x in plain.MOOD)
    return "\n".join([f"📘 {plain.nick(skill['name'])}",
                      f"What it looks for: {skill['kid_explainer']}",
                      f"Plays on: {w} days",
                      f"Watch out: {WATCH_OUT.get(skill['name'], 'Every skill loses sometimes - always use the Safety price.')}"])


def data_tips(df):
    """Lessons from the bot's own trades (only when there are enough of them)."""
    tips, past, real = [], _past(), _real(df)
    if "weather" in past:
        for name, g in past.groupby("setup"):
            by = g.groupby("weather")["r_multiple"].agg(["mean", "size"])
            by = by[by["size"] >= MIN_TRADES]
            if len(by) >= 2 and by["mean"].max() > 0 and by["mean"].max() - by["mean"].min() >= 0.3:
                hi, lo = by["mean"].idxmax(), by["mean"].idxmin()
                tips.append(f"{plain.nick(name)} did better on {plain.MOOD.get(hi, (hi,))[0]} days "
                            f"({plain.money(by.loc[hi, 'mean'])} a trade) than on {plain.MOOD.get(lo, (lo,))[0]} days "
                            f"({plain.money(by.loc[lo, 'mean'])}), in the past-days test.")
    if df is not None and len(df):
        done = df[df["status"].isin(FILLED + ["no_fill"])]
        if len(done) >= MIN_TRADES:
            miss = (done["status"] == "no_fill").mean() * 100
            tips.append(f"{miss:.0f}% of the bot's picks never reached the Buy price. That's patience working - no trade, no loss.")
        losers = real[real["r_multiple"] < 0]
        if len(losers) >= MIN_TRADES:
            small = (losers["r_multiple"] > -1.3).mean() * 100
            tips.append(f"{small:.0f}% of the bot's losing trades stayed no bigger than planned, because the Safety price did its job.")
    return tips


def tip(df, day):
    """One tip for tonight. Rotates through the bot's own lessons and the safety rules."""
    tips = data_tips(df) + RULES
    return "🎓 Teacher's tip: " + tips[pd.Timestamp(day).toordinal() % len(tips)]


def lesson(df, day):
    """The full /teach lesson: best skills now, how the top one works, and tonight's tip."""
    skills = {s["name"]: s for s in load_skills()}
    top = [r for r in rank(df) if r[1] >= MIN_EDGE_R][:3]
    lines = ["🎓 Teacher's lesson [info only - not advice, no promises]", ""]
    if top:
        lines.append("Best skills right now (average per trade if you risked $10):")
        for i, (name, avg, n_real, n_past, real_r) in enumerate(top, 1):
            lines.append(f"{i}. {plain.nick(name)}: {plain.money(avg)} a trade "
                         f"({n_real} real pick{'' if n_real == 1 else 's'} + {n_past} past-test trades). "
                         f"Real picks so far: {plain.money(real_r)} in total")
        lines += ["", explain(skills[top[0][0]])]
    else:
        lines.append(f"No skill is clearly winning yet (each needs {MIN_TRADES}+ finished trades). Patience!")
    lines += ["", tip(df, day), "", "Type /teach any time for this lesson."]
    return "\n".join(lines)
