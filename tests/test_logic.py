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

    # 1) backtest + coach + guard
    trades, summary, prepared, ib = backtest.run(intraday, daily)
    print(summary.to_string(index=False))
    assert len(trades) and "weather" in trades
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
    print(df[["date", "mode", "ticker", "setup", "status", "r_multiple"]].to_string())
    print("\n--- sample message to Boss ---\n" + [t for who, t in sent if who == "boss"][0])
    print("\n--- results message ---\n" + [t for who, t in sent if who == "boss"][-1][:1500])
    print("ALL OK")


if __name__ == "__main__":
    test_simulate()
    test_all()
