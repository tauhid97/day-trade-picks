"""WEATHER BOT - checks the mood of the whole market (using SPY) before trading.

sunny  = market is up today AND above its 20-day average -> all skills allowed
cloudy = mixed -> most skills allowed
stormy = market down 1%+ today -> only skills built for storms (e.g. Oversold Bounce)
"""
from .. import config as C


def check(day, scan_ts, intraday, daily):
    t = C.MARKET_TICKER
    if t not in intraday or t not in daily:
        return "cloudy", "Market data unavailable - assuming cloudy"
    b = intraday[t]
    b = b[(b.index.normalize() == day) & (b.index < scan_ts)]
    d = daily[t]
    d = d[d.index < day.tz_localize(None)]
    if b.empty or len(d) < 20:
        return "cloudy", "Not enough market data - assuming cloudy"
    last, prev = float(b["Close"].iloc[-1]), float(d["Close"].iloc[-1])
    sma20 = float(d["Close"].tail(20).mean())
    chg = (last / prev - 1) * 100
    above = last > sma20
    if chg <= -1.0:
        w = "stormy"
    elif chg >= 0 and above:
        w = "sunny"
    else:
        w = "cloudy"
    return w, f"SPY {chg:+.2f}% today, {'above' if above else 'below'} its 20-day average"
