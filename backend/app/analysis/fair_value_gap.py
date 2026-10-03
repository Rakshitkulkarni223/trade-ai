"""Three-candle imbalances (Fair Value Gaps) and their mitigation status."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .candles import Candles


@dataclass
class FVG:
    type: str          # bullish | bearish
    low: float
    high: float
    index: int         # middle candle of the three-candle pattern
    status: str        # unmitigated | partially_mitigated | filled
    size: float

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2


def detect(c: Candles, atr_values: Optional[np.ndarray] = None,
           min_atr_fraction: float = 0.25, max_results: int = 8) -> list[FVG]:
    n = len(c)
    gaps: list[FVG] = []
    for i in range(2, n):
        a = None
        if atr_values is not None and not np.isnan(atr_values[i]):
            a = atr_values[i]
        floor = min_atr_fraction * a if a else 0.0
        if c.l[i] > c.h[i - 2] and (c.l[i] - c.h[i - 2]) >= floor:
            gaps.append(FVG("bullish", float(c.h[i - 2]), float(c.l[i]), i - 1, "unmitigated",
                            float(c.l[i] - c.h[i - 2])))
        elif c.h[i] < c.l[i - 2] and (c.l[i - 2] - c.h[i]) >= floor:
            gaps.append(FVG("bearish", float(c.h[i]), float(c.l[i - 2]), i - 1, "unmitigated",
                            float(c.l[i - 2] - c.h[i])))

    for g in gaps:
        after = slice(g.index + 2, n)           # candles after the pattern completed
        if g.type == "bullish":
            lowest = float(c.l[after].min()) if g.index + 2 < n else np.inf
            if lowest <= g.low:
                g.status = "filled"
            elif lowest < g.high:
                g.status = "partially_mitigated"
        else:
            highest = float(c.h[after].max()) if g.index + 2 < n else -np.inf
            if highest >= g.high:
                g.status = "filled"
            elif highest > g.low:
                g.status = "partially_mitigated"

    live = [g for g in gaps if g.status != "filled"]
    live.sort(key=lambda g: g.index, reverse=True)
    return list(reversed(live[:max_results]))
