"""COMMANDS - answers Boss when he types to the bot on Telegram (same idea as Crypto Boss).

A small schedule wakes this up every ~15 minutes, so answers can take that long.
It only ever answers Boss's own chat (TELEGRAM_CHAT_ID); anyone else is ignored.

  /status       am I awake, last scan, how many skills are live / practice
  /picks        the latest picks and how they did
  /scoreboard   win/loss scorecard, all-time and per skill
  /skills       which skills are LIVE and which are PRACTICE
  /lessons      what the Study bot has learned from past charts
  /watchlist    beaten-down stocks + who's holding up on red days
  anything else this help message
"""
import json
import os

import pandas as pd
import requests

from . import plain
from .bots import guard, study, watchlist
from .data import NY
from .live import load_picks
from .notify import to_boss

DONE = ["target", "stop", "eod", "no_fill"]

HELP = ("Hi Boss! I check for messages about every 15 minutes, so my answers can take that long.\n"
        "Things you can ask me:\n"
        "/status - am I working\n"
        "/picks - the latest picks and how they did\n"
        "/scoreboard - wins and losses so far\n"
        "/skills - which skills are live and which are practice\n"
        "/lessons - what the Study bot learned from past charts\n"
        "/watchlist - beaten-down stocks, and who's strong on red days")


def get_updates(offset):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    if not tok:
        return []
    params = {"timeout": 0, "allowed_updates": json.dumps(["message"])}
    if offset is not None:
        params["offset"] = offset
    r = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", params=params, timeout=20)
    return r.json().get("result", []) if r.ok else []


def status_text(df, status):
    t = pd.Timestamp.now(tz=NY)
    live = sum(s["mode"] == "live" for s in status.values())
    last = df["date"].max() if len(df) else "none yet"
    return "\n".join([
        f"I'm awake, Boss! Checked at {t:%I:%M %p} ET ({t:%a %b %d}).".replace(" 0", " "),
        f"Last picks made on: {last}.",
        f"Skills: {live} live, {len(status) - live} practice.",
        "Picks arrive about 10:40 AM ET, results after the close. No real money until the record looks good for 2-3 months."])


def picks_text(df):
    if not len(df):
        return "No picks yet, Boss."
    day = df["date"].max()
    rows = df[df["date"] == day]
    lines = [f"Picks from {day}:", ""]
    for mode in ["live", "practice"]:
        part = rows[rows["mode"].fillna("live") == mode]
        if not len(part):
            continue
        lines += [f"--- {mode.upper()} ---"]
        for i, (_, p) in enumerate(part.iterrows(), 1):
            lines += plain.pick_lines(i, p.to_dict())[:-1]
            st = p["status"]
            if st in DONE or st == "open":
                r = f" → {plain.money(float(p['r_multiple']))}" if st in plain.FINISHED else ""
                lines.append(f"Result: {plain.result_word(p.to_dict())}{r}")
            else:
                lines.append("Result: not graded yet (comes after the close)")
            lines.append("")
    return "\n".join(lines).rstrip()


def scoreboard_text(df):
    done = df[df["status"].isin(DONE)] if len(df) else df
    if not len(done):
        return "No graded trades yet, Boss."
    mode = done["mode"].fillna("live")
    lines = [f"📈 All-time scorecard (real picks): {plain.scorecard(done[mode == 'live'].to_dict('records'))}",
             f"🧪 Practice picks: {plain.scorecard(done[mode == 'practice'].to_dict('records'))}", "", "By skill:"]
    for setup, g in done.groupby("setup"):
        lines.append(f"- {plain.nick(setup)}: {plain.scorecard(g.to_dict('records'))}")
    lines += ["", f"(Money shown as if you risked ${plain.RISK_DOLLARS} on each trade)"]
    return "\n".join(lines)


def skills_text(status):
    if not status:
        return "The skill team list isn't ready yet - it fills in after the first evening results."
    lines = ["Skill team sheet:"]
    for name, s in sorted(status.items(), key=lambda kv: kv[1]["mode"] != "live"):
        lines.append(f"- {plain.nick(name)}: {s['mode'].upper()}")
    return "\n".join(lines)


def answer(text, df, status):
    word = text.strip().split()[0].split("@")[0].lower() if (text or "").strip() else ""
    if word == "/status":
        return status_text(df, status)
    if word == "/picks":
        return picks_text(df)
    if word == "/scoreboard":
        return scoreboard_text(df)
    if word == "/skills":
        return skills_text(status)
    if word == "/lessons":
        return study.lessons_text()
    if word == "/watchlist":
        return watchlist.text()
    return HELP


def handle():
    """Answer any new messages, then tell Telegram they're read so nothing is answered twice."""
    boss = str(os.getenv("TELEGRAM_CHAT_ID") or "")
    updates = get_updates(None)
    if not updates:
        return
    df, status = load_picks(), guard.load_status()
    for u in sorted(updates, key=lambda u: u["update_id"]):
        m = u.get("message") or {}
        if boss and str((m.get("chat") or {}).get("id")) == boss and "text" in m:
            to_boss(answer(m["text"], df, status))
    get_updates(max(u["update_id"] for u in updates) + 1)
