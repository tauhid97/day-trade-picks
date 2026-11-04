"""STUDY BOT - after the close, studies the past charts of every stock we watch.

PRACTICE ONLY: it writes down what it learns and tells Boss, but it never changes
a pick. For each "clue" a chart can show at the close (heavy volume, oversold,
quiet day, ...) it checks what usually happened the NEXT day: did the stock rise
1%+ or fall 1%+ from open to close (a day trader's day)?

To avoid fooling itself it learns on the older 60% of days and then checks on the
newer 40% it hasn't looked at. A clue only counts as a lesson if it works on both.
Charts can't see news, so many big moves will have no clue at all - that's normal.

Like a trader it also looks at clues TOGETHER (combos, e.g. "oversold + heavy volume") and,
from the nightly snapshots, at Reddit hype and good/bad news. A combo only counts if it
beats each of its parts. Hype and news clues need a few weeks of snapshots first.
"""
import itertools
import json
import os

import pandas as pd

from .. import config as C
from ..data import get_daily, load_universe

MOVE_PCT = 1.0       # "rose" / "fell" = next day's open-to-close move of 1%+ either way
LEARN_SHARE = 0.6    # learn on the older 60% of days, check on the newer 40%
MIN_CHECK = 100      # a clue needs this many examples in each part before we trust it
MIN_LIFT = 3.0       # and must beat normal by 3+ percentage points in both parts
SHOW = 5             # lessons shown per section in /lessons
HISTORY_CLUES = {"Reddit hype", "Lots of Reddit talk", "Good news", "Bad news"}


def _rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, float("nan")))


def clues(d, market_ok=None):
    """Yes/no clues for every day, using only that day's close and earlier."""
    c, v, rng = d["Close"], d["Volume"], d["High"] - d["Low"]
    chg = c.pct_change() * 100
    rsi = _rsi(c)
    out = {
        "Heavy volume (1.5x normal)": v > 1.5 * v.rolling(20).mean().shift(1),
        "Big up day (+3% or more)": chg >= 3,
        "Big down day (-3% or more)": chg <= -3,
        "Oversold (RSI under 30)": rsi < 30,
        "Overbought (RSI over 70)": rsi > 70,
        "In an uptrend (above its 50-day average)": c > c.rolling(50).mean(),
        "In a downtrend (below its 50-day average)": c < c.rolling(50).mean(),
        "Quiet day (smallest range in 7 days)": rng <= rng.rolling(7).min(),
        "Closed near its 20-day high": c >= 0.98 * d["High"].rolling(20).max(),
        "Closed near its 20-day low": c <= 1.02 * d["Low"].rolling(20).min(),
    }
    if market_ok is not None:
        out["Healthy market (SPY above its 20-day average)"] = market_ok.reindex(d.index).fillna(False).astype(bool)
    return pd.DataFrame(out)


def _short(name):
    return name.split(" (")[0]


def _history():
    """Clues from the nightly Hype / News snapshots: {clue: (rows with date+ticker, first date)}."""
    out = {}
    if os.path.exists(C.HYPE_HISTORY_FILE):
        h = pd.read_csv(C.HYPE_HISTORY_FILE)
        out["Reddit hype (2x more mentions)"] = h[h["level"] == "hype"]
        out["Lots of Reddit talk (20+ mentions)"] = h[h["level"].isin(["hype", "buzz"])]
        out = {k: (v, h["date"].min()) for k, v in out.items()}
    if os.path.exists(C.NEWS_HISTORY_FILE):
        n = pd.read_csv(C.NEWS_HISTORY_FILE)
        for k, m in [("Good news (headlines)", "good"), ("Bad news (headlines)", "bad")]:
            out[k] = (n[n["mood"] == m], n["date"].min())
    return out


def _table(daily):
    """One row per stock per day: every clue (yes/no), combos, and the next day's move."""
    spy = daily.get(C.MARKET_TICKER)
    market_ok = spy["Close"] > spy["Close"].rolling(20).mean() if spy is not None else None
    rows = []
    for t, d in daily.items():
        if t == C.MARKET_TICKER or len(d) < 60:
            continue
        f = clues(d, market_ok)
        f["next_move"] = (d["Close"].shift(-1) / d["Open"].shift(-1) - 1) * 100
        f["date"], f["ticker"] = pd.DatetimeIndex(d.index).tz_localize(None).normalize(), t
        rows.append(f.iloc[50:])
    if not rows:
        return pd.DataFrame(), {}
    table = pd.concat(rows, ignore_index=True)
    chart = [c for c in table.columns if c not in ("next_move", "date", "ticker")]
    since = {}
    for name, (h, first) in _history().items():
        keys = set(zip(pd.to_datetime(h["date"]), h["ticker"]))
        table[name] = [k in keys for k in zip(table["date"], table["ticker"])]
        since[name] = pd.Timestamp(first)
    extra = list(since)
    combos = {}
    for a, b in itertools.combinations(chart + extra, 2):
        if a in extra and b in extra:
            continue
        name = f"{_short(a)} + {_short(b)}"
        combos[name] = table[a] & table[b]
        if a in since or b in since:
            since[name] = max(since.get(a, since.get(b)), since.get(b, since.get(a)))
    return pd.concat([table, pd.DataFrame(combos)], axis=1), since


def _stats(part, col=None):
    g = part[part[col]] if col else part
    n = len(g)
    return {"n": n,
            "rise_pct": round((g["next_move"] >= MOVE_PCT).mean() * 100, 1) if n else 0.0,
            "fall_pct": round((g["next_move"] <= -MOVE_PCT).mean() * 100, 1) if n else 0.0,
            "avg_move": round(float(g["next_move"].mean()), 2) if n else 0.0}


def _split(known):
    days = sorted(known["date"].unique())
    if len(days) < 2:
        return None, days
    cut = days[int(len(days) * LEARN_SHARE)]
    return {"learn": known[known["date"] < cut], "check": known[known["date"] >= cut]}, days


def learn(table, since=None):
    """Learn on the older 60% of days, check on the newer 40%. Hype/news clues only use the days we have snapshots for."""
    since = since or {}
    known = table.dropna(subset=["next_move"])
    parts, days = _split(known)
    base = {k: _stats(p) for k, p in parts.items()}
    cache, out = {}, []
    for col in [c for c in known.columns if c not in ("next_move", "date", "ticker")]:
        if col in since:
            key = since[col]
            if key not in cache:
                cache[key] = _split(known[known["date"] >= key])[0]
            p = cache[key]
        else:
            p = parts
        if p is None:
            out.append({"name": col, "kind": None, "held": False, "base": base,
                        "learn": _stats(known.iloc[:0]), "check": _stats(known.iloc[:0])})
            continue
        b = base if p is parts else {k: _stats(v) for k, v in p.items()}
        s = {k: _stats(v, col) for k, v in p.items()}
        enough = all(s[k]["n"] >= MIN_CHECK for k in s)
        sides = [side for side, k2 in [("rise", "rise_pct"), ("fall", "fall_pct")]
                 if enough and all(s[k][k2] - b[k][k2] >= MIN_LIFT for k in s)]
        kind = "big move" if len(sides) == 2 else (sides[0] if sides else None)   # both = moves big, either way
        out.append({"name": col, "kind": kind, "held": kind is not None, "base": b, **s})
    for x in out:                                 # a combo must beat each of its parts, or it teaches nothing new
        if " + " in x["name"] and x["held"]:
            parts_ = [y for y in out if " + " not in y["name"] and _short(y["name"]) in x["name"].split(" + ")]
            if any(_pct(y["check"], x["kind"]) >= _pct(x["check"], x["kind"]) for y in parts_):
                x["kind"], x["held"] = None, False
    return base, out, len(days)


def todays_movers(daily):
    """Today's biggest riser and faller, and the clues their charts showed the day before."""
    spy = daily.get(C.MARKET_TICKER)
    market_ok = spy["Close"] > spy["Close"].rolling(20).mean() if spy is not None else None
    last = max(d.index[-1] for d in daily.values())
    moves = []
    for t, d in daily.items():
        if t == C.MARKET_TICKER or len(d) < 60 or d.index[-1] != last:
            continue
        f = clues(d, market_ok).iloc[-2]
        moves.append({"ticker": t, "chg": round((d["Close"].iloc[-1] / d["Close"].iloc[-2] - 1) * 100, 1),
                      "clues": [k for k, v in f.items() if bool(v)]})
    if not moves:
        return {}
    moves.sort(key=lambda m: m["chg"])
    return {"date": pd.Timestamp(last).strftime("%Y-%m-%d"), "riser": moves[-1], "faller": moves[0]}


def run(daily=None):
    """Study, save the notes, and return a short note for Boss's evening message."""
    if daily is None:
        daily = get_daily(load_universe(C.UNIVERSE_FILE) + [C.MARKET_TICKER], period="2y")
    table, since = _table(daily)
    if table.empty:
        return ""
    base, found, n_days = learn(table, since)
    notes = {"updated": pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d %H:%M"),
             "stocks": int(table["ticker"].nunique()), "days": n_days,
             "baseline": base, "clues": found, "movers": todays_movers(daily)}
    os.makedirs(os.path.dirname(C.STUDY_FILE), exist_ok=True)
    json.dump(notes, open(C.STUDY_FILE, "w"), indent=1)
    return note(notes)


def load():
    return json.load(open(C.STUDY_FILE)) if os.path.exists(C.STUDY_FILE) else {}


def _mover_line(word, m):
    why = ", ".join(c.split(" (")[0].lower() for c in m["clues"]) or "no special clues (maybe news)"
    return f"{word}: ${m['ticker']} {m['chg']:+.1f}%. The day before, its chart showed: {why}."


def _pct(s, kind):
    return s["rise_pct"] if kind == "rise" else s["fall_pct"] if kind == "fall" else s["rise_pct"] + s["fall_pct"]


def _lesson_line(x, base):
    word = {"rise": "rose", "fall": "fell", "big move": "moved"}[x["kind"]]
    way = " either way" if x["kind"] == "big move" else ""
    base = x.get("base") or base
    tag = "🧩 " if " + " in x["name"] else ""
    return (f"{tag}\"{x['name']}\" - next day it {word} 1%+{way} {_pct(x['check'], x['kind']):.0f}% of the time "
            f"(normal: {_pct(base['check'], x['kind']):.0f}%), on {x['check']['n']} unseen examples ✅")


def note(notes):
    lines = ["🔎 Study bot [practice - info only, never changes picks]",
             f"Studied the charts of {notes['stocks']} stocks over {notes['days']} days."]
    mv = notes.get("movers") or {}
    if mv:
        lines += [_mover_line("Biggest riser today", mv["riser"]), _mover_line("Biggest faller today", mv["faller"])]
    held = [x for x in notes["clues"] if x["held"]]
    for kind, word in [("rise", "rise"), ("fall", "drop")]:
        best = sorted([x for x in held if x["kind"] == kind], key=lambda x: -_pct(x["check"], kind))
        if best:
            lines.append(f"Best clue before a {word}: " + _lesson_line(best[0], notes["baseline"]))
    if not held:
        lines.append("No clue has passed the unseen-days check yet.")
    lines.append("Type /lessons to see everything it has learned.")
    return "\n".join(lines)


def lessons_text():
    notes = load()
    if not notes:
        return "The Study bot hasn't studied yet, Boss - it runs after the market closes."
    base = notes["baseline"]
    lines = [f"🔎 What the Study bot has learned (updated {notes['updated']} ET)",
             f"{notes['stocks']} stocks, {notes['days']} days of charts. Normal next day: "
             f"rose 1%+ {base['check']['rise_pct']:.0f}% of the time, fell 1%+ {base['check']['fall_pct']:.0f}%.", ""]
    for kind, title in [("rise", "📈 Clues that came before RISES:"), ("fall", "📉 Clues that came before DROPS:"),
                        ("big move", "🎢 Clues that came before BIG MOVES (up or down - no direction):")]:
        found = sorted([x for x in notes["clues"] if x["kind"] == kind], key=lambda x: -_pct(x["check"], kind))
        lines.append(title)
        lines += [f"- {_lesson_line(x, base)}" for x in found[:SHOW]] or ["- none passed the check yet"]
        if len(found) > SHOW:
            lines.append(f"- ...and {len(found) - SHOW} more")
        lines.append("")
    waiting = [x for x in notes["clues"] if " + " not in x["name"] and x["name"].split(" (")[0] in HISTORY_CLUES
               and min(x["learn"]["n"], x["check"]["n"]) < MIN_CHECK]
    if waiting:
        lines.append("⏳ Still collecting (hype & news snapshots, need " + str(MIN_CHECK) + " examples each half): "
                     + ", ".join(f"{_short(x['name'])} {x['learn']['n'] + x['check']['n']} so far" for x in waiting))
    lines.append(f"Didn't pass (no clear edge): {sum(not x['held'] for x in notes['clues'])} clues and combos.")
    lines.append("The edges are small (a few % more often than normal). These are patterns from the past, "
                 "not promises. Big moves often come from news, which charts can't see.")
    return "\n".join(lines)
