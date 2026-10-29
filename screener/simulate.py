"""Grades a pick against the price bars that came AFTER it was published.

Conservative rules: if stop and target are both touched in the same bar we
assume the stop hit first; no target fills in the entry bar; slippage on
both sides.
"""
import pandas as pd

from . import config as C


def simulate(pick: dict, bars_after: pd.DataFrame) -> dict:
    entry, stop, target = pick["entry"], pick["stop"], pick.get("target")
    if target is not None and target != target:   # NaN from CSV -> no target
        target = None
    risk = entry - stop
    res = {"status": "no_fill", "fill_price": None, "exit_price": None,
           "exit_time": None, "r_multiple": 0.0, "pct_return": 0.0}
    t = bars_after.index.strftime("%H:%M")
    filled_at = None
    for i, (ts, bar) in enumerate(bars_after.iterrows()):
        hm = t[i]
        if filled_at is None:
            if hm >= C.LAST_ENTRY_TIME:
                return res
            if pick["order_type"] == "buy_stop" and bar["High"] >= entry:
                fill = max(entry, bar["Open"])
            elif pick["order_type"] == "buy_limit" and bar["Low"] <= entry:
                fill = min(entry, bar["Open"])
            else:
                continue
            filled_at = i
            res["fill_price"] = round(fill, 2)
            if bar["Low"] <= stop:                     # stopped in the entry bar
                return _close(res, stop, ts, "stop", risk, entry)
            if hm >= C.EXIT_TIME:
                return _close(res, bar["Close"], ts, "eod", risk, entry)
            continue
        if bar["Low"] <= stop:
            return _close(res, min(stop, bar["Open"]), ts, "stop", risk, entry)
        if target is not None and bar["High"] >= target:
            return _close(res, max(target, bar["Open"]), ts, "target", risk, entry)
        if hm >= C.EXIT_TIME:
            return _close(res, bar["Close"], ts, "eod", risk, entry)
    if filled_at is not None:                          # ran out of bars (data ends early)
        last_ts = bars_after.index[-1]
        return _close(res, bars_after["Close"].iloc[-1], last_ts, "eod", risk, entry)
    return res


def _close(res, exit_px, ts, status, risk, planned_entry):
    fill = res["fill_price"] * (1 + C.SLIPPAGE_PCT)
    ex = exit_px * (1 - C.SLIPPAGE_PCT)
    res.update(status=status, exit_price=round(float(exit_px), 2),
               exit_time=ts.strftime("%H:%M"),
               r_multiple=round((ex - fill) / risk, 3),
               pct_return=round((ex / fill - 1) * 100, 3))
    return res
