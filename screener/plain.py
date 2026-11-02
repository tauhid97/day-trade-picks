"""PLAIN ENGLISH - turns the bot's numbers into simple messages for Boss.

Buy / Safety / Win prices instead of entry / stop / target, nicknames for each
skill, and results in dollars "if you risked $10" instead of R.
"""
from . import config as C

RISK_DOLLARS = 10   # every result is shown as if you risked this much per trade

NICKNAMES = {
    "VWAP Pullback": "Dip Buy",
    "Oversold Bounce": "Bounce Back",
    "Gap & Go": "Morning Rocket",
    "ORB Stocks in Play": "Crowd Breakout",
    "Bull Flag": "Rest & Rocket",
    "20-Day Breakout": "New Monthly High",
    "MA20 Reclaim": "Back Above Normal",
    "NR7 Breakout": "Tight Spring",
    "Relative Strength": "Strong Kid",
    "Downtrend Reversal": "Wake Up Rally",
}

BUY_WORDS = {
    "buy_stop": "only if the price climbs UP to",
    "buy_limit": "only if the price dips DOWN to",
}

MOOD = {
    "sunny": ("☀️ SUNNY", "good day to trade"),
    "cloudy": ("⛅ CLOUDY", "mixed day, be picky"),
    "stormy": ("⛈️ STORMY", "market is falling, only Bounce Back plays"),
}

RESULT_WORDS = {
    "target": "✅ hit the Win price",
    "stop": "❌ hit the Safety price",
    "eod": "⏰ sold at the end of the day",
    "no_fill": "⏸️ price never reached the Buy price - no trade",
}


def nick(setup):
    n = NICKNAMES.get(setup)
    return f"{n} ({setup})" if n else setup


def money(r):
    d = r * RISK_DOLLARS
    return f"{'+' if d >= 0 else '-'}${abs(d):.2f}"


def _has_target(p):
    return p.get("target") is not None and p["target"] == p["target"]


def pick_lines(i, p):
    lines = [f"**{i}. ${p['ticker']} - {nick(p['setup'])}**",
             f"Buy: {BUY_WORDS[p['order_type']]} ${p['entry']:.2f}",
             f"Safety (sell if it falls to): ${p['stop']:.2f}"]
    if _has_target(p):
        win_r = (p["target"] - p["entry"]) / (p["entry"] - p["stop"])
        lines += [f"Win (sell if it rises to): ${p['target']:.2f}",
                  f"If you risked ${RISK_DOLLARS}: lose {money(-1)[1:]} at Safety, win {money(win_r)} at Win."]
    else:
        lines += [f"Win: no set price - sell at {clock(C.EXIT_TIME)} ET",
                  f"If you risked ${RISK_DOLLARS}: lose {money(-1)[1:]} at Safety."]
    lines.append(f"Why: {p['reason']}")
    return lines + ([p["tm"]] if p.get("tm") else []) + [""]


def luck(o):
    if not o:
        return "Luck check: not enough history for this stock."
    return (f"Luck check ({o['sessions']} past days replayed 2,000 times): the Buy happens {o['trigger_pct']}% of the time. "
            f"Win first {o['target_pct']}%, Safety first {o['stop_pct']}%. "
            f"Average {money(o['avg_r'])} per ${RISK_DOLLARS} risked. A simulation, not a promise.")


def weather_line(w, note):
    word, meaning = MOOD.get(w, (w.upper(), ""))
    return f"Market mood: {word} - {meaning} ({note})"


def breadth_line(zone, note):
    return f"How many stocks are rising [practice, info only]: {zone.upper()} ({note})"


def clock(hm):
    h, m = map(int, hm.split(":"))
    return f"{(h - 1) % 12 + 1}:{m:02d} {'PM' if h >= 12 else 'AM'}"


def footer():
    return [f"Not bought by {clock(C.LAST_ENTRY_TIME)} ET? Forget it. Still holding at {clock(C.EXIT_TIME)} ET? Sell."]


def scorecard(rows):
    """Simple count, e.g. '3 trades. 1 win. 2 losses. 33% wins. Total +$8.00'. Picks that never bought don't count."""
    rs = [float(g["r_multiple"]) for g in rows if g["status"] != "no_fill"]
    if not rs:
        return "0 trades (no Buy prices were reached)"
    wins = sum(r > 0 for r in rs)
    losses = len(rs) - wins
    return (f"{len(rs)} trade{'s' if len(rs) != 1 else ''}. {wins} win{'s' if wins != 1 else ''}. "
            f"{losses} loss{'es' if losses != 1 else ''}. {round(wins / len(rs) * 100)}% wins. Total {money(sum(rs))}")


def scoreboard(today, all_live):
    """The daily scorecard block for Boss's results message."""
    live = [g for g in today if g.get("mode", "live") == "live"]
    practice = [g for g in today if g.get("mode") == "practice"]
    lines = ["📊 Today's scorecard", f"Real picks: {scorecard(live)}"]
    if practice:
        lines.append(f"Practice picks: {scorecard(practice)}")
    lines += ["", f"📈 All-time scorecard (real picks): {scorecard(all_live)}",
              f"(Money shown as if you risked ${RISK_DOLLARS} on each trade)"]
    return "\n".join(lines)


def quiet_day(waiting, all_live):
    """Evening message when there was nothing to grade."""
    if waiting:
        first = (f"Boss, I couldn't get prices to grade {waiting} pick{'s' if waiting != 1 else ''} today. "
                 "I'll try again tomorrow evening.")
    else:
        first = "Boss, no picks were made today, so there's nothing to grade. No trade is a good trade."
    return (f"**{C.BRAND_NAME} - evening update**\n\n{first}\n\n"
            f"📈 All-time scorecard (real picks): {scorecard(all_live)}")


def results(graded):
    lines = []
    for day in sorted({g["date"] for g in graded}):
        rows = [g for g in graded if g["date"] == day]
        lines += [f"**{C.BRAND_NAME} - results for {day}**", ""]
        for g in rows:
            tag = " [practice]" if g.get("mode") == "practice" else ""
            r = f" → {money(g['r_multiple'])}" if g["status"] != "no_fill" else ""
            lines.append(f"${g['ticker']} {nick(g['setup'])}{tag}: {RESULT_WORDS[g['status']]}{r}")
        live = [g for g in rows if g.get("mode", "live") == "live"]
        lines += ["", f"Real picks total: {money(sum(g['r_multiple'] for g in live))} (if you risked ${RISK_DOLLARS} on each)", ""]
    lines.append("Every pick, win or lose, is on the public scoreboard.")
    return "\n".join(lines)
