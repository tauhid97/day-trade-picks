"""Offline checks for Gap & Go's 'up over the past month' rule: python -m tests.test_gap_and_go_trend"""
from types import SimpleNamespace

import pandas as pd


def test_gap_and_go_trend():
    """Gap & Go only picks stocks whose close is higher than ~a month (20 trading days) ago (practice)."""
    from screener.skills import gap_and_go as gg
    p = dict(gg.SKILL["params"])
    assert p["trend_days"] == 20

    def ctx(closes):
        daily = pd.DataFrame({"Close": closes}, index=pd.bdate_range("2026-09-01", periods=len(closes)))
        return SimpleNamespace(gap_pct=5.0, rvol=3.0, last=10.0, vwap=9.8, hod=10.1, or_low=9.6, atr=0.5, daily=daily)

    up = [8.0 + 0.05 * i for i in range(30)]          # climbing for a month
    down = [12.0 - 0.05 * i for i in range(30)]       # sliding for a month
    assert gg.find(ctx(up), p) is not None
    assert "past month" in gg.find(ctx(up), p)["reason"]
    assert gg.find(ctx(down), p) is None
    assert gg.find(ctx(up[:15]), p) is None           # not enough history -> skip
    flat = [10.0] * 30
    assert gg.find(ctx(flat), p) is None              # must be higher, not equal
    print("gap & go trend OK")


if __name__ == "__main__":
    test_gap_and_go_trend()
