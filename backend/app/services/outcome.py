"""What would have happened to a saved plan? Walks the candles after the plan was made.

Conservative by construction: if one candle touches both the stop and a target, the stop wins.
Fills are assumed at the plan's entry; fees, slippage and gaps are ignored. This is a study
tool, not a P&L statement.
"""
from __future__ import annotations

from typing import Optional


def evaluate(direction: str, entry: float, stop: float, targets: list[dict],
             candles: list[dict], after_t: int) -> dict:
    long = direction == "long"
    risk = abs(entry - stop)
    best = 0
    state, closed_t, last = "open", None, entry
    for c in candles:
        if c["t"] <= after_t:
            continue
        last = c["c"]
        stop_hit = c["l"] <= stop if long else c["h"] >= stop
        if stop_hit:
            state, closed_t = "stopped", c["t"]
            break
        for i, tg in enumerate(targets, start=1):
            if (c["h"] >= tg["price"]) if long else (c["l"] <= tg["price"]):
                best = max(best, i)
        if best == len(targets):
            state, closed_t = "target_%d" % best, c["t"]
            break
    if state == "open" and best:
        state = f"target_{best}_open"
    r_now = ((last - entry) if long else (entry - last)) / risk if risk else 0.0
    if state == "stopped":
        outcome_r = -1.0 if best == 0 else float(targets[best - 1]["r"])
    elif state.startswith("target_") and not state.endswith("_open"):
        outcome_r = float(targets[best - 1]["r"])
    else:
        outcome_r = None
    return {"state": state, "best_target": best, "closed_t": closed_t,
            "last_price": last, "open_r": round(r_now, 2),
            "realised_r": None if outcome_r is None else round(outcome_r, 2),
            "closed": state in ("stopped",) or (state.startswith("target_") and not state.endswith("_open")),
            "note": "Idealised: assumes a fill at entry, no fees or slippage; stop wins ties within a candle."}
