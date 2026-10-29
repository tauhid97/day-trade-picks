"""Practice on the past: replay the last ~2 months of 5-minute data.

Yahoo only gives ~60 days of 5-min history - treat this as a sanity check,
not proof. Each skill is tested on its own (top picks per day, per skill).
"""
import pandas as pd

from . import config as C
from .bots import weather as weather_bot
from .data import get_daily, get_intraday, load_universe
from .engine import build_contexts, ideas
from .setups import rank_and_cap
from .simulate import simulate
from .skills import load_skills

PUBLISH_DELAY_MIN = 5


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
    out = []
    for day in all_days[C.RVOL_LOOKBACK_DAYS:]:
        scan_ts = day + pd.Timedelta(hours=hh, minutes=mm)
        w, _ = weather_bot.check(day, scan_ts, intraday, daily)
        out.append({"day": day, "publish_ts": scan_ts + pd.Timedelta(minutes=PUBLISH_DELAY_MIN),
                    "ctxs": build_contexts(day, scan_ts, intraday, daily), "weather": w})
    return out


def trades_for(skill, params, prepared, intraday):
    trades = []
    for d in prepared:
        picks = rank_and_cap(ideas(d["ctxs"], skill, params, d["weather"]), total=C.MAX_PICKS_PER_SETUP)
        for p in picks:
            bars = intraday[p["ticker"]]
            after = bars[(bars.index.normalize() == d["day"]) & (bars.index >= d["publish_ts"])]
            trades.append({"date": d["day"].strftime("%Y-%m-%d"), "weather": d["weather"], **p, **simulate(p, after)})
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
