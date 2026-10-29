"""The daily routine: scan -> send signals -> grade after the close -> Guard check."""
import os

import pandas as pd

from . import config as C
from .bots import guard, timemachine
from .data import NY, get_daily, get_intraday, load_universe
from .engine import picks_for_day
from .notify import to_boss, to_community
from .simulate import simulate
from .skills import load_skills

PICK_COLS = ["date", "published_at", "mode", "ticker", "setup", "order_type", "entry", "stop",
             "target", "risk_pct", "reason", "status", "fill_price", "exit_price",
             "exit_time", "r_multiple", "pct_return"]

DISCLAIMER = ("Educational content only, not financial advice. Same picks for every member; "
              "not tailored to anyone. Trading involves risk of loss. Past results do not "
              "guarantee future results.")

ORDER_WORDS = {
    "buy_stop": "BUY STOP - only buy if the price climbs UP to the entry",
    "buy_limit": "BUY LIMIT - only buy if the price dips DOWN to the entry",
}


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


def _pick_lines(i, p):
    tgt = f"${p['target']:.2f}" if p.get("target") is not None and p["target"] == p["target"] else f"sell at {C.EXIT_TIME} ET"
    return [f"**{i}. ${p['ticker']} - {p['setup']}**",
            f"Order: {ORDER_WORDS[p['order_type']]}",
            f"Entry: ${p['entry']:.2f} | Stop: ${p['stop']:.2f} | Target: {tgt}",
            f"Risk: {p['risk_pct']:.1f}% | Why: {p['reason']}"] + ([p["tm"]] if p.get("tm") else []) + [""]


def format_post(live, ts, practice=None, weather_note=None, weather=None):
    lines = [f"**{C.BRAND_NAME} - {ts:%a %b %d, %Y}** (posted {ts:%I:%M %p} ET)", ""]
    if weather:
        lines += [f"Market weather: {weather.upper()} ({weather_note})", ""]
    if not live:
        lines += ["No live setups met our rules today. No trade is a valid trade.", ""]
    for i, p in enumerate(live, 1):
        lines += _pick_lines(i, p)
    if practice:
        lines += ["--- PRACTICE picks (skills on the bench - tracked, not for the community) ---", ""]
        for i, p in enumerate(practice, 1):
            lines += _pick_lines(i, p)
    lines += [f"Unfilled orders cancel at {C.LAST_ENTRY_TIME} ET. Open trades close at {C.EXIT_TIME} ET.",
              "", f"_{DISCLAIMER}_"]
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
    boss_text = format_post(live, ts, practice, note, w)
    os.makedirs("data", exist_ok=True)
    open(C.TODAY_POST_FILE, "w").write(boss_text)
    print(boss_text)
    rows = ([{"date": today.strftime("%Y-%m-%d"), "published_at": ts.isoformat(), "mode": "live", **p} for p in live] +
            [{"date": today.strftime("%Y-%m-%d"), "published_at": ts.isoformat(), "mode": "practice", **p} for p in practice])
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
                p["tm"] = timemachine.line(timemachine.odds(p, hist[p["ticker"]], ts))
            except Exception as e:
                print("Time Machine failed for", p["ticker"], e)


def grade():
    df = load_picks()
    now = now_ny()
    graded = []
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
    status, changes = guard.run(df, now.strftime("%Y-%m-%d"))
    if graded:
        to_boss(format_results(graded) + ("\n\nGuard bot: " + "\n".join(changes) if changes else ""))
        live_only = [g for g in graded if g.get("mode", "live") == "live"]
        if live_only:
            to_community(format_results(live_only))
    elif changes:
        to_boss("Guard bot update:\n" + "\n".join(changes))
    return graded


def format_results(graded):
    word = {"target": "TARGET HIT", "stop": "STOPPED OUT", "eod": "SOLD AT CLOSE", "no_fill": "NEVER TRIGGERED"}
    lines = []
    for day in sorted({g["date"] for g in graded}):
        rows = [g for g in graded if g["date"] == day]
        lines += [f"**{C.BRAND_NAME} - results for {day}**", ""]
        for g in rows:
            r = f"{g['r_multiple']:+.2f}R ({g['pct_return']:+.2f}%)" if g["status"] != "no_fill" else "no trade"
            tag = " [practice]" if g.get("mode") == "practice" else ""
            lines.append(f"${g['ticker']} {g['setup']}{tag}: {word[g['status']]} - {r}")
        live = [g for g in rows if g.get("mode", "live") == "live"]
        lines += [f"Live total: {sum(g['r_multiple'] for g in live):+.2f}R", ""]
    lines.append("Every pick, win or lose, is on the public track-record page.")
    return "\n".join(lines)
