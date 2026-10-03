"""A triggered setup is a commitment, not a live reading.

Without this, a signal recomputed every refresh can read LONG, then SHORT, then WAIT within minutes as price
wobbles. Here a setup, once triggered on a closed candle, keeps its entry / stop / targets until one of:
  - the stop is hit (a closed candle trades through it) or the last target is reached,
  - it has run for `ttl_bars` closed candles,
  - the Supertrend turns against it.
Only then can the opposite side (or a fresh setup) replace it. The opposite side cannot appear earlier anyway,
because every setup requires the Supertrend to agree.
"""
from __future__ import annotations

import copy
from typing import Optional

import numpy as np

from ..services.outcome import evaluate
from .candles import Candles

TTL_BARS = 30


class SignalMemory:
    def __init__(self, ttl_bars: int = TTL_BARS):
        self.ttl_bars = ttl_bars
        self._held: dict[str, dict] = {}

    def clear(self) -> None:
        self._held.clear()

    def get(self, key: str) -> Optional[dict]:
        return self._held.get(key)

    def apply(self, key: str, sig: dict, plan: dict, closed: Candles, st_dir: int):
        """Returns (signal, plan, state). `closed` holds only completed candles."""
        last_t = int(closed.t[-1])
        rec = self._held.get(key)
        progress: Optional[dict] = None

        if rec:
            idx = int(np.searchsorted(closed.t, rec["signal_t"], side="right"))
            rows = closed.slice(idx).to_rows()
            progress = evaluate(rec["direction"], rec["plan"]["entry"], rec["plan"]["stop"],
                                rec["plan"]["targets"], rows, rec["signal_t"])
            want = 1 if rec["direction"] == "long" else -1
            if progress["closed"] or len(rows) > self.ttl_bars or st_dir != want:
                del self._held[key]
                rec, progress = None, None

        if sig["action"] != "WAIT":
            if rec and rec["direction"] == sig["considered_direction"]:
                plan = copy.deepcopy(rec["plan"])               # same idea as before: levels do not move
            else:
                rec = {"direction": sig["considered_direction"], "signal": copy.deepcopy(sig),
                       "plan": copy.deepcopy(plan), "signal_t": last_t}
                self._held[key] = rec
                progress = None
        elif rec:
            sig = copy.deepcopy(rec["signal"])                  # conditions lapsed, the setup is still live
            sig["held"] = True
            plan = copy.deepcopy(rec["plan"])

        state = None
        if rec:
            idx = int(np.searchsorted(closed.t, rec["signal_t"], side="right"))
            state = {"since_t": rec["signal_t"], "age_bars": len(closed) - idx, "held": bool(sig.get("held")),
                     "progress": {k: progress[k] for k in ("state", "best_target", "open_r")} if progress else
                                 {"state": "open", "best_target": 0, "open_r": 0.0}}
        return sig, plan, state
