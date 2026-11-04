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
    # swing trades: follow the trade into the next day(s)
    def two_days(day2_open, day2_high):
        d1 = pd.date_range("2026-09-01 10:35", "2026-09-01 15:55", freq="5min", tz=NY)
        d2 = pd.date_range("2026-09-02 09:30", "2026-09-02 15:55", freq="5min", tz=NY)
        b1 = pd.DataFrame({"Open": 10.0, "High": 10.25, "Low": 9.95, "Close": 10.1, "Volume": 1}, index=d1)
        b2 = pd.DataFrame({"Open": day2_open, "High": day2_high, "Low": min(day2_open, 10.0) - 0.02,
                           "Close": day2_open, "Volume": 1}, index=d2)
        return pd.concat([b1, b2])
    sw = {"entry": 10.2, "stop": 9.9, "target": 10.8, "order_type": "buy_stop"}
    r = simulate({**sw, "hold_days": 2}, two_days(10.3, 10.9))
    assert r["status"] == "target" and r["days_held"] == 2, r                  # won on day 2
    r = simulate({**sw, "hold_days": 1}, two_days(10.3, 10.9))
    assert r["status"] == "eod" and r["days_held"] == 1 and r["exit_time"] == "15:55", r   # day trade: sold day 1
    r = simulate({**sw, "hold_days": 2}, two_days(10.4, 10.5))
    assert r["status"] == "eod" and r["days_held"] == 2, r                     # sold at the close of day 2
    r = simulate({**sw, "hold_days": 2}, two_days(9.5, 9.6))
    assert r["status"] == "stop" and r["exit_price"] == 9.5 and r["r_multiple"] < -2, r   # overnight gap: the real, bigger loss
    r = simulate({**sw, "hold_days": 2}, two_days(10.3, 10.9).loc[:"2026-09-01 23:59"])
    assert r["status"] == "open" and r["days_held"] == 1, r                     # day 2 not here yet: still holding
    assert simulate({**sw, "hold_days": float("nan")}, two_days(10.3, 10.9))["status"] == "eod"   # old picks = day trades
    # smart selling: sell half at +1R, then the Safety price moves up to the Buy price
    idx = pd.date_range("2026-09-01 10:35", periods=3, freq="5min", tz=NY)
    up_then_down = pd.DataFrame({"Open": [10.0, 10.25, 10.3], "High": [10.25, 10.45, 10.3],
                                 "Low": [10.05, 10.3, 9.9], "Close": [10.2, 10.4, 9.95], "Volume": 1}, index=idx)
    p = {"entry": 10.2, "stop": 10.0, "target": 10.6, "order_type": "buy_stop"}
    assert simulate(p, up_then_down)["r_multiple"] < -0.9                      # normal: the full loss
    r = simulate({**p, "half_at_r": 1.0}, up_then_down)
    assert r["status"] == "stop" and r["half_price"] == 10.4 and 0.4 < r["r_multiple"] < 0.5, r   # half won, half even
    up = up_then_down.assign(High=[10.25, 10.45, 10.7], Low=[10.05, 10.3, 10.35])
    r = simulate({**p, "half_at_r": 1.0}, up)
    assert r["status"] == "target" and 1.4 < r["r_multiple"] < 1.5, r          # half at +1R, half at +2R
    assert simulate({**p, "half_at_r": float("nan")}, up_then_down)["r_multiple"] < -0.9   # blank = off
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
    assert plain.scorecard(day + [{"status": "open", "r_multiple": 0.0}]) == plain.scorecard(day)   # still holding: not counted yet
    assert plain.result_word({"status": "eod", "days_held": 2}) == "⏰ sold after 2 days"
    assert plain.result_word({"status": "eod", "days_held": 1}) == "⏰ sold at the end of the day"
    assert "still holding" in plain.result_word({"status": "open", "days_held": 1, "hold_days": 2})
    swing = "\n".join(plain.pick_lines(1, {**pick, "hold_days": 2}))
    assert "Hold: up to 2 days" in swing, swing
    assert "Hold:" not in text                                                  # day trades say nothing new
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
    # Crowd Breakout (ORB): Safety price = middle of the opening range (from the YouTube study)
    from screener.skills import orb_stocks_in_play as orb
    ctx = SimpleNamespace(atr=2.0, rvol=3.0, or_open=100.0, or_close=103.0, or_high=104.0, or_low=99.0, last=103.5)
    idea = orb.find(ctx, orb.SKILL["params"])
    assert idea and idea["entry"] == 104.01 and idea["stop"] == 101.5, idea
    assert orb.find(SimpleNamespace(**{**vars(ctx), "or_close": 99.5}), orb.SKILL["params"]) is None   # red range
    assert orb.find(SimpleNamespace(**{**vars(ctx), "last": 104.5}), orb.SKILL["params"]) is None      # already broken
    # Comeback Kid: yesterday a big drop into oversold; today buy only once it climbs above the morning high
    from screener.skills import comeback_kid as ck
    slide = np.r_[np.linspace(100, 80, 59), 76.0]               # steady slide, then -5% yesterday
    dk = pd.DataFrame({"Open": slide, "High": slide + 0.5, "Low": slide - 0.5, "Close": slide, "Volume": 1e6},
                      index=pd.bdate_range("2026-06-01", periods=60))
    ctx = SimpleNamespace(daily=dk, or_high=77.0, last=76.6, lod=75.8, atr=1.5, rvol=1.4, vwap=76.4)
    idea = ck.find(ctx, ck.SKILL["params"])
    assert idea and idea["order_type"] == "buy_stop" and round(idea["entry"], 2) == 77.01 and idea["stop"] < 77, idea
    assert ck.find(SimpleNamespace(**{**vars(ctx), "last": 77.2}), ck.SKILL["params"]) is None       # already broke out
    calm = dk.copy(); calm.iloc[-1, calm.columns.get_loc("Close")] = 80.5                            # no big drop yesterday
    assert ck.find(SimpleNamespace(**{**vars(ctx), "daily": calm}), ck.SKILL["params"]) is None
    assert "stormy" in ck.SKILL["weather"]
    # Hype Rider: Reddit HYPE + heavy volume + moving up -> buy the new high of the day
    from screener.skills import hype_rider as hr
    ctx = SimpleNamespace(hype="hype", rvol=2.5, day_chg_pct=4.0, last=51.0, hod=51.3, vwap=50.2, atr=1.5)
    idea = hr.find(ctx, hr.SKILL["params"])
    assert idea and round(idea["entry"], 2) == 51.31 and idea["stop"] >= 50.19 - 1e-9, idea
    assert hr.find(SimpleNamespace(**{**vars(ctx), "hype": "buzz"}), hr.SKILL["params"]) is None
    assert hr.find(SimpleNamespace(**{k: v for k, v in vars(ctx).items() if k != "hype"}), hr.SKILL["params"]) is None   # backtests: no hype data
    assert hr.find(SimpleNamespace(**{**vars(ctx), "day_chg_pct": -1.0}), hr.SKILL["params"]) is None
    # Crash Bounce: opened 4%+ down on heavy volume; buy only once it climbs back above the morning high
    from screener.skills import gap_down_bounce as gd
    ctx = SimpleNamespace(gap_pct=-6.0, rvol=2.2, or_high=95.0, last=94.2, lod=92.8, atr=2.0, prev_close=100.0)
    idea = gd.find(ctx, gd.SKILL["params"])
    assert idea and idea["order_type"] == "buy_stop" and round(idea["entry"], 2) == 95.01 and idea["stop"] >= 92.79 - 1e-9, idea
    assert gd.find(SimpleNamespace(**{**vars(ctx), "gap_pct": -2.0}), gd.SKILL["params"]) is None    # not a real crash
    assert gd.find(SimpleNamespace(**{**vars(ctx), "rvol": 1.0}), gd.SKILL["params"]) is None        # nobody's trading it
    assert gd.find(SimpleNamespace(**{**vars(ctx), "last": 95.5}), gd.SKILL["params"]) is None       # already bounced past
    assert "stormy" in gd.SKILL["weather"]
    # Underdog: the day after a red market day, a stock 25%+ below its 6-month high; buy above the morning high
    from screener.skills import underdog
    sink = np.r_[np.linspace(100, 70, 130)]                      # slid from 100 to 70 over ~6 months
    du = pd.DataFrame({"Open": sink, "High": sink + 0.5, "Low": sink - 0.5, "Close": sink, "Volume": 1e6},
                      index=pd.bdate_range("2026-04-01", periods=130))
    ctx = SimpleNamespace(daily=du, market_prev_chg=-1.4, day_chg_pct=1.5, last=71.05, vwap=70.9, rvol=1.4,
                          or_high=71.5, lod=70.3, atr=1.8, prev_close=70.0)
    idea = underdog.find(ctx, underdog.SKILL["params"])
    assert idea and round(idea["entry"], 2) == 71.51 and idea["stop"] < idea["entry"], idea
    assert underdog.SKILL["params"]["hold_days"] == 2
    assert underdog.find(SimpleNamespace(**{**vars(ctx), "market_prev_chg": -0.3}), underdog.SKILL["params"]) is None  # yesterday wasn't red
    assert underdog.find(SimpleNamespace(**{**vars(ctx), "market_prev_chg": None}), underdog.SKILL["params"]) is None
    flat = du.copy(); flat["Close"] = 70.0; flat["High"] = 71.0
    assert underdog.find(SimpleNamespace(**{**vars(ctx), "daily": flat}), underdog.SKILL["params"]) is None       # not beaten down
    assert underdog.find(SimpleNamespace(**{**vars(ctx), "last": 71.6}), underdog.SKILL["params"]) is None        # already broke out
    assert "stormy" in underdog.SKILL["weather"]
    # the Scout tells every stock how the market did yesterday
    spy = pd.DataFrame({"Close": [100.0, 98.0]}, index=pd.bdate_range("2026-11-02", periods=2))
    assert round(engine.market_prev_change(pd.Timestamp("2026-11-04", tz=NY), {"SPY": spy}), 1) == -2.0
    # live scans hand every stock its hype level, so Hype Rider can see it
    old_check = engine.hype.check
    engine.hype.check = lambda t: ("hype", "x")
    try:
        cx = [SimpleNamespace(ticker="ABC")]
        engine.add_hype(cx)
        assert cx[0].hype == "hype"
    finally:
        engine.hype.check = old_check
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


def test_news():
    import datetime as dt
    from screener import plain
    from screener.bots import news
    now = pd.Timestamp("2026-11-02 10:31", tz="America/New_York")
    h = lambda hrs, title: (now - pd.Timedelta(hours=hrs), title)
    tag, note = news.classify(dt.date(2026, 11, 2), [], now)
    assert tag == "earnings" and "today" in note, note
    tag, note = news.classify(dt.date(2026, 11, 3), [], now)
    assert tag == "earnings" and "tomorrow" in note, note
    heads = [h(2, "Palantir lands Army deal"), h(5, "Palantir CEO interview"), h(40, "Palantir old news")]
    tag, note = news.classify(dt.date(2026, 12, 1), heads, now)
    assert tag == "news" and "2 headlines" in note and "deal" in note, note
    assert news.classify(None, [h(30, "old")], now)[0] == "quiet"
    assert news.mentions("Palantir (PLTR) rises", "PLTR", "Palantir Technologies Inc.")
    assert news.mentions("Is Palantir a buy?", "PLTR", "Palantir Technologies Inc.")
    assert not news.mentions("Apple and Microsoft report", "PLTR", "Palantir Technologies Inc.")
    assert not news.mentions("Advanced chips rally", "AMD", "Advanced Micro Devices")
    pick = {"ticker": "ABC", "setup": "VWAP Pullback", "order_type": "buy_limit", "entry": 10.0,
            "stop": 9.5, "target": 11.0, "risk_pct": 5.0, "reason": "dipped", "news_note": news.line("news", "1 headline")}
    assert "News [practice, info only]: IN THE NEWS" in "\n".join(plain.pick_lines(1, pick))
    df = pd.DataFrame({"mode": "live", "news": ["earnings", "quiet", "quiet", None],
                       "status": ["target", "stop", "no_fill", "target"], "r_multiple": [2.0, -1.0, 0.0, 1.0]})
    text = "\n".join(news.summary(df))
    assert "Earnings day: 1 trade" in text and "Quiet: 1 trade" in text, text
    # Dip Buy may hold through an earnings report (sell the day after), up to 5 trading days
    mon = pd.Timestamp("2026-11-02")
    assert news.earnings_hold(mon, dt.date(2026, 11, 4))[0] == 4                # Wed report -> sell Thu close
    assert news.earnings_hold(mon, dt.date(2026, 11, 2))[0] == 2                # report today -> sell tomorrow
    assert news.earnings_hold(mon, dt.date(2026, 11, 6))[0] is None            # Fri report -> Mon exit is too far
    assert news.earnings_hold(mon, dt.date(2026, 10, 30))[0] is None           # already happened
    assert news.earnings_hold(mon, None)[0] is None
    assert "Thu Nov 05" in news.earnings_hold(mon, dt.date(2026, 11, 4))[1]


def test_reader():
    """News mood (good/bad headlines) and the Hype bot (Reddit buzz)."""
    import os
    import screener.config as C
    from screener.bots import hype, news
    assert news.mood(["Acme beats estimates, raises guidance", "Analyst upgrades Acme"]) == "good"
    assert news.mood(["Acme misses estimates", "Acme downgraded to sell"]) == "bad"
    assert news.mood(["Acme beats estimates", "Acme sued by rival"]) == "mixed"
    assert news.mood(["Acme CEO interview"]) == "neutral"
    assert news.mood(["Futures fall as techs tumble; Acme rises"]) == "neutral"     # good + bad in one headline
    now = pd.Timestamp("2026-11-02 10:31", tz="America/New_York")
    tag, note = news.classify(None, [(now - pd.Timedelta(hours=2), "Acme upgraded at Goldman")], now)
    assert tag == "news" and "mood: GOOD" in note, note
    assert hype.level(331, 114) == "hype" and hype.level(25, 20) == "buzz" and hype.level(3, 1) == "quiet"
    assert hype.level(None, None) == "quiet"
    hype.fetch = lambda: {"AMD": {"mentions": 331, "mentions_24h_ago": 114}, "MU": {"mentions": 25, "mentions_24h_ago": 30}}
    hype._cache.clear()
    tag, note = hype.check("AMD")
    assert tag == "hype" and "331" in note and "3x" in note, note
    assert hype.check("ZZZ")[0] == "quiet"
    assert "Hype [practice, info only]: 🔥 HYPE" in hype.line(tag, note)
    C.HYPE_HISTORY_FILE, C.NEWS_HISTORY_FILE = "/tmp/dtp_hype.csv", "/tmp/dtp_newsmood.csv"
    for f in (C.HYPE_HISTORY_FILE, C.NEWS_HISTORY_FILE):
        if os.path.exists(f):
            os.remove(f)
    hype.snapshot(["AMD", "MU", "ZZZ"], "2026-11-03"); hype.snapshot(["AMD", "MU", "ZZZ"], "2026-11-03")   # twice -> kept once
    h = pd.read_csv(C.HYPE_HISTORY_FILE)
    assert list(h["ticker"]) == ["AMD", "MU"] and h.loc[0, "level"] == "hype", h
    old = news.headlines
    news.headlines = lambda t: [(now.tz_convert("UTC") - pd.Timedelta(hours=1), f"{t} beats estimates")]
    try:
        news.snapshot(["AMD", "MU"], now)
    finally:
        news.headlines = old
    m = pd.read_csv(C.NEWS_HISTORY_FILE)
    assert list(m["mood"]) == ["good", "good"] and list(m["headlines"]) == [1, 1], m
    for f in (C.HYPE_HISTORY_FILE, C.NEWS_HISTORY_FILE):
        os.remove(f)
    print("reader OK")


def test_teacher():
    """Teacher: ranks skills on real + past-test trades, explains them, gives a nightly tip."""
    import os
    import screener.config as C
    from screener.bots import teacher
    C.BACKTEST_TRADES_FILE = "/tmp/dtp_teacher_bt.csv"
    past = [{"setup": "VWAP Pullback", "status": "target", "r_multiple": 2.0, "weather": "sunny"}] * 8 + \
           [{"setup": "VWAP Pullback", "status": "stop", "r_multiple": -1.0, "weather": "cloudy"}] * 8 + \
           [{"setup": "Gap & Go", "status": "stop", "r_multiple": -1.0, "weather": "sunny"}] * 10
    pd.DataFrame(past).to_csv(C.BACKTEST_TRADES_FILE, index=False)
    real = pd.DataFrame({"setup": ["VWAP Pullback", "Oversold Bounce", "Oversold Bounce"], "mode": "live",
                         "status": ["target", "eod", "no_fill"], "r_multiple": [2.0, 0.5, 0.0]})
    r = teacher.rank(real)
    assert [x[0] for x in r] == ["VWAP Pullback", "Gap & Go"] and r[0][2:] == (1, 16, 2.0), r   # Bounce Back: too few trades
    text = teacher.lesson(real, pd.Timestamp("2026-11-04"))
    assert "1. Dip Buy (VWAP Pullback)" in text and "1 real pick +" in text and "Real picks so far: +$20.00" in text and "Morning Rocket" not in text, text
    assert "Watch out:" in text and "What it looks for:" in text and "not advice" in text, text
    tips = teacher.data_tips(real)
    assert any("did better on ☀️ SUNNY" in t for t in tips), tips                 # the bot's own lesson
    assert teacher.tip(real, "2026-11-04") != teacher.tip(real, "2026-11-05")      # a new tip each night
    assert all(teacher.WATCH_OUT.get(s["name"]) for s in teacher.load_skills())   # every skill has a warning
    os.remove(C.BACKTEST_TRADES_FILE)
    assert "No skill is clearly winning yet" in teacher.lesson(real.iloc[:0], "2026-11-04")
    print("teacher OK")


def test_long_test():
    """2-year test: hourly prices are split into 5-minute steps, every skill is graded normal + smart sell."""
    import os
    import screener.config as C
    from screener.data import hourly_to_5min
    h = pd.DataFrame({"Open": [10.0, 10.8], "High": [11.0, 11.2], "Low": [9.5, 10.6], "Close": [10.8, 10.7],
                      "Volume": [1200.0, 600.0]},
                     index=pd.DatetimeIndex(["2026-09-01 09:30", "2026-09-01 15:30"]).tz_localize(NY))
    f = hourly_to_5min(h)
    first, last = f[f.index < "2026-09-01 10:30"], f[f.index >= "2026-09-01 15:30"]
    assert len(first) == 12 and len(last) == 6 and f.index[-1].strftime("%H:%M") == "15:55", f
    assert first["Open"].iloc[0] == 10.0 and first["Close"].iloc[-1] == 10.8, first
    assert first["High"].max() == 11.0 and first["Low"].min() == 9.5 and first["Volume"].sum() == 1200, first
    C.LONG_TEST_FILE = "/tmp/dtp_long_test.csv"
    intraday, daily = build()
    hourly = {t: b.resample("60min", offset="30min").agg({"Open": "first", "High": "max", "Low": "min",
                                                          "Close": "last", "Volume": "sum"}).dropna()
              for t, b in intraday.items()}
    s = backtest.long_test(hourly, daily)
    assert len(s) and {"setup", "trades", "win_pct", "total_R", "smart_win_pct", "smart_total_R"} <= set(s), s
    assert os.path.exists(C.LONG_TEST_FILE)
    text = backtest.long_text(s)
    assert "2-year practice test" in text and "smart sell" in text and "rough" in text, text
    assert "not enough" in backtest.long_text(s.iloc[:0])
    os.remove(C.LONG_TEST_FILE)
    print(text + "\nlong test OK")


def test_watchlist():
    """Beaten-down watchlist + red-day 'holding up best' list."""
    import os
    import screener.config as C
    from screener.bots import watchlist
    C.WATCHLIST_FILE = "/tmp/dtp_watchlist.json"
    idx = pd.bdate_range("2026-04-01", periods=130)
    def stock(top, now):
        c = np.r_[np.full(30, top), np.linspace(top, now, 100)]
        return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1e6}, index=idx)
    daily = {"AAA": stock(100, 60), "BBB": stock(100, 90), "CCC": stock(50, 35), "SPY": stock(500, 480)}
    today = idx[-1] + pd.offsets.BDay(1)
    w = watchlist.build(daily, today, {"AAA": -3.0, "BBB": 0.5, "CCC": 1.2}, market_chg=-1.6)
    assert [x["ticker"] for x in w["beaten"]] == ["AAA", "CCC"], w            # BBB only 10% down: not beaten
    assert w["beaten"][0]["below_high_pct"] == 40 and w["red_day"], w
    assert [x["ticker"] for x in w["holding_up"]][:2] == ["CCC", "BBB"], w   # best on a red day first
    text = "\n".join(watchlist.lines(w))
    assert "Beaten-down watchlist" in text and "$AAA" in text and "Red day" in text, text
    calm = watchlist.build(daily, today, {"AAA": 1.0}, market_chg=0.3)
    assert not calm["red_day"] and "Red day" not in "\n".join(watchlist.lines(calm))
    assert "$AAA" in watchlist.text()                                         # /watchlist reads the saved list
    os.remove(C.WATCHLIST_FILE)
    print("watchlist OK")


def plain_nick_ok():
    from screener import plain
    return plain.nick("NR7 Breakout") == "Tight Spring (NR7 Breakout)" and plain.nick("Relative Strength") == "Strong Kid (Relative Strength)" \
        and plain.nick("Downtrend Reversal") == "Wake Up Rally (Downtrend Reversal)" \
        and plain.nick("Oversold Comeback") == "Comeback Kid (Oversold Comeback)" \
        and plain.nick("Hype Breakout") == "Hype Rider (Hype Breakout)" \
        and plain.nick("Gap-Down Bounce") == "Crash Bounce (Gap-Down Bounce)" \
        and plain.nick("Beaten-Down Turnaround") == "Underdog (Beaten-Down Turnaround)"


def test_all(tmp="/tmp/dtp_test"):
    import os, shutil
    import screener.config as C
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    for k in ["PICKS_FILE", "BACKTEST_TRADES_FILE", "BACKTEST_SUMMARY_FILE", "SKILL_STATUS_FILE",
              "TUNED_FILE", "COACH_FILE", "REPORT_FILE", "TODAY_POST_FILE", "STUDY_FILE",
              "HYPE_HISTORY_FILE", "NEWS_HISTORY_FILE", "WATCHLIST_FILE", "LONG_TEST_FILE"]:
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
    from screener.bots import news
    news.earnings_date = lambda t: None
    news.headlines = lambda t: [(pd.Timestamp.now(tz="UTC"), f"{t} wins big contract")]
    news.company_name = lambda t: None
    from screener.bots import hype
    hype.fetch = lambda: {"GAPR": {"mentions": 80, "mentions_24h_ago": 20}}
    hype._cache.clear()

    # 1) backtest + coach + guard
    trades, summary, prepared, ib = backtest.run(intraday, daily)
    print(summary.to_string(index=False))
    assert len(trades) and "weather" in trades and "breadth" in trades
    print("\n".join(backtest.by_breadth(trades)))
    print(coach.run(prepared, ib))
    assert coach.nightly(prepared, ib) == ""                     # same ideas as last night -> stays quiet
    open(C.COACH_FILE, "w").write("{}")
    tip = coach.nightly(prepared, ib)
    assert (tip != "") == bool(coach._changes()), tip           # a new idea -> speaks up
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
    assert df["news"].notna().all() and "news_note" not in df
    assert df["hype"].notna().all() and "hype_note" not in df
    assert "Hype [practice, info only]" in [t for who, t in sent if who == "boss"][0]
    assert all("Hype [practice" not in t for who, t in sent if who == "community")
    assert "News [practice, info only]" in [t for who, t in sent if who == "boss"][0]
    assert "Beaten-down watchlist" in [t for who, t in sent if who == "boss"][0]
    assert all("Beaten-down watchlist" not in t for who, t in sent if who == "community")
    assert all("News [practice" not in t for who, t in sent if who == "community")
    print("\n--- sample message to Boss ---\n" + [t for who, t in sent if who == "boss"][0])
    results_msg = [t for who, t in sent if who == "boss"][-1]
    assert "Today's scorecard" in results_msg and "All-time scorecard" in results_msg, results_msg[-600:]
    print("\n--- results message (end) ---\n" + results_msg[-700:])

    # 3) evening with nothing to grade -> still tell Boss
    n = len(sent)
    assert live.grade() == []
    quiet = sent[-1][1]
    assert len(sent) == n + 1 and "no picks were made today" in quiet and "All-time scorecard" in quiet, quiet
    # a pick whose prices couldn't be downloaded -> say we'll retry
    stuck = live.load_picks().iloc[[0]].assign(ticker="ZZZZ", status=None)
    live.save_picks(pd.concat([live.load_picks(), stuck], ignore_index=True))
    live.grade()
    assert "couldn't get prices" in sent[-1][1], sent[-1][1]
    print("\n--- quiet evening message ---\n" + quiet)

    # 4) Telegram commands: Boss types /status, /picks, /scoreboard, /skills
    from screener import commands
    os.environ["TELEGRAM_CHAT_ID"] = "111"
    msg = lambda uid, chat, text: {"update_id": uid, "message": {"chat": {"id": chat}, "text": text}}
    inbox = [msg(10, 111, "/status"), msg(11, 111, "/picks"), msg(12, 111, "/scoreboard"),
             msg(13, 999, "/picks"),                       # a stranger: ignored
             msg(14, 111, "/skills"), msg(15, 111, "hi bot"), msg(16, 111, "/Status@BossSignalsBot")]
    asked, replies = [], []
    commands.get_updates = lambda offset: asked.append(offset) or [u for u in inbox if u["update_id"] >= (offset or 0)]
    commands.to_boss = lambda t: replies.append(t) or True
    commands.handle()
    assert asked == [None, 17], asked                       # read, then tell Telegram we're done up to 16
    assert len(replies) == 6, replies                       # stranger never answered
    assert "awake" in replies[0].lower() and "skills" in replies[0].lower(), replies[0]
    assert "Buy:" in replies[1] and "Safety" in replies[1], replies[1]
    assert "All-time scorecard" in replies[2] and "Dip Buy" in replies[2], replies[2]
    assert "LIVE" in replies[3] and "PRACTICE" in replies[3], replies[3]
    assert "/scoreboard" in replies[4] and "/picks" in replies[4], replies[4]   # unknown -> help
    assert "awake" in replies[5].lower()                                        # works with @botname
    saved = list(replies)
    replies.clear(); inbox.clear(); commands.handle()
    assert replies == [] and asked[-1] is None, (replies, asked)                # nothing new -> quiet
    print("\n--- command replies ---\n" + "\n\n".join(saved))

    # 5) Study bot: after the close it studies past charts for clues that came before rises / drops
    from screener.bots import study
    hype.snapshot(list(daily), "2026-09-04"); news.snapshot(list(daily), live.now_ny())
    assert os.path.exists(C.HYPE_HISTORY_FILE) and os.path.exists(C.NEWS_HISTORY_FILE)
    note = study.run(daily)
    assert "Study bot" in note and "Biggest riser" in note and "Biggest faller" in note, note
    assert os.path.exists(C.STUDY_FILE)
    assert "Study bot" in commands.answer("/lessons", live.load_picks(), {})
    assert "/lessons" in commands.HELP and "/watchlist" in commands.HELP and "/teach" in commands.HELP
    assert "Teacher's lesson" in commands.answer("/teach", live.load_picks(), {})
    assert "watchlist" in commands.answer("/watchlist", live.load_picks(), {}).lower()
    n = len(sent); live.grade(note=note)                     # the note rides along in the evening message
    assert len(sent) == n + 1 and "Study bot" in sent[-1][1], sent[-1][1]
    print("\n--- study note ---\n" + note + "\n\n--- /lessons ---\n" + commands.answer("/lessons", live.load_picks(), {}))

    # 6) a 2-day swing pick: still holding after day 1, graded after day 2
    d1, d2 = days[-2], days[-1]
    first = intraday["FLAT"][intraday["FLAT"].index >= d1 + pd.Timedelta(hours=10, minutes=35)].iloc[0]
    row = {"date": d1.strftime("%Y-%m-%d"), "published_at": (d1 + pd.Timedelta(hours=10, minutes=31)).isoformat(),
           "mode": "practice", "ticker": "FLAT", "setup": "NR7 Breakout", "order_type": "buy_stop",
           "entry": round(first["Open"] * 0.999, 2), "stop": round(first["Open"] * 0.5, 2),
           "target": round(first["Open"] * 2, 2), "risk_pct": 50.0, "reason": "test swing", "hold_days": 2}
    live.save_picks(pd.concat([live.load_picks(), pd.DataFrame([row])], ignore_index=True))
    live.now_ny = lambda: d1 + pd.Timedelta(hours=17)
    live.get_intraday = lambda t, **k: {x: intraday[x][intraday[x].index < d2] for x in t if x in intraday}
    live.grade()
    held = live.load_picks().iloc[-1]
    assert held["status"] == "open", held.to_dict()
    assert "still holding" in sent[-1][1], sent[-1][1]
    live.now_ny = lambda: d2 + pd.Timedelta(hours=17)
    live.get_intraday = lambda t, **k: {x: intraday[x] for x in t if x in intraday}
    live.grade()
    done = live.load_picks().iloc[-1]
    assert done["status"] == "eod" and int(done["days_held"]) == 2, done.to_dict()
    assert "sold after 2 days" in sent[-1][1], sent[-1][1]
    report.build()
    print("ALL OK")


def test_study_finds_a_planted_clue():
    """Heavy-volume days are always followed by a +2% day: the Study bot must spot that, on unseen days too."""
    import os
    import screener.config as C
    from screener.bots import study
    C.STUDY_FILE = "/tmp/dtp_study_test.json"
    idx = pd.bdate_range("2025-06-02", periods=260)
    daily = {}
    for t, seed in [("AAA", 1), ("BBB", 2), ("CCC", 3), ("SPY", 4)]:
        r = np.random.default_rng(seed)
        o = 50 + np.cumsum(r.normal(0, 0.1, len(idx)))
        c = o * (1 + r.normal(0, 0.002, len(idx)))
        v = np.full(len(idx), 1e6)
        for i in range(25, len(idx) - 1, 6):
            v[i] = 4e6                                       # heavy volume today...
            c[i + 1] = o[i + 1] * 1.02                       # ...then +2% open-to-close tomorrow
        daily[t] = pd.DataFrame({"Open": o, "High": np.maximum(o, c) * 1.001, "Low": np.minimum(o, c) * 0.999,
                                 "Close": c, "Volume": v}, index=idx)
    # Reddit hype history for the last 120 days: hyped days are followed by a -2% day
    C.HYPE_HISTORY_FILE, C.NEWS_HISTORY_FILE = "/tmp/dtp_hype_plant.csv", "/tmp/dtp_news_plant.csv"
    rows = []
    for t in ["AAA", "BBB", "CCC"]:
        d = daily[t]
        for i in range(len(idx) - 120, len(idx) - 1):
            hyped = i % 4 == 0 and i % 6 != 1                # never on a heavy-volume day
            rows.append({"date": idx[i].strftime("%Y-%m-%d"), "ticker": t, "mentions": 90 if hyped else 2,
                         "mentions_24h_ago": 10 if hyped else 2, "level": "hype" if hyped else "quiet"})
            if hyped:
                d.iloc[i + 1, d.columns.get_loc("Close")] = d["Open"].iloc[i + 1] * 0.98
    pd.DataFrame(rows).to_csv(C.HYPE_HISTORY_FILE, index=False)
    old = study.MIN_CHECK
    study.MIN_CHECK = 10
    try:
        study.run(daily)
    finally:
        study.MIN_CHECK = old
    notes = study.load()
    heavy = [x for x in notes["clues"] if x["name"].startswith("Heavy volume")][0]
    assert heavy["held"] and heavy["kind"] == "rise" and heavy["check"]["rise_pct"] > 90, heavy
    hyped = [x for x in notes["clues"] if x["name"].startswith("Reddit hype")][0]
    assert hyped["held"] and hyped["kind"] == "fall", hyped
    assert any(" + " in x["name"] for x in notes["clues"]), "no combos studied"
    names = {x["name"] for x in notes["clues"]}
    assert "Far below its 6-month high (25%+)" in names and "Red market day (SPY down 1%+)" in names, names
    text = study.lessons_text()
    assert "Heavy volume" in text and "Reddit hype" in text, text
    for f in (C.STUDY_FILE, C.HYPE_HISTORY_FILE):
        os.remove(f)
    print("study OK")


if __name__ == "__main__":
    test_simulate()
    test_plain()
    test_news()
    test_reader()
    test_watchlist()
    test_teacher()
    test_long_test()
    test_new_skills()
    test_study_finds_a_planted_clue()
    test_all()
