"""Offline tests with synthetic prices (no internet needed): python -m tests.test_logic"""
import numpy as np
import pandas as pd

from screener import backtest
from screener.simulate import simulate

NY = "America/New_York"
rng = np.random.default_rng(7)


def make_day(day, open_px, drift, vol_mult=1.0, noise=0.002):
    idx = pd.date_range(day + pd.Timedelta(hours=9, minutes=30), periods=78, freq="5min", tz=NY)
    rets = rng.normal(drift / 78, noise, 78)
    close = open_px * np.exp(np.cumsum(rets))
    opn = np.r_[open_px, close[:-1]]
    high = np.maximum(opn, close) * (1 + abs(rng.normal(0, noise / 2, 78)))
    low = np.minimum(opn, close) * (1 - abs(rng.normal(0, noise / 2, 78)))
    vol = (rng.integers(80_000, 120_000, 78) * vol_mult).astype(float)
    return pd.DataFrame({"Open": opn, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def build():
    days = pd.bdate_range("2026-08-03", periods=30).tz_localize(NY)
    intraday, daily = {}, {}
    for k, t in enumerate(["GAPR", "TRND", "DUMP", "FLAT", "SPY"]):
        px, frames = 50.0, []
        for i, d in enumerate(days):
            if t == "GAPR" and i % 3 == 0:
                df = make_day(d, px * 1.06, 0.04, vol_mult=4)     # gap up + run
            elif t == "TRND" and i % 4 == 0:
                df = make_day(d, px * 1.005, 0.03, vol_mult=2)    # trend day
            elif t == "DUMP" and i >= 10:
                df = make_day(d, px * 0.985, -0.025 if i % 5 else 0.03, vol_mult=1.5)  # selloff
            else:
                df = make_day(d, px, rng.normal(0, 0.01))
            frames.append(df)
            px = df["Close"].iloc[-1]
        bars = pd.concat(frames)
        intraday[t] = bars
        # daily history: 60 quiet days before + aggregates of intraday days
        pre_idx = pd.bdate_range(end=days[0].tz_localize(None) - pd.Timedelta(days=1), periods=60)
        pre_close = 50 * np.exp(np.cumsum(rng.normal(0, 0.01, 60)))
        pre = pd.DataFrame({"Open": pre_close, "High": pre_close * 1.01, "Low": pre_close * 0.99,
                            "Close": pre_close, "Volume": 7_800_000.0}, index=pre_idx)
        agg = bars.groupby(bars.index.normalize().tz_localize(None)).agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        daily[t] = pd.concat([pre, agg])
    return intraday, daily


def test_simulate():
    idx = pd.date_range("2026-09-01 10:35", periods=4, freq="5min", tz=NY)
    bars = pd.DataFrame({"Open": [10, 10.1, 10.3, 10.5], "High": [10.1, 10.35, 10.6, 10.6],
                         "Low": [9.95, 10.05, 10.25, 10.4], "Close": [10.05, 10.3, 10.5, 10.5],
                         "Volume": 1}, index=idx)
    p = {"entry": 10.2, "stop": 10.0, "target": 10.6, "order_type": "buy_stop"}
    r = simulate(p, bars)
    assert r["status"] == "target" and r["r_multiple"] > 1.9, r
    p2 = {"entry": 10.2, "stop": 10.1, "target": 11.0, "order_type": "buy_stop"}
    r2 = simulate(p2, bars)
    assert r2["status"] == "stop" and r2["r_multiple"] < -0.9, r2   # entry bar low 10.05 <= stop
    p3 = {"entry": 12.0, "stop": 11.5, "target": 13.0, "order_type": "buy_stop"}
    assert simulate(p3, bars)["status"] == "no_fill"
    print("simulate OK")


def test_plain():
    from screener import plain
    assert plain.money(1.5) == "+$15.00" and plain.money(-1) == "-$10.00"
    assert plain.nick("VWAP Pullback") == "Dip Buy (VWAP Pullback)"
    assert plain.nick("Brand New Skill") == "Brand New Skill"
    pick = {"ticker": "ABC", "setup": "VWAP Pullback", "order_type": "buy_limit", "entry": 10.0,
            "stop": 9.5, "target": 11.0, "risk_pct": 5.0, "reason": "dipped to VWAP"}
    text = "\n".join(plain.pick_lines(1, pick))
    assert "Buy: only if the price dips DOWN to $10.00" in text and "Safety" in text and "+$20.00" in text, text
    res = plain.results([{**pick, "date": "2026-11-02", "mode": "live", "status": "target", "r_multiple": 2.0},
                         {**pick, "date": "2026-11-02", "mode": "practice", "status": "no_fill", "r_multiple": 0.0}])
    assert "+$20.00" in res and "never reached the Buy price" in res and "risked $10" in res, res
    lk = plain.luck({"trigger_pct": 40, "target_pct": 15, "stop_pct": 20, "avg_r": 0.1, "sessions": 39})
    assert "+$1.00 per $10 risked" in lk and "0.10R" not in lk, lk
    assert plain.clock("15:55") == "3:55 PM" and plain.clock("10:30") == "10:30 AM"
    day = [{"status": "target", "r_multiple": 2.0}, {"status": "stop", "r_multiple": -1.0},
           {"status": "eod", "r_multiple": -0.2}, {"status": "no_fill", "r_multiple": 0.0}]
    assert plain.scorecard(day) == "3 trades. 1 win. 2 losses. 33% wins. Total +$8.00", plain.scorecard(day)
    assert plain.scorecard(day[:1]) == "1 trade. 1 win. 0 losses. 100% wins. Total +$20.00"
    assert plain.scorecard(day[3:]) == "0 trades (no Buy prices were reached)"
    print("plain OK")


def test_new_skills():
    from types import SimpleNamespace
    from screener import engine
    from screener.skills import strong_kid, tight_spring
    # Tight Spring: yesterday was the quietest of the last 7 days, stock in an uptrend
    idx = pd.bdate_range("2026-08-03", periods=60)
    close = np.linspace(40, 50, 60)
    rng_ = np.r_[np.full(59, 1.0), 0.3]                       # last day = narrowest range
    daily = pd.DataFrame({"Open": close, "High": close + rng_ / 2, "Low": close - rng_ / 2,
                          "Close": close, "Volume": 1e6}, index=idx)
    ctx = SimpleNamespace(daily=daily, last=50.05, hod=50.10, lod=49.80, vwap=49.95, atr=1.0, rvol=1.2)
    idea = tight_spring.find(ctx, tight_spring.SKILL["params"])
    assert idea and idea["order_type"] == "buy_stop" and round(idea["entry"], 2) == 50.16, idea   # above yesterday's high
    wide = daily.copy(); wide.iloc[-1, wide.columns.get_loc("High")] += 2
    assert tight_spring.find(SimpleNamespace(**{**vars(ctx), "daily": wide}), tight_spring.SKILL["params"]) is None
    down = daily.copy(); down["Close"] = close[::-1]
    assert tight_spring.find(SimpleNamespace(**{**vars(ctx), "daily": down}), tight_spring.SKILL["params"]) is None
    # Strong Kid: stock +3% while the market is -0.5%
    ctx = SimpleNamespace(day_chg_pct=3.0, market_chg_pct=-0.5, last=103.0, hod=103.2, lod=100.5,
                          vwap=102.0, atr=2.5, rvol=2.0)
    idea = strong_kid.find(ctx, strong_kid.SKILL["params"])
    assert idea and round(idea["entry"], 2) == 103.21 and idea["stop"] >= 101.99 - 1e-9, idea
    assert strong_kid.find(SimpleNamespace(**{**vars(ctx), "market_chg_pct": 1.5}), strong_kid.SKILL["params"]) is None
    assert strong_kid.find(SimpleNamespace(**{**vars(ctx), "market_chg_pct": None}), strong_kid.SKILL["params"]) is None
    assert "stormy" in strong_kid.SKILL["weather"]
    # Wake Up Rally: fell 30% over 3 months, today +5% on 3x volume with a wide range
    from screener.skills import wake_up_rally
    fall = np.linspace(100, 70, 80)
    dd = pd.DataFrame({"Open": fall, "High": fall + 1, "Low": fall - 1, "Close": fall, "Volume": 1e6},
                      index=pd.bdate_range("2026-06-01", periods=80))
    ctx = SimpleNamespace(daily=dd, day_chg_pct=5.0, last=73.4, hod=73.6, lod=70.1, vwap=72.0, atr=2.0, rvol=3.0)
    idea = wake_up_rally.find(ctx, wake_up_rally.SKILL["params"])
    assert idea and round(idea["entry"], 2) == 73.61 and idea["stop"] < idea["entry"], idea
    up = dd.copy(); up["Close"] = fall[::-1]                    # was rising, not falling -> skip
    assert wake_up_rally.find(SimpleNamespace(**{**vars(ctx), "daily": up}), wake_up_rally.SKILL["params"]) is None
    assert wake_up_rally.find(SimpleNamespace(**{**vars(ctx), "rvol": 1.1}), wake_up_rally.SKILL["params"]) is None
    assert wake_up_rally.find(SimpleNamespace(**{**vars(ctx), "hod": 74.6, "lod": 73.0}), wake_up_rally.SKILL["params"]) is None
    # A skill missing from the Guard's team list must start in PRACTICE, never live
    fake = {"name": "Brand New", "weather": ["cloudy"], "params": {},
            "find": lambda c, p: {"order_type": "buy_stop", "entry": 10.0, "stop": 9.8, "target_r": 2, "score": 1, "reason": "x"}}
    old_bc, old_w = engine.build_contexts, engine.weather_bot.check
    engine.build_contexts = lambda *a: [SimpleNamespace(ticker="ABC")]
    engine.weather_bot.check = lambda *a: ("cloudy", "test")
    try:
        live_p, practice_p, _, _ = engine.picks_for_day(None, None, {}, {}, [fake], {"Other": "live"})
    finally:
        engine.build_contexts, engine.weather_bot.check = old_bc, old_w
    assert not live_p and len(practice_p) == 1, (live_p, practice_p)
    assert plain_nick_ok()
    print("new skills OK")


def plain_nick_ok():
    from screener import plain
    return plain.nick("NR7 Breakout") == "Tight Spring (NR7 Breakout)" and plain.nick("Relative Strength") == "Strong Kid (Relative Strength)" \
        and plain.nick("Downtrend Reversal") == "Wake Up Rally (Downtrend Reversal)"


def test_all(tmp="/tmp/dtp_test"):
    import os, shutil
    import screener.config as C
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    for k in ["PICKS_FILE", "BACKTEST_TRADES_FILE", "BACKTEST_SUMMARY_FILE", "SKILL_STATUS_FILE",
              "TUNED_FILE", "COACH_FILE", "REPORT_FILE", "TODAY_POST_FILE"]:
        setattr(C, k, os.path.join(tmp, os.path.basename(getattr(C, k))))
    C.MIN_AVG_DOLLAR_VOL = 1e6
    C.GUARD_MIN_TRADES = 2; C.COACH_MIN_TRADES = 1
    from screener import live, report
    from screener.bots import coach, guard
    from screener.skills import load_skills
    for sk in load_skills():
        if "min_avg_dollar_vol" in sk["params"]:
            import importlib; mod = importlib.import_module("screener.skills.oversold_bounce")
            mod.SKILL["params"]["min_avg_dollar_vol"] = 1e6
    intraday, daily = build()
    from screener.bots import breadth
    bd = pd.bdate_range("2026-06-01", "2026-12-31")
    breadth._cache["df"] = pd.DataFrame({"Breadth_Index_8MA": np.linspace(0.35, 0.75, len(bd)),
                                         "Breadth_200MA_Trend": 1}, index=bd)
    assert breadth.zone(0.65) == "healthy" and breadth.zone(0.2) == "very weak"

    # 1) backtest + coach + guard
    trades, summary, prepared, ib = backtest.run(intraday, daily)
    print(summary.to_string(index=False))
    assert len(trades) and "weather" in trades and "breadth" in trades
    print("\n".join(backtest.by_breadth(trades)))
    print(coach.run(prepared, ib))
    status, changes = guard.run(live.load_picks(), "2026-09-01")
    print(guard.team_sheet(status)); assert set(status) == {s["name"] for s in load_skills()}
    print(coach.approve())

    # 2) live days: scan each morning, grade at the end
    sent = []
    live.to_boss = lambda t: sent.append(("boss", t)) or True
    live.to_community = lambda t: sent.append(("community", t)) or True
    live.load_universe = lambda p: [t for t in intraday if t != "SPY"]
    live.get_daily = lambda t, **k: daily
    days = sorted({d for b in intraday.values() for d in b.index.normalize().unique()})
    for d in days[12:25]:
        cut = d + pd.Timedelta(hours=10, minutes=31)
        live.get_intraday = (lambda c: (lambda t, **k: {x: intraday[x][intraday[x].index < c] for x in t if x in intraday}))(cut)
        live.now_ny = (lambda c: (lambda: c))(cut)
        live.scan()
    live.get_intraday = lambda t, **k: {x: intraday[x] for x in t if x in intraday}
    live.now_ny = lambda: days[-1] + pd.Timedelta(hours=17)
    g = live.grade()
    assert g, "nothing graded"
    report.build()
    df = live.load_picks()
    print(df[["date", "mode", "ticker", "setup", "status", "r_multiple", "breadth"]].to_string())
    assert df["breadth"].notna().all()
    print("\n--- sample message to Boss ---\n" + [t for who, t in sent if who == "boss"][0])
    results_msg = [t for who, t in sent if who == "boss"][-1]
    assert "Today's scorecard" in results_msg and "All-time scorecard" in results_msg, results_msg[-600:]
    print("\n--- results message (end) ---\n" + results_msg[-700:])
    print("ALL OK")


if __name__ == "__main__":
    test_simulate()
    test_plain()
    test_new_skills()
    test_all()
