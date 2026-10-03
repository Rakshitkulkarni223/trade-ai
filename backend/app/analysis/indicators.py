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
