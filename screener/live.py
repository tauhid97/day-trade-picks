"""The daily routine: scan -> send signals -> grade after the close -> Guard check."""
import os

import pandas as pd

from . import config as C
from . import plain
from .bots import breadth, guard, timemachine
from .data import NY, get_daily, get_intraday, load_universe
from .engine import picks_for_day
from .notify import to_boss, to_community
from .simulate import simulate
from .skills import load_skills

PICK_COLS = ["date", "published_at", "mode", "ticker", "setup", "order_type", "entry", "stop",
             "target", "risk_pct", "reason", "status", "fill_price", "exit_price",
             "exit_time", "r_multiple", "pct_return", "breadth"]

DISCLAIMER = ("Educational content only, not financial advice. Same picks for every member; "
              "not tailored to anyone. Trading involves risk of loss. Past results do not "
              "guarantee future results.")


def now_ny():
    return pd.Timestamp.now(tz=NY)


def load_picks():
    if os.path.exists(C.PICKS_FILE):
        df = pd.read_csv(C.PICKS_FILE, dtype={"status": "object", "exit_time": "object", "mode": "object"})
        if "mode" not in df:
            df["mode"] = "live"
        return df
    return pd.DataFrame(columns=PICK_COLS)


def save_picks(df):
    os.makedirs(os.path.dirname(C.PICKS_FILE), exist_ok=True)
    for c in PICK_COLS:
        if c not in df:
            df[c] = None
    df[PICK_COLS].to_csv(C.PICKS_FILE, index=False)


def format_post(live, ts, practice=None, weather_note=None, weather=None, breadth_note=None, breadth_zone=None):
    lines = [f"**{C.BRAND_NAME} - {ts:%a %b %d, %Y}** (sent {ts:%I:%M %p} ET)", ""]
    if weather:
        lines += [plain.weather_line(weather, weather_note), ""]
    if breadth_zone:
        lines += [plain.breadth_line(breadth_zone, breadth_note), ""]
    if not live:
        lines += ["No real picks today - nothing met our rules. No trade is a good trade.", ""]
    for i, p in enumerate(live, 1):
        lines += plain.pick_lines(i, p)
    if practice:
        lines += ["--- PRACTICE picks (skills still being tested - just watch, don't trade these) ---", ""]
        for i, p in enumerate(practice, 1):
            lines += plain.pick_lines(i, p)
    lines += plain.footer() + ["", f"_{DISCLAIMER}_"]
    return "\n".join(lines)


def scan(force=False):
    ts = now_ny().floor("min")
    hm = ts.strftime("%H:%M")
    if not force and (ts.weekday() >= 5 or not (C.SCAN_TIME <= hm <= C.SCAN_WINDOW_END)):
        print(f"Outside scan window ({hm} ET). Skipping.")
        return
    today = ts.normalize()
    picks_df = load_picks()
    if not force and (picks_df["date"] == today.strftime("%Y-%m-%d")).any():
        print("Already scanned today. Skipping.")
        return
    tickers = load_universe(C.UNIVERSE_FILE) + [C.MARKET_TICKER]
    intraday = get_intraday(tickers, period="20d", interval="5m")
    if not intraday:
        print("No data returned (market closed or data source down).")
        to_boss("Boss, I couldn't get market data today, so no picks were made.")
        return
    if max(b.index.max() for b in intraday.values()).normalize() != today:
        print("Market not open today (holiday?). Skipping.")
        return
    daily = get_daily(list(intraday), period="1y")
    live, practice, w, note = picks_for_day(today, ts, intraday, daily, load_skills(), guard.modes())
    add_time_machine(live + practice, ts)
    bz, bnote = breadth.check(today)
    boss_text = format_post(live, ts, practice, note, w, bnote, bz)
    os.makedirs("data", exist_ok=True)
    open(C.TODAY_POST_FILE, "w").write(boss_text)
    print(boss_text)
    rows = ([{"date": today.strftime("%Y-%m-%d"), "published_at": ts.isoformat(), "mode": "live", "breadth": bz, **p} for p in live] +
            [{"date": today.strftime("%Y-%m-%d"), "published_at": ts.isoformat(), "mode": "practice", "breadth": bz, **p} for p in practice])
    if rows:
        new = pd.DataFrame(rows).drop(columns=["score", "tm"], errors="ignore")
        picks_df = pd.concat([picks_df, new], ignore_index=True) if len(picks_df) else new
        save_picks(picks_df)
    to_boss(boss_text)
    to_community(format_post([{k: v for k, v in p.items() if k != "tm"} for p in live], ts))


def add_time_machine(picks, ts):
    if not picks:
        return
    try:
        hist = get_intraday(sorted({p["ticker"] for p in picks}), period="60d", interval="5m")
    except Exception as e:
        print("Time Machine skipped:", e)
        return
    for p in picks:
        if p["ticker"] in hist:
            try:
                p["tm"] = plain.luck(timemachine.odds(p, hist[p["ticker"]], ts))
            except Exception as e:
                print("Time Machine failed for", p["ticker"], e)


def grade():
    df = load_picks()
    now = now_ny()
    graded, waiting = [], 0
    if len(df):
        todo = df[df["status"].isna() | (df["status"] == "")]
        todo = todo[[pd.Timestamp(d).tz_localize(NY) + pd.Timedelta(hours=16, minutes=5) < now for d in todo["date"]]]
        if len(todo):
            intraday = get_intraday(sorted(todo["ticker"].unique()), period="30d", interval="5m")
            for i, row in todo.iterrows():
                bars = intraday.get(row["ticker"])
                if bars is None:
                    continue
                pub = pd.Timestamp(row["published_at"])
                after = bars[(bars.index.normalize() == pub.normalize()) & (bars.index >= pub)]
                if after.empty:
                    continue
                res = simulate(row.to_dict(), after)
                for k, v in res.items():
                    df.at[i, k] = v
                graded.append({**row.to_dict(), **res})
            save_picks(df)
            waiting = len(todo) - len(graded)
    status, changes = guard.run(df, now.strftime("%Y-%m-%d"))
    guard_note = "\n\nGuard bot: " + "\n".join(changes) if changes else ""
    done = df[df["status"].isin(["target", "stop", "eod"])] if len(df) else df
    all_live = done[done["mode"].fillna("live") == "live"].to_dict("records") if len(done) else []
    if graded:
        to_boss(format_results(graded) + "\n\n" + plain.scoreboard(graded, all_live) + guard_note)
        live_only = [g for g in graded if g.get("mode", "live") == "live"]
        if live_only:
            to_community(format_results(live_only))
    else:
        to_boss(plain.quiet_day(waiting, all_live) + guard_note)
    return graded


def format_results(graded):
    return plain.results(graded)
