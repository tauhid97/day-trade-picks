"""Free market data from Yahoo Finance (via yfinance)."""
import time

import pandas as pd

NY = "America/New_York"
COLS = ["Open", "High", "Low", "Close", "Volume"]


def load_universe(path):
    out = []
    for line in open(path):
        line = line.split("#")[0]
        out += [t.strip().upper() for t in line.split() if t.strip()]
    return list(dict.fromkeys(out))


def _download(tickers, **kw):
    import yfinance as yf
    frames = {}
    for i in range(0, len(tickers), 40):
        chunk = tickers[i:i + 40]
        for attempt in range(3):
            try:
                df = yf.download(chunk, group_by="ticker", auto_adjust=False,
                                 threads=True, progress=False, **kw)
                break
            except Exception as e:  # rate limits etc.
                print(f"download error ({e}); retrying...")
                time.sleep(10 * (attempt + 1))
        else:
            continue
        for t in chunk:
            try:
                sub = df[t] if isinstance(df.columns, pd.MultiIndex) else df
            except KeyError:
                continue
            sub = sub[[c for c in COLS if c in sub.columns]].dropna(subset=["Close"])
            if len(sub):
                frames[t] = sub
        time.sleep(1)
    return frames


def get_intraday(tickers, period="15d", interval="5m"):
    out = {}
    for t, df in _download(tickers, period=period, interval=interval, prepost=False).items():
        idx = df.index if df.index.tz is not None else df.index.tz_localize("UTC")
        df = df.copy()
        df.index = idx.tz_convert(NY)
        df = df.between_time("09:30", "15:59")
        if len(df):
            out[t] = df
    return out


def get_daily(tickers, period="1y"):
    out = {}
    for t, df in _download(tickers, period=period, interval="1d").items():
        df = df.copy()
        idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
        df.index = pd.DatetimeIndex(idx).normalize()
        out[t] = df
    return out
