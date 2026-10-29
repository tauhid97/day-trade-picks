"""COACH BOT - tries small tweaks to each skill's settings to find better ones.

How it avoids fooling itself (overfitting):
 1. It only changes ONE setting at a time, from a short list of sensible values.
 2. It learns on the older 60% of days, then checks on the newer 40% it never saw.
 3. It only suggests a change if it wins on BOTH, by at least 1R on the unseen days.
 4. Nothing changes until YOU approve it (Actions -> Run workflow -> approve).
"""
import json
import os

import pandas as pd

from .. import config as C
from ..backtest import trades_for
from ..skills import load_skills


def _score(trades, days):
    f = [t for t in trades if t["date"] in days and t["status"] != "no_fill"]
    return round(sum(t["r_multiple"] for t in f), 2), len(f)


def run(prepared, intraday):
    all_days = [d["day"].strftime("%Y-%m-%d") for d in prepared]
    cut = int(len(all_days) * C.COACH_TRAIN_SHARE)
    train, test = set(all_days[:cut]), set(all_days[cut:])
    suggestions, lines = {}, ["Coach report (learned on older days, checked on newer unseen days):"]
    for sk in load_skills():
        base = sk["params"]
        variants = [dict(base)]
        for k, vals in sk.get("tune", {}).items():
            for v in vals:
                if base.get(k) != v:
                    variants.append({**base, k: v})
        results = []
        for p in variants:
            tr = trades_for(sk, p, prepared, intraday)
            results.append((p, _score(tr, train), _score(tr, test)))
        base_train, base_test = results[0][1], results[0][2]
        ok = [r for r in results[1:] if r[1][1] >= C.COACH_MIN_TRADES and r[1][0] > base_train[0]]
        best = max(ok, key=lambda r: r[1][0]) if ok else None
        if best and best[2][0] - base_test[0] >= C.COACH_MIN_IMPROVEMENT_R:
            change = {k: v for k, v in best[0].items() if base.get(k) != v}
            suggestions[sk["name"]] = {"change": change, "train_R": [base_train[0], best[1][0]],
                                       "test_R": [base_test[0], best[2][0]]}
            lines.append(f"- {sk['name']}: try {change}. Unseen days: {base_test[0]:+.1f}R -> {best[2][0]:+.1f}R")
        else:
            lines.append(f"- {sk['name']}: current settings are fine (unseen days {base_test[0]:+.1f}R)")
    os.makedirs(os.path.dirname(C.COACH_FILE), exist_ok=True)
    json.dump(suggestions, open(C.COACH_FILE, "w"), indent=2, default=str)
    if suggestions:
        lines.append("To accept: GitHub -> Actions -> Daily picks -> Run workflow -> choose 'approve'.")
    return "\n".join(lines)


def approve():
    if not os.path.exists(C.COACH_FILE):
        return "No coach suggestions to approve."
    sugg = json.load(open(C.COACH_FILE))
    if not sugg:
        return "No coach suggestions to approve."
    tuned = json.load(open(C.TUNED_FILE)) if os.path.exists(C.TUNED_FILE) else {}
    for name, s in sugg.items():
        tuned.setdefault(name, {}).update(s["change"])
    json.dump(tuned, open(C.TUNED_FILE, "w"), indent=2)
    json.dump({}, open(C.COACH_FILE, "w"))
    return "Approved coach changes: " + ", ".join(f"{n} {s['change']}" for n, s in sugg.items())
