"""WAKE-UP LIST - Boss's /wakeup command: which beaten-down stocks have busy volume right now.

INFO ONLY (practice): it never buys anything. Yahoo's free data is about 15 minutes late.
Volume is compared with the stock's normal volume by the same time of day (like the scout does).
"""
import pandas as pd

from .. import config as C
from . import watchlist

MIN_RVOL = 1.5
TOP_N = 5
FINVIZ = ("https://finviz.com/screener.ashx?v=111&f=sh_avgvol_o1000,sh_price_o5,sh_relvol_o1.5,"
          "ta_change_u,ta_highlow52w_b20h&o=-relativevolume")


def lines(ctxs, when):
    """ctxs already have beaten_rank / below_high_pct (engine.add_beaten_rank)."""
    head = f"🔔 Wake-up list [practice, info only] - {when:%a %b %d, %I:%M %p} ET (data ~15 min late)"
    if not ctxs:
        return "\n".join([head, "Too early or the market is closed, Boss - try after 10 AM ET on a weekday.",
                          "", f"Free live screener (all US stocks): {FINVIZ}"])
    ranked = sorted((c for c in ctxs if c.beaten_rank), key=lambda c: c.beaten_rank)
    out = [head, "Top beaten-down stocks, and how busy their volume is vs normal by now:"]
    for c in ranked[:TOP_N]:
        flag = " ⚡ volume waking up!" if c.rvol >= MIN_RVOL else ""
        out.append(f"- ${c.ticker}: {c.below_high_pct:.0f}% below its high, today {c.day_chg_pct:+.1f}%, "
                   f"volume {c.rvol:.1f}x{flag}")
    if not ranked:
        out.append("- none of our stocks are 20%+ below their 6-month high right now")
    more = [c for c in ranked[TOP_N:] if c.rvol >= MIN_RVOL][:5]
    if more:
        out += ["", "Other beaten-down stocks with busy volume:"]
        out += [f"- ${c.ticker}: {c.below_high_pct:.0f}% below, today {c.day_chg_pct:+.1f}%, volume {c.rvol:.1f}x" for c in more]
    out += ["", "\"Waking up\" on a top-5 stock = what the Volume Wake-Up practice skill looks for at the morning scan.",
            f"Free live screener (all US stocks): {FINVIZ}"]
    return "\n".join(out)


def text(now=None):
    from .. import engine
    from ..data import NY, get_daily, get_intraday, load_universe
    now = (now or pd.Timestamp.now(tz=NY)).floor("min")
    try:
        daily = get_daily(load_universe(C.UNIVERSE_FILE), period="1y")
        cands = [t for t, d in daily.items() if t != C.MARKET_TICKER and len(d) > 30 and
                 float(d["Close"].iloc[-1]) <= float(d["High"].iloc[-watchlist.LOOKBACK_DAYS:].max()) * 0.85]
        intraday = get_intraday(cands, period="20d", interval="5m") if cands else {}
        if not intraday:
            return lines([], now)
        day = max(b.index.max() for b in intraday.values()).normalize()
        ts = min(now, day + pd.Timedelta(hours=16))
        return lines(engine.build_contexts(day, ts, intraday, daily), ts)
    except Exception as e:
        print("Wake-up list failed:", e)
        return f"Sorry Boss, I couldn't get live data just now. Free live screener: {FINVIZ}"
