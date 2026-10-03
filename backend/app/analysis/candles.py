"""Candle container shared by every analysis module."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class Candles:
    t: np.ndarray  # unix seconds, int64
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray

    def __len__(self) -> int:
        return len(self.t)

    @classmethod
    def from_rows(cls, rows: Iterable[dict]) -> "Candles":
        rows = list(rows)
        return cls(
            t=np.array([r["t"] for r in rows], dtype=np.int64),
            o=np.array([r["o"] for r in rows], dtype=float),
            h=np.array([r["h"] for r in rows], dtype=float),
            l=np.array([r["l"] for r in rows], dtype=float),
            c=np.array([r["c"] for r in rows], dtype=float),
            v=np.array([r.get("v", 0.0) for r in rows], dtype=float),
        )

    def to_rows(self) -> list[dict]:
        return [
            {"t": int(self.t[i]), "o": float(self.o[i]), "h": float(self.h[i]),
             "l": float(self.l[i]), "c": float(self.c[i]), "v": float(self.v[i])}
            for i in range(len(self))
        ]

    def slice(self, start: int, stop: int | None = None) -> "Candles":
        return Candles(self.t[start:stop], self.o[start:stop], self.h[start:stop],
                       self.l[start:stop], self.c[start:stop], self.v[start:stop])


def fmt_price(v: float) -> str:
    """Human-readable level for explanation text: thousands separators, trailing zeros trimmed."""
    if v is None:
        return "n/a"
    d = 2 if abs(v) >= 1000 else 4 if abs(v) >= 1 else 8
    return f"{v:,.{d}f}".rstrip("0").rstrip(".")
