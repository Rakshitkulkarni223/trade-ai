"""Technical indicators. Every function returns an array the same length as its input,
front-padded with NaN where the indicator is not yet defined."""
from __future__ import annotations

import numpy as np

from .candles import Candles


def _blank(n: int) -> np.ndarray:
    return np.full(n, np.nan)


def sma(v: np.ndarray, p: int) -> np.ndarray:
    out = _blank(len(v))
    if len(v) < p:
        return out
    cs = np.cumsum(np.insert(v, 0, 0.0))
    out[p - 1:] = (cs[p:] - cs[:-p]) / p
    return out


def ema(v: np.ndarray, p: int) -> np.ndarray:
    out = _blank(len(v))
    if len(v) < p:
        return out
    k = 2.0 / (p + 1)
    out[p - 1] = v[:p].mean()
    for i in range(p, len(v)):
        out[i] = v[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(v: np.ndarray, p: int = 14) -> np.ndarray:
    out = _blank(len(v))
    if len(v) <= p:
        return out
    d = np.diff(v)
    gain, loss = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    ag, al = gain[:p].mean(), loss[:p].mean()
    out[p] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(p, len(d)):
        ag = (ag * (p - 1) + gain[i]) / p
        al = (al * (p - 1) + loss[i]) / p
        out[i + 1] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def macd(v: np.ndarray, fast: int = 12, slow: int = 26, sig: int = 9):
    line = ema(v, fast) - ema(v, slow)
    signal = _blank(len(v))
    valid = ~np.isnan(line)
    if valid.sum() >= sig:
        first = int(np.argmax(valid))
        signal[first:] = ema(line[first:], sig)
    return line, signal, line - signal


def true_range(h: np.ndarray, l: np.ndarray, c: np.ndarray) -> np.ndarray:
    prev = np.concatenate([[c[0]], c[:-1]])
    return np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))


def atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, p: int = 14) -> np.ndarray:
    out = _blank(len(c))
    if len(c) <= p:
        return out
    tr = true_range(h, l, c)
    out[p] = tr[1:p + 1].mean()
    for i in range(p + 1, len(c)):
        out[i] = (out[i - 1] * (p - 1) + tr[i]) / p
    return out


def bollinger(v: np.ndarray, p: int = 20, k: float = 2.0):
    mid = sma(v, p)
    sd = _blank(len(v))
    for i in range(p - 1, len(v)):
        sd[i] = v[i - p + 1:i + 1].std()
    return mid + k * sd, mid, mid - k * sd


def vwap(c: Candles) -> np.ndarray:
    """VWAP anchored to the UTC day, resetting at each new session day."""
    typical = (c.h + c.l + c.c) / 3
    out = _blank(len(c))
    day = c.t // 86400
    pv = vol = 0.0
    for i in range(len(c)):
        if i == 0 or day[i] != day[i - 1]:
            pv = vol = 0.0
        w = c.v[i] if c.v[i] > 0 else 1.0
        pv += typical[i] * w
        vol += w
        out[i] = pv / vol
    return out


def volume_ratio(v: np.ndarray, p: int = 20) -> np.ndarray:
    base = sma(v, p)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(base > 0, v / base, np.nan)


def clean(a: np.ndarray, digits: int = 6) -> list:
    """NaN -> None so arrays serialise to JSON."""
    return [None if (x is None or np.isnan(x)) else round(float(x), digits) for x in a]


def last(a: np.ndarray):
    """Last finite value, or None."""
    idx = np.where(~np.isnan(a))[0]
    return float(a[idx[-1]]) if len(idx) else None


def supertrend(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 10, mult: float = 3.0):
    """Supertrend, a port of the TradingView script (source hl2, ATR via Wilder smoothing).

    Returns (trend, up_line, dn_line, buy, sell):
      trend    1 = up, -1 = down, 0 = not yet defined
      up_line  the green support line, NaN while the trend is down
      dn_line  the red resistance line, NaN while the trend is up
      buy/sell booleans, True only on the candle where the trend flips
    The bands only ratchet in the trend's direction, so the trend flips rarely and never inside a candle.
    """
    n = len(c)
    a = atr(h, l, c, period)
    hl2 = (h + l) / 2
    trend = np.zeros(n, dtype=int)
    up = np.full(n, np.nan)
    dn = np.full(n, np.nan)
    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)
    valid = np.where(~np.isnan(a))[0]
    if len(valid) == 0:
        return trend, up.copy(), dn.copy(), buy, sell
    s = int(valid[0])
    for i in range(s, n):
        up_raw, dn_raw = hl2[i] - mult * a[i], hl2[i] + mult * a[i]
        if i == s:
            up1, dn1, prev_trend, prev_close = up_raw, dn_raw, 1, None
        else:
            up1, dn1, prev_trend, prev_close = up[i - 1], dn[i - 1], trend[i - 1], c[i - 1]
        up[i] = max(up_raw, up1) if (prev_close is not None and prev_close > up1) else up_raw
        dn[i] = min(dn_raw, dn1) if (prev_close is not None and prev_close < dn1) else dn_raw
        t = prev_trend
        if t == -1 and c[i] > dn1:
            t = 1
        elif t == 1 and c[i] < up1:
            t = -1
        trend[i] = t
        if i > s and t == 1 and prev_trend == -1:
            buy[i] = True
        if i > s and t == -1 and prev_trend == 1:
            sell[i] = True
    up_line = np.where(trend == 1, up, np.nan)
    dn_line = np.where(trend == -1, dn, np.nan)
    return trend, up_line, dn_line, buy, sell
