"""Swing points, HH/HL/LH/LL labelling, BOS / CHoCH and trend.

A swing high is a bar whose high is the highest within `k` bars on each side; it is only
*confirmed* `k` bars later, and the walk below honours that so nothing here looks ahead.

BOS   = a close beyond the latest swing level, in the direction of the existing trend.
CHoCH = a close beyond the latest swing level, against the existing trend (first sign of a flip).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .candles import Candles


@dataclass
class Swing:
    index: int
    price: float
    kind: str                  # "high" | "low"
    confirmed_at: int
    label: str = ""            # HH / LH / HL / LL (filled by labelling)


@dataclass
class StructureEvent:
    type: str                  # "BOS" | "CHoCH"
    direction: str             # "bullish" | "bearish"
    index: int                 # candle that closed through the level
    level: float
    level_index: int           # swing candle that formed the level


@dataclass
class Structure:
    trend: str = "neutral"     # bullish | bearish | neutral
    swings: list[Swing] = field(default_factory=list)
    events: list[StructureEvent] = field(default_factory=list)

    def last_event(self, type_: Optional[str] = None, direction: Optional[str] = None):
        for e in reversed(self.events):
            if (type_ is None or e.type == type_) and (direction is None or e.direction == direction):
                return e
        return None


def detect_swings(c: Candles, k: int = 3) -> list[Swing]:
    n = len(c)
    out: list[Swing] = []
    for i in range(k, n - k):
        hi_window = c.h[i - k:i + k + 1]
        lo_window = c.l[i - k:i + k + 1]
        # strict on the left, non-strict on the right so a flat top yields a single swing
        if c.h[i] > c.h[i - k:i].max() and c.h[i] >= hi_window.max():
            out.append(Swing(i, float(c.h[i]), "high", i + k))
        if c.l[i] < c.l[i - k:i].min() and c.l[i] <= lo_window.min():
            out.append(Swing(i, float(c.l[i]), "low", i + k))
    out.sort(key=lambda s: (s.index, s.kind))
    return out


def _label(swings: list[Swing]) -> None:
    prev: dict[str, Optional[Swing]] = {"high": None, "low": None}
    for s in swings:
        p = prev[s.kind]
        if p is not None:
            if s.kind == "high":
                s.label = "HH" if s.price > p.price else "LH"
            else:
                s.label = "HL" if s.price > p.price else "LL"
        prev[s.kind] = s


def analyse(c: Candles, k: int = 3) -> Structure:
    swings = detect_swings(c, k)
    _label(swings)

    result = Structure(swings=swings)
    if len(c) == 0:
        return result

    by_conf: dict[int, list[Swing]] = {}
    for s in swings:
        by_conf.setdefault(s.confirmed_at, []).append(s)

    active: dict[str, Optional[Swing]] = {"high": None, "low": None}
    broken: set[int] = set()
    trend = "neutral"

    for i in range(len(c)):
        for s in by_conf.get(i, []):
            active[s.kind] = s
        hi, lo = active["high"], active["low"]
        if hi is not None and hi.index not in broken and c.c[i] > hi.price:
            broken.add(hi.index)
            kind = "CHoCH" if trend == "bearish" else "BOS"
            result.events.append(StructureEvent(kind, "bullish", i, hi.price, hi.index))
            trend = "bullish"
        elif lo is not None and lo.index not in broken and c.c[i] < lo.price:
            broken.add(lo.index)
            kind = "CHoCH" if trend == "bullish" else "BOS"
            result.events.append(StructureEvent(kind, "bearish", i, lo.price, lo.index))
            trend = "bearish"

    # If no break has happened yet, fall back to the swing sequence.
    if trend == "neutral":
        highs = [s for s in swings if s.kind == "high"][-2:]
        lows = [s for s in swings if s.kind == "low"][-2:]
        if len(highs) == 2 and len(lows) == 2:
            if highs[1].price > highs[0].price and lows[1].price > lows[0].price:
                trend = "bullish"
            elif highs[1].price < highs[0].price and lows[1].price < lows[0].price:
                trend = "bearish"
    result.trend = trend
    return result
