"""Hand-built candle series with a known answer, so each detector can be checked exactly."""
from __future__ import annotations

import numpy as np

from app.analysis.candles import Candles

H = 3600


def build(rows: list[tuple], start: int = 1_700_000_000, step: int = H, vol: float = 100.0) -> Candles:
    """rows of (open, high, low, close[, volume])"""
    return Candles.from_rows([
        {"t": start + i * step, "o": r[0], "h": r[1], "l": r[2], "c": r[3], "v": r[4] if len(r) > 4 else vol}
        for i, r in enumerate(rows)])


def zigzag(points: list[float], per_leg: int = 6, width: float = 0.4) -> list[tuple]:
    """Walk linearly through `points`, emitting candles whose closes follow the path."""
    rows, prev = [], points[0]
    for target in points[1:]:
        for k in range(1, per_leg + 1):
            c = prev + (target - prev) * k / per_leg
            o = prev + (target - prev) * (k - 1) / per_leg
            rows.append((o, max(o, c) + width, min(o, c) - width, c))
        prev = target
    return rows
