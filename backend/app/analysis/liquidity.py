"""Liquidity map: previous day/week extremes, swing highs/lows, equal highs/lows, and sweeps.

Buy-side liquidity (BSL) rests above highs, sell-side liquidity (SSL) below lows.
A level is *swept* when price trades through it with a wick but closes back on the original
side within a few candles; it is *broken* when price closes and holds beyond it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .candles import Candles
from .market_structure import Structure, detect_swings

RECLAIM_WINDOW = 3       # candles allowed for price to close back inside after the wick
RECENT_SWEEP_BARS = 20   # "recent" for the purpose of the setup logic
MAJOR_SWING_K = 8        # swing liquidity comes from major swings; minor wiggles are noise


@dataclass
class LiquidityLevel:
    id: str
    kind: str                    # PDH PDL PWH PWL BSL SSL EQH EQL
    side: str                    # buy_side | sell_side
    price: float
    index: int                   # candle where the level formed
    status: str = "active"       # active | swept | broken
    swept_index: Optional[int] = None
    reclaimed: bool = False
    eval_from: int = -1          # first candle to test for a sweep (internal)


@dataclass
class LiquidityMap:
    levels: list[LiquidityLevel] = field(default_factory=list)
    price: float = 0.0

    def active(self, side: str) -> list[LiquidityLevel]:
        return [l for l in self.levels if l.side == side and l.status == "active"]

    def nearest(self, side: str) -> Optional[LiquidityLevel]:
        act = self.active(side)
        if not act:
            return None
        if side == "buy_side":
            above = [l for l in act if l.price > self.price]
            return min(above, key=lambda l: l.price) if above else None
        below = [l for l in act if l.price < self.price]
        return max(below, key=lambda l: l.price) if below else None

    def sweeps(self) -> list[LiquidityLevel]:
        return sorted((l for l in self.levels if l.status == "swept"),
                      key=lambda l: l.swept_index or 0, reverse=True)

    def recent_sweep(self, n: int, side: Optional[str] = None,
                     within: int = RECENT_SWEEP_BARS) -> Optional[LiquidityLevel]:
        for l in self.sweeps():
            if l.swept_index is not None and n - 1 - l.swept_index <= within and (side is None or l.side == side):
                return l
        return None


# --------------------------------------------------------------------------- helpers
def _evaluate(level: LiquidityLevel, c: Candles, start: int) -> None:
    """Walk candles from `start` and set sweep / break status on the level."""
    n = len(c)
    for j in range(max(start, 0), n):
        if level.side == "buy_side":
            pierced = c.h[j] > level.price
        else:
            pierced = c.l[j] < level.price
        if not pierced:
            continue
        for m in range(j, min(j + RECLAIM_WINDOW + 1, n)):
            back_inside = c.c[m] <= level.price if level.side == "buy_side" else c.c[m] >= level.price
            if back_inside:
                level.status, level.swept_index, level.reclaimed = "swept", j, True
                return
        # closed beyond and (as far as we can see) held there
        level.status, level.swept_index = "broken", j
        return


def _period_extremes(c: Candles, key: np.ndarray):
    """(high, low, last_index_of_period) of the most recent *completed* period, or None."""
    n = len(c)
    if n == 0:
        return None
    cur = key[-1]
    idx = np.where(key != cur)[0]
    if len(idx) == 0:
        return None
    prev_key = key[idx[-1]]
    members = np.where(key == prev_key)[0]
    return float(c.h[members].max()), float(c.l[members].min()), int(members[-1])


def build(c: Candles, structure: Structure, atr_values: Optional[np.ndarray] = None,
          tf_seconds: int = 3600, session_offset_s: int = 0, lookback: int = 250) -> LiquidityMap:
    n = len(c)
    lm = LiquidityMap(price=float(c.c[-1]) if n else 0.0)
    if n < 10:
        return lm

    local_t = c.t + session_offset_s
    day_key = local_t // 86400
    week_key = (day_key + 3) // 7            # weeks start on Monday

    # ---- previous day / week
    if tf_seconds < 86400:
        ext = _period_extremes(c, day_key)
        if ext:
            hi, lo, last_i = ext
            lm.levels += [LiquidityLevel("PDH", "PDH", "buy_side", hi, last_i),
                          LiquidityLevel("PDL", "PDL", "sell_side", lo, last_i)]
    if tf_seconds < 7 * 86400:
        ext = _period_extremes(c, week_key)
        if ext:
            hi, lo, last_i = ext
            lm.levels += [LiquidityLevel("PWH", "PWH", "buy_side", hi, last_i),
                          LiquidityLevel("PWL", "PWL", "sell_side", lo, last_i)]

    # ---- equal highs / lows from swings
    cutoff = max(0, n - lookback)
    swings = [s for s in structure.swings if s.index >= cutoff]
    a = float(atr_values[-1]) if atr_values is not None and not np.isnan(atr_values[-1]) else None
    tol = max(0.15 * a if a else 0.0, lm.price * 0.0005)

    used: set[int] = set()
    for kind, eq_kind, side in (("high", "EQH", "buy_side"), ("low", "EQL", "sell_side")):
        pts = [s for s in swings if s.kind == kind]
        pts.sort(key=lambda s: s.price)
        cluster: list = []
        clusters: list[list] = []
        for s in pts:
            if cluster and abs(s.price - cluster[-1].price) <= tol:
                cluster.append(s)
            else:
                if len(cluster) >= 2:
                    clusters.append(cluster)
                cluster = [s]
        if len(cluster) >= 2:
            clusters.append(cluster)
        for cl in clusters:
            price = max(s.price for s in cl) if kind == "high" else min(s.price for s in cl)
            formed = max(s.confirmed_at for s in cl)
            lvl = LiquidityLevel(f"{eq_kind}-{formed}", eq_kind, side, price, max(s.index for s in cl))
            lm.levels.append(lvl)
            used.update(s.index for s in cl)
            lvl.eval_from = formed + 1

    # ---- individual swing levels (major swings only)
    major = [s for s in detect_swings(c, MAJOR_SWING_K) if s.index >= cutoff]
    for s in major:
        if s.index in used:
            continue
        kind, side = ("BSL", "buy_side") if s.kind == "high" else ("SSL", "sell_side")
        lvl = LiquidityLevel(f"{kind}-{s.index}", kind, side, s.price, s.index)
        lvl.eval_from = s.confirmed_at + 1
        lm.levels.append(lvl)

    # ---- evaluate each level against the candles that followed its formation
    for lvl in lm.levels:
        _evaluate(lvl, c, lvl.eval_from if lvl.eval_from >= 0 else lvl.index + 1)

    # ---- prune: drop broken levels, keep a short, readable map
    kept: list[LiquidityLevel] = []
    for lvl in lm.levels:
        if lvl.status == "broken":
            continue
        if lvl.status == "swept" and (n - 1 - (lvl.swept_index or 0)) > 60:
            continue
        kept.append(lvl)

    persistent = [l for l in kept if l.kind in ("PDH", "PDL", "PWH", "PWL")]
    dynamic = [l for l in kept if l.kind not in ("PDH", "PDL", "PWH", "PWL")]
    price = lm.price
    out = list(persistent)
    for side in ("buy_side", "sell_side"):
        act = [l for l in dynamic if l.side == side and l.status == "active"]
        act.sort(key=lambda l: abs(l.price - price))
        out += act[:4]
        swept = [l for l in dynamic if l.side == side and l.status == "swept"]
        swept.sort(key=lambda l: l.swept_index or 0, reverse=True)
        out += swept[:2]
    lm.levels = out
    return lm
