"""Offline checks for the Turnaround Tuesday skill: python -m tests.test_turnaround_tuesday"""
import pandas as pd

from screener.simulate import simulate

NY = "America/New_York"


def test_turnaround_tuesday():
    """Turnaround Tuesday: QQQ down Friday AND Monday -> buy Monday's close, sell Tuesday's close (practice)."""
    import os
    import screener.config as C
    from screener import plain
    from screener.bots import teacher
    from screener.skills import load_skills, turnaround_tuesday as tt
    days = pd.DatetimeIndex(["2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09"])   # Wed Thu Fri Mon
    def qqq(closes):
        return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1e6}, index=days)
    assert tt.signal(qqq([100, 101, 100, 99]), "2026-11-09")                 # Fri red + Mon red
    assert not tt.signal(qqq([100, 99, 100, 99]), "2026-11-09")              # Fri was green
    assert not tt.signal(qqq([100, 101, 100, 101]), "2026-11-09")            # Mon was green
    assert not tt.signal(qqq([100, 101, 100, 99]), "2026-11-10")             # today's bar not there yet
    tue = pd.DatetimeIndex(["2026-11-05", "2026-11-06", "2026-11-09", "2026-11-10"])     # Thu Fri Mon Tue
    assert not tt.signal(pd.DataFrame({"Close": [100, 99, 98, 97]}, index=tue), "2026-11-10")   # Tuesday: not first day of week
    hol = pd.DatetimeIndex(["2026-01-15", "2026-01-16", "2026-01-20"])        # Thu Fri, Monday holiday -> Tue
    assert tt.signal(pd.DataFrame({"Close": [100, 99, 98]}, index=hol), "2026-01-20")
    # the morning scan never fires it (it only runs in the evening)
    assert tt.SKILL["weather"] == [] and tt.SKILL["name"] in [s["name"] for s in load_skills()]
    # the pick it makes
    now = pd.Timestamp("2026-11-09 17:35", tz=NY)
    pk = tt.make_pick(99.0, now, "practice")
    assert pk["ticker"] == "QQQ" and pk["order_type"] == "at_close" and pk["mode"] == "practice", pk
    assert round(pk["stop"], 2) == 96.03 and pk["hold_days"] == 1 and pk["date"] == "2026-11-09", pk
    # grading: already bought at Monday's close, sold at Tuesday 3:55 PM
    d2 = pd.date_range("2026-11-10 09:30", "2026-11-10 15:55", freq="5min", tz=NY)
    up = pd.DataFrame({"Open": 99.5, "High": 100.2, "Low": 99.2, "Close": 100.0, "Volume": 1}, index=d2)
    r = simulate(pk, up)
    assert r["status"] == "eod" and r["exit_time"] == "15:55" and r["fill_price"] == 99.0 and r["days_held"] == 1, r
    assert r["pct_return"] > 0.9, r
    gap = up.assign(Open=95.0, Low=94.5, High=95.5, Close=95.2)                # Tuesday opens below the Safety price
    r = simulate(pk, gap)
    assert r["status"] == "stop" and r["exit_price"] == 95.0 and r["r_multiple"] < -1.3, r
    assert simulate(pk, up.iloc[:0])["status"] == "open"                      # Tuesday hasn't happened yet: still holding
    # plain words
    assert plain.nick("Turnaround Tuesday") == "Monday Bounce (Turnaround Tuesday)"
    text = "\n".join(plain.pick_lines(1, pk))
    assert "at today's closing price" in text and "next trading day" in text, text
    line = plain.practice_line(1, pk)
    assert "buy at the close" in line and "sell 3:55 PM next trading day" in line, line
    assert "Monday" in teacher.explain(tt.SKILL)
    # evening job: saves one practice pick and tells Boss; never twice for the same day
    C.PICKS_FILE = "/tmp/dtp_tt_picks.csv"
    if os.path.exists(C.PICKS_FILE):
        os.remove(C.PICKS_FILE)
    sent = []
    msg = tt.evening(now, daily=qqq([100, 101, 100, 99]), send=sent.append)
    msg2 = tt.evening(now, daily=qqq([100, 101, 100, 99]), send=sent.append)
    from screener import live
    df = live.load_picks()
    assert len(df) == 1 and df.iloc[0]["setup"] == "Turnaround Tuesday" and df.iloc[0]["mode"] == "practice", df
    assert msg and not msg2 and len(sent) == 1 and "PRACTICE" in sent[0] and "$QQQ" in sent[0], sent
    assert tt.evening(now, daily=qqq([100, 99, 100, 101]), send=sent.append) == "" and len(sent) == 1
    os.remove(C.PICKS_FILE)
    print("turnaround tuesday OK")


if __name__ == "__main__":
    test_turnaround_tuesday()
