"""Risk arithmetic. Pure functions; every assumption is returned with the numbers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskConfig:
    equity: float = 100_000.0
    max_risk_per_trade_pct: float = 1.0
    max_position_pct: float = 25.0
    max_daily_loss_pct: float = 3.0
    tp_r_multiples: tuple = (1.0, 2.0, 3.0)
    stop_atr_buffer: float = 0.25      # padding beyond the structural anchor
    min_stop_atr: float = 0.75         # never place a stop tighter than this many ATRs
    max_stop_atr: float = 4.0          # wider than this is flagged, not hidden

    def as_dict(self) -> dict:
        return {
            "equity": self.equity,
            "max_risk_per_trade_pct": self.max_risk_per_trade_pct,
            "max_position_pct": self.max_position_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "tp_r_multiples": list(self.tp_r_multiples),
            "stop_atr_buffer": self.stop_atr_buffer,
            "min_stop_atr": self.min_stop_atr,
            "max_stop_atr": self.max_stop_atr,
        }


def position_size(equity: float, risk_pct: float, entry: float, stop: float,
                  max_position_pct: Optional[float] = None, lot_size: float = 0.0) -> dict:
    """Quantity such that being stopped out loses `risk_pct` of equity, capped by position size.

    `lot_size` > 0 floors the quantity to a whole number of units (use 1 for shares,
    0 for fractional assets such as crypto).
    """
    per_unit = abs(entry - stop)
    if per_unit <= 0 or entry <= 0 or equity <= 0:
        return {"quantity": 0.0, "risk_per_unit": per_unit, "risk_amount": 0.0,
                "position_value": 0.0, "position_pct": 0.0, "capped": False,
                "note": "entry and stop must differ and equity must be positive"}
    budget = equity * risk_pct / 100
    qty = budget / per_unit
    capped = False
    if max_position_pct:
        max_qty = equity * max_position_pct / 100 / entry
        if qty > max_qty:
            qty, capped = max_qty, True
    qty = float(int(qty)) if lot_size >= 1 else round(qty, 6)
    value = qty * entry
    return {
        "quantity": qty,
        "risk_per_unit": round(per_unit, 8),
        "risk_amount": round(qty * per_unit, 2),
        "risk_pct_of_equity": round(qty * per_unit / equity * 100, 3),
        "position_value": round(value, 2),
        "position_pct": round(value / equity * 100, 2),
        "capped": capped,
        "note": ("Quantity reduced to respect the maximum position size." if capped else
                 ("One unit risks more than the whole risk budget." if qty == 0 else None)),
    }
