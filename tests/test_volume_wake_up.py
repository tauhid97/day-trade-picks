"""Offline checks for Volume Wake-Up + the /wakeup list: python -m tests.test_volume_wake_up"""
from types import SimpleNamespace

import numpy as np
import pandas as pd


def fake_ctx(ticker, top, now, rvol=2.0, chg=1.0):
    c = np.r_[np.full(30, top), np.linspace(top, now, 100)]
    daily = pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1e6},
                         index=pd.bdate_range("2026-04-01", periods=130))
    return SimpleNamespace(ticker=ticker, daily=daily, prev_close=float(now), last=float(now) * (1 + chg / 100),
                           rvol=rvol, day_chg_pct=chg)


def test_beaten_rank():
    """The scout gives each stock its watchlist rank: 1 = furthest below its 6-month high (20%+ down only)."""
    from screener import engine
    ctxs = [fake_ctx("AAA", 100, 60), fake_ctx("BBB", 100, 90), fake_ctx("CCC", 50, 35)]
    engine.add_beaten_rank(ctxs)
    r = {c.ticker: c.beaten_rank for c in ctxs}
    assert r == {"AAA": 1, "CCC": 2, "BBB": None}, r          # BBB only 10% down: not beaten
    assert round(ctxs[0].below_high_pct) == 40


def test_volume_wake_up_skill():
    """Buy a top-5 beaten-down stock as soon as its volume is 1.5x normal; 5.9% safety; hold up to 3 days."""
    from screener import config as C, plain
    from screener.bots import teacher
    from screener.setups import make_pick
    from screener.skills import load_skills, volume_wake_up as vw
    p = vw.SKILL["params"]
    assert p["top_n"] == 5 and p["min_rvol"] == 1.5 and p["hold_days"] == 3
    c = SimpleNamespace(ticker="AAA", beaten_rank=2, below_high_pct=40.0, rvol=1.8, last=20.0)
    idea = vw.find(c, p)
    assert idea and idea["target_r"] is None and idea["order_type"] == "buy_stop"
    assert abs(idea["entry"] - 20.01) < 1e-9 and "volume" in idea["reason"].lower()
    pick = make_pick(c, vw.SKILL["name"], idea)
    assert pick and 5.8 <= pick["risk_pct"] <= C.MAX_RISK_PCT, pick   # fits the bot's 6% limit
    assert vw.find(SimpleNamespace(**{**vars(c), "beaten_rank": 6}), p) is None    # not top 5
    assert vw.find(SimpleNamespace(**{**vars(c), "beaten_rank": None}), p) is None # not beaten down
    assert vw.find(SimpleNamespace(**{**vars(c), "rvol": 1.2}), p) is None         # volume still sleepy
    assert vw.find(SimpleNamespace(ticker="X", rvol=3.0, last=10.0), p) is None   # no rank given -> skip
    assert vw.SKILL["weather"] == ["sunny", "cloudy", "stormy"]
    assert vw.SKILL["name"] in [s["name"] for s in load_skills()]
    assert plain.nick(vw.SKILL["name"]) == "Volume Wake-Up (Beaten-Down Volume)"
    assert teacher.WATCH_OUT.get(vw.SKILL["name"])


def test_wakeup_command():
    """/wakeup shows the beaten-down list with a 'volume waking up' flag (info only) + the free Finviz link."""
    from screener import commands, engine
    from screener.bots import wakeup
    ctxs = [fake_ctx("AAA", 100, 60, rvol=2.4, chg=3.1), fake_ctx("CCC", 50, 35, rvol=0.8, chg=-1.0),
            fake_ctx("BBB", 100, 90, rvol=5.0)]
    engine.add_beaten_rank(ctxs)
    t = wakeup.lines(ctxs, pd.Timestamp("2026-11-24 11:05", tz="America/New_York"))
    assert "$AAA" in t and "2.4x" in t and "⚡" in t and "$CCC" in t and "$BBB" not in t, t
    assert t.index("$AAA") < t.index("$CCC") and t.count("⚡") == 1, t
    assert "finviz.com" in t and "practice" in t.lower(), t
    assert "too early" in wakeup.lines([], pd.Timestamp("2026-11-24 09:40", tz="America/New_York")).lower()
    assert "/wakeup" in commands.HELP
    old = wakeup.text
    wakeup.text = lambda: "WAKE"
    try:
        assert commands.answer("/wakeup", None, {}) == "WAKE"
    finally:
        wakeup.text = old
    print("volume wake-up OK")


if __name__ == "__main__":
    test_beaten_rank()
    test_volume_wake_up_skill()
    test_wakeup_command()
