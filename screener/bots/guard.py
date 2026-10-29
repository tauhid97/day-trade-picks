"""GUARD BOT - the bouncer. Watches every skill's results.

- A skill that keeps losing gets benched to PRACTICE (its picks still get
  tracked, but they're labeled practice and never go to the community).
- A practice skill that starts winning gets promoted back to LIVE.
- Brand-new skills start in PRACTICE until they prove themselves.
Evidence = the skill's last 20 real graded trades; if it has fewer than 10,
the backtest is used instead.
"""
import json
import os

import pandas as pd

from .. import config as C
from ..skills import load_skills


def load_status():
    if os.path.exists(C.SKILL_STATUS_FILE):
        return json.load(open(C.SKILL_STATUS_FILE))
    return {}


def modes():
    return {k: v["mode"] for k, v in load_status().items()}


def run(picks: pd.DataFrame, today: str):
    old = load_status()
    bt = pd.read_csv(C.BACKTEST_SUMMARY_FILE) if os.path.exists(C.BACKTEST_SUMMARY_FILE) else pd.DataFrame()
    new, changes = {}, []
    for sk in load_skills():
        name = sk["name"]
        prev = old.get(name, {"mode": "practice", "why": "New skill - must prove itself first", "since": today})
        evidence, avg = None, None
        if len(picks):
            real = picks[(picks["setup"] == name) & picks["status"].isin(["target", "stop", "eod"])]
            real = real.sort_values("published_at").tail(C.GUARD_WINDOW)
            if len(real) >= C.GUARD_MIN_TRADES:
                evidence, avg = f"last {len(real)} real trades", float(pd.to_numeric(real["r_multiple"]).mean())
        if evidence is None and len(bt) and (bt["setup"] == name).any():
            row = bt[bt["setup"] == name].iloc[0]
            if row["filled"] >= C.GUARD_MIN_TRADES:
                evidence, avg = f"backtest ({int(row['filled'])} trades)", float(row["avg_R"])
        mode, why = prev["mode"], prev["why"]
        if avg is not None:
            if avg < C.GUARD_BENCH_BELOW_R:
                mode, why = "practice", f"Benched: averaging {avg:+.2f}R over {evidence}"
            elif avg > C.GUARD_PROMOTE_ABOVE_R:
                mode, why = "live", f"Playing: averaging {avg:+.2f}R over {evidence}"
            else:
                why = f"Holding: averaging {avg:+.2f}R over {evidence} (not clearly good or bad)"
        since = prev["since"] if mode == prev["mode"] else today
        new[name] = {"mode": mode, "why": why, "since": since}
        if name in old and mode != old[name]["mode"]:
            changes.append(f"{name}: {old[name]['mode'].upper()} -> {mode.upper()} ({why})")
        elif name not in old:
            changes.append(f"{name}: starts in {mode.upper()} ({why})")
    os.makedirs(os.path.dirname(C.SKILL_STATUS_FILE), exist_ok=True)
    json.dump(new, open(C.SKILL_STATUS_FILE, "w"), indent=2)
    return new, changes


def team_sheet(status):
    lines = ["Skill team sheet:"]
    for name, s in status.items():
        lines.append(f"- {name}: {s['mode'].upper()} - {s['why']}")
    return "\n".join(lines)
