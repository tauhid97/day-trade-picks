"""TIME MACHINE BOT - idea borrowed from Jake Schincariol's open-source
trader-timemachine (MIT), rewritten for our team.

For each pick it replays the rest of today 2,000 times, using this stock's own
5-minute moves from the same time of day on past full sessions. It reports how
often the order triggers, hits the target first, hits the stop first, and the
average R. It's a reality check (a simulation), not a prediction.
"""
import numpy as np
import pandas as pd

from .. import config as C

REPLAYS = 2000
SEED = 19
WINDOW = 2   # borrow bars from +/- 2 bars around the same time of day


def odds(pick, bars, now_ts):
    days = bars.index.normalize()
    today = now_ts.normalize()
    sessions = [g for d, g in bars[days < today].groupby(days[days < today]) if len(g) == 78]
    if len(sessions) < 15:
        return None
    o = np.array([g["Open"].values for g in sessions])
    h = np.array([g["High"].values for g in sessions])
    l = np.array([g["Low"].values for g in sessions])
    c = np.array([g["Close"].values for g in sessions])
    prev = np.concatenate([o[:, :1], c[:, :-1]], axis=1)
    ro, rh, rl, rc = o / prev, h / prev, l / prev, c / prev

    tb = bars[(days == today) & (bars.index < now_ts)]
    if tb.empty:
        return None
    start = len(tb)                       # next bar index (0 = 9:30)
    times = [f"{9 + (30 + 5 * i) // 60:02d}:{(30 + 5 * i) % 60:02d}" for i in range(78)]
    rng = np.random.default_rng(SEED)
    n = REPLAYS
    price = np.full(n, float(tb["Close"].iloc[-1]))
    entry, stop = pick["entry"], pick["stop"]
    target = pick.get("target")
    target = None if target is None or target != target else target
    risk = entry - stop
    filled = np.zeros(n, bool); done = np.zeros(n, bool)
    r = np.zeros(n); outcome = np.zeros(n, int)   # 1 target, -1 stop, 0 other
    for i in range(start, 78):
        lo, hi = max(0, i - WINDOW), min(77, i + WINDOW)
        si = rng.integers(0, len(sessions), n)
        bi = rng.integers(lo, hi + 1, n)
        bo, bh, bl, bc = price * ro[si, bi], price * rh[si, bi], price * rl[si, bi], price * rc[si, bi]
        bh = np.maximum(bh, np.maximum(bo, bc)); bl = np.minimum(bl, np.minimum(bo, bc))
        live = ~done
        if times[i] < C.LAST_ENTRY_TIME:
            hit = (bh >= entry) if pick["order_type"] == "buy_stop" else (bl <= entry)
            newly = live & ~filled & hit
            filled |= newly
        else:
            newly = np.zeros(n, bool)
        act = live & filled
        stp = act & (bl <= stop)
        r[stp] = -1.0; outcome[stp] = -1; done |= stp
        if target is not None:
            tgt = act & ~stp & ~newly & (bh >= target)
            r[tgt] = (target - entry) / risk; outcome[tgt] = 1; done |= tgt
        if times[i] >= C.EXIT_TIME:
            rest = act & ~done
            r[rest] = (bc[rest] - entry) / risk; done |= rest
        price = bc
    rest = filled & ~done
    r[rest] = (price[rest] - entry) / risk
    f = filled.sum()
    return {
        "trigger_pct": round(f / n * 100),
        "target_pct": round((outcome == 1).sum() / n * 100),
        "stop_pct": round((outcome == -1).sum() / n * 100),
        "avg_r": round(float(r[filled].mean()) if f else 0.0, 2),
        "sessions": len(sessions),
    }


def line(o):
    if not o:
        return "Time Machine: not enough history for this stock."
    return (f"Time Machine ({REPLAYS:,} replays of its last {o['sessions']} days): triggers {o['trigger_pct']}%, "
            f"target first {o['target_pct']}%, stop first {o['stop_pct']}%, avg {o['avg_r']:+.2f}R if triggered. "
            f"Simulation, not a prediction.")
