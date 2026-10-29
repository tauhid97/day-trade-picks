"""Shared building blocks for skills: the market snapshot (Context) and pick helpers."""
import pandas as pd

from . import config as C
from .indicators import atr, rsi, vwap


class Context:
    """Everything a skill may look at for one stock, using only data before the scan time."""

    def __init__(self, ticker, bars, daily, avg_cum_vol):
        self.ticker, self.bars, self.daily = ticker, bars, daily
        b, d = bars, daily
        self.prev_close = float(d["Close"].iloc[-1])
        self.open = float(b["Open"].iloc[0])
        self.last = float(b["Close"].iloc[-1])
        self.hod = float(b["High"].max())
        self.lod = float(b["Low"].min())
        self.gap_pct = (self.open / self.prev_close - 1) * 100
        self.day_chg_pct = (self.last / self.prev_close - 1) * 100
        self.rvol = float(b["Volume"].sum()) / avg_cum_vol if avg_cum_vol > 0 else 0.0
        self.vwap_series = vwap(b)
        self.vwap = float(self.vwap_series.iloc[-1])
        self.atr = atr(d)
        self.avg_dollar_vol = float((d["Close"] * d["Volume"]).tail(20).mean())
        orb = b[b.index.strftime("%H:%M") < C.OPENING_RANGE_END]
        self.or_high = float(orb["High"].max()) if len(orb) else self.hod
        self.or_low = float(orb["Low"].min()) if len(orb) else self.lod
        self.or_open = float(orb["Open"].iloc[0]) if len(orb) else self.open
        self.or_close = float(orb["Close"].iloc[-1]) if len(orb) else self.last
        closes = pd.concat([d["Close"], pd.Series([self.last])], ignore_index=True)
        self.rsi = rsi(closes)


def make_pick(ctx, setup, idea):
    """Turn a skill's idea into a checked pick. idea = dict(order_type, entry, stop, target_r, score, reason)."""
    entry, stop = round(idea["entry"], 2), round(idea["stop"], 2)
    risk = entry - stop
    if risk <= 0 or not (C.MIN_RISK_PCT <= risk / entry * 100 <= C.MAX_RISK_PCT):
        return None
    tr = idea.get("target_r")
    return {
        "ticker": ctx.ticker, "setup": setup, "order_type": idea["order_type"],
        "entry": entry, "stop": stop,
        "target": round(entry + tr * risk, 2) if tr else None,   # None = hold until close
        "risk_pct": round(risk / entry * 100, 2), "score": round(idea["score"], 3),
        "reason": idea["reason"],
    }


def rank_and_cap(picks, per_setup=None, total=None):
    per_setup = per_setup or C.MAX_PICKS_PER_SETUP
    total = total or C.MAX_PICKS_TOTAL
    out, seen, per = [], set(), {}
    for p in sorted(picks, key=lambda p: p["score"], reverse=True):
        if p["ticker"] in seen or per.get(p["setup"], 0) >= per_setup:
            continue
        out.append(p); seen.add(p["ticker"]); per[p["setup"]] = per.get(p["setup"], 0) + 1
        if len(out) >= total:
            break
    return out
