"""Practice on the past: replay the last ~2 months of 5-minute data.

Yahoo only gives ~60 days of 5-min history - treat this as a sanity check,
not proof. Each skill is tested on its own (top picks per day, per skill).

The 2-year test (long_test) uses free hourly prices instead: rougher, but much longer.
It grades every skill twice: the normal way, and with smart selling (half at +1R).
"""
import pandas as pd

from . import config as C
from .bots import breadth
from .bots import weather as weather_bot
from .data import get_daily, get_intraday, hourly_to_5min, load_universe
from .engine import build_contexts, ideas
from .setups import rank_and_cap
from .simulate import simulate
from .skills import load_skills

PUBLISH_DELAY_MIN = 5
SMART_HALF_R = 1.0         # smart selling: sell half once the trade is up this many R


def load_data():
    tickers = load_universe(C.UNIVERSE_FILE) + [C.MARKET_TICKER]
    print(f"Downloading data for {len(tickers)} tickers...")
    intraday = get_intraday(tickers, period="60d", interval="5m")
    daily = get_daily(list(intraday), period="2y")
    return intraday, daily


def prepare(intraday, daily):
    """Pre-compute each day's stock snapshots once, so skills can be re-tested quickly."""
    all_days = sorted({d for b in intraday.values() for d in b.index.normalize().unique()})
    hh, mm = map(int, C.SCAN_TIME.split(":"))
    return [_day(day, hh, mm, intraday, daily) for day in all_days[C.RVOL_LOOKBACK_DAYS:]]


def _day(day, hh, mm, intraday, daily):
    scan_ts = day + pd.Timedelta(hours=hh, minutes=mm)
    w, _ = weather_bot.check(day, scan_ts, intraday, daily)
    return {"day": day, "publish_ts": scan_ts + pd.Timedelta(minutes=PUBLISH_DELAY_MIN),
            "ctxs": build_contexts(day, scan_ts, intraday, daily), "weather": w,
            "breadth": breadth.check(day)[0]}


def trades_for(skill, params, prepared, intraday, smart=False):
    trades = []
    for d in prepared:
        picks = rank_and_cap(ideas(d["ctxs"], skill, params, d["weather"]), total=C.MAX_PICKS_PER_SETUP)
        for p in picks:
            if smart:
                p = {**p, "half_at_r": SMART_HALF_R}
            bars = intraday[p["ticker"]]
            res = simulate(p, bars[bars.index >= d["publish_ts"]])
            if res["status"] == "open":          # data ends before the hold does - can't grade it
                continue
            trades.append({"date": d["day"].strftime("%Y-%m-%d"), "weather": d["weather"],
                           "breadth": d["breadth"], **p, **res})
    return trades


def summarize(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, g in [("ALL SETUPS", trades)] + list(trades.groupby("setup")):
        f = g[g["status"] != "no_fill"]
        wins, losses = f[f["r_multiple"] > 0], f[f["r_multiple"] <= 0]
        cum = f.sort_values("date")["r_multiple"].cumsum()
        dd = float((cum - cum.cummax().clip(lower=0)).min()) if len(cum) else 0.0
        rows.append({
            "setup": name, "picks": len(g), "filled": len(f),
            "win_rate_pct": round(len(wins) / len(f) * 100, 1) if len(f) else 0,
            "avg_R": round(f["r_multiple"].mean(), 3) if len(f) else 0,
            "total_R": round(f["r_multiple"].sum(), 2),
            "avg_pct": round(f["pct_return"].mean(), 3) if len(f) else 0,
            "profit_factor": round(wins["r_multiple"].sum() / abs(losses["r_multiple"].sum()), 2)
            if len(losses) and losses["r_multiple"].sum() != 0 else None,
            "max_drawdown_R": round(dd, 2),
        })
    return pd.DataFrame(rows)


def by_breadth(trades: pd.DataFrame) -> list:
    """Practice check: do picks do better when more stocks are in uptrends?"""
    f = trades[trades["status"] != "no_fill"]
    order = ["strong", "healthy", "neutral", "weak", "very weak", "unknown"]
    out = []
    for z in order:
        g = f[f["breadth"] == z]
        if len(g):
            out.append(f"- {z}: {len(g)} trades, win {(g['r_multiple'] > 0).mean() * 100:.0f}%, avg {g['r_multiple'].mean():+.2f}R")
    return out


def run(intraday=None, daily=None):
    if intraday is None:
        intraday, daily = load_data()
    prepared = prepare(intraday, daily)
    trades = []
    for sk in load_skills():
        trades += trades_for(sk, sk["params"], prepared, intraday)
        print(f"tested skill: {sk['name']}")
    trades = pd.DataFrame(trades)
    if trades.empty:
        print("No trades generated.")
        return trades, pd.DataFrame(), prepared, intraday
    summary = summarize(trades)
    trades.to_csv(C.BACKTEST_TRADES_FILE, index=False)
    summary.to_csv(C.BACKTEST_SUMMARY_FILE, index=False)
    print(summary.to_string(index=False))
    return trades, summary, prepared, intraday


def long_test(hourly=None, daily=None):
    """2-year practice test on hourly prices: every skill, normal vs smart selling."""
    if hourly is None:
        tickers = load_universe(C.UNIVERSE_FILE) + [C.MARKET_TICKER]
        print(f"Downloading 2 years of hourly prices for {len(tickers)} tickers...")
        hourly = get_intraday(tickers, period="729d", interval="1h")
        daily = get_daily(list(hourly), period="5y")
    bars = {t: hourly_to_5min(b) for t, b in hourly.items()}
    days = sorted({d for b in bars.values() for d in b.index.normalize().unique()})
    hh, mm = map(int, C.SCAN_TIME.split(":"))
    skills, normal, smart = load_skills(), [], []
    for day in days[C.RVOL_LOOKBACK_DAYS:]:          # one day at a time, so memory stays small
        lo, hi = day - pd.Timedelta(days=C.RVOL_LOOKBACK_DAYS * 2 + 5), day + pd.Timedelta(days=8)
        win = {t: b.loc[lo:hi] for t, b in bars.items()}
        dl = day.tz_localize(None)
        dwin = {t: d.loc[dl - pd.Timedelta(days=400):dl + pd.Timedelta(days=8)] for t, d in daily.items()}
        prepared = [_day(day, hh, mm, win, dwin)]
        for sk in skills:
            normal += trades_for(sk, sk["params"], prepared, win)
            smart += trades_for(sk, sk["params"], prepared, win, smart=True)
    if not normal:
        return pd.DataFrame(columns=["setup", "trades", "win_pct", "total_R", "smart_win_pct", "smart_total_R"])
    a, b = summarize(pd.DataFrame(normal)), summarize(pd.DataFrame(smart))
    out = pd.DataFrame({"setup": a["setup"], "trades": a["filled"], "win_pct": a["win_rate_pct"], "total_R": a["total_R"]})
    out = out.merge(b[["setup", "win_rate_pct", "total_R"]].rename(
        columns={"win_rate_pct": "smart_win_pct", "total_R": "smart_total_R"}), on="setup", how="left")
    out.attrs["days"] = len(days)
    out.to_csv(C.LONG_TEST_FILE, index=False)
    return out


def long_text(summary):
    from . import plain
    if not len(summary):
        return "2-year practice test: not enough hourly prices this week - skipped."
    days = summary.attrs.get("days")
    lines = [f"2-year practice test [hourly prices, rough - hypothetical, not real trades{f', {days} days' if days else ''}]:",
             "Normal selling vs smart sell (sell half when up $10, then the Safety price moves up to the Buy price):"]
    for _, r in summary.iterrows():
        name = "All skills" if r["setup"] == "ALL SETUPS" else plain.nick(r["setup"])
        better = " ✅ smart sell better" if r["smart_total_R"] > r["total_R"] else ""
        n = int(r["trades"])
        lines.append(f"- {name}: {n} trade{'' if n == 1 else 's'} | normal: won {r['win_pct']:.0f}%, total {plain.money(r['total_R'])} "
                     f"| smart sell: won {r['smart_win_pct']:.0f}%, total {plain.money(r['smart_total_R'])}{better}")
    return "\n".join(lines)
