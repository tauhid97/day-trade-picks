import pandas as pd


def atr(daily: pd.DataFrame, n: int = 14) -> float:
    h, l, c = daily["High"], daily["Low"], daily["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / n, adjust=False).mean().iloc[-1])


def rsi(close: pd.Series, n: int = 14) -> float:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    if dn.iloc[-1] == 0:
        return 100.0
    rs = up.iloc[-1] / dn.iloc[-1]
    return float(100 - 100 / (1 + rs))


def vwap(bars: pd.DataFrame) -> pd.Series:
    tp = (bars["High"] + bars["Low"] + bars["Close"]) / 3
    return (tp * bars["Volume"]).cumsum() / bars["Volume"].cumsum().replace(0, float("nan"))
