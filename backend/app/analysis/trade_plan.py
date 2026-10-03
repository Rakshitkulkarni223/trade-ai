"""Entry / invalidation / targets from configurable rules. Levels are scenarios, not promises."""
from __future__ import annotations

from typing import Optional

from .risk import RiskConfig, position_size


def build_plan(direction: str, entry: float, atr: Optional[float], anchor: Optional[float],
               cfg: RiskConfig, liquidity_targets: Optional[list[float]] = None,
               lot_size: float = 0.0, status: str = "active", precision: int = 6,
               entry_basis: str = "last close") -> dict:
    """direction is "long" or "short". `anchor` is the structural level that, if lost,
    invalidates the idea (swept wick extreme, swing low/high)."""
    sign = 1 if direction == "long" else -1
    warnings: list[str] = []
    a = atr if atr and atr > 0 else entry * 0.01
    if not atr:
        warnings.append("ATR unavailable; a 1% stand-in was used for stop sizing.")

    stop = (anchor - sign * cfg.stop_atr_buffer * a) if anchor else entry - sign * 1.5 * a
    # stop must be on the losing side, and at least min_stop_atr away
    stop = min(stop, entry - cfg.min_stop_atr * a) if sign == 1 else max(stop, entry + cfg.min_stop_atr * a)
    risk = abs(entry - stop)
    if risk > cfg.max_stop_atr * a:
        warnings.append(f"Stop is {risk / a:.1f} ATR away. Wide stops mean small positions or large losses.")

    targets = []
    for i, r in enumerate(cfg.tp_r_multiples, start=1):
        price = entry + sign * r * risk
        note = None
        for lvl in liquidity_targets or []:
            if abs(lvl - price) <= 0.5 * a and (lvl - entry) * sign > 0:
                note = f"near liquidity at {round(lvl, precision)}"
                break
        targets.append({"name": f"TP{i}", "price": round(price, precision), "r": r, "note": note})

    sizing = position_size(cfg.equity, cfg.max_risk_per_trade_pct, entry, stop,
                           cfg.max_position_pct, lot_size)
    return {
        "direction": direction,
        "status": status,           # active | conditional (a WAIT scenario, not yet triggered)
        "entry": round(entry, precision),
        "stop": round(stop, precision),
        "targets": targets,
        "risk_per_unit": round(risk, precision),
        "rr": [round(t["r"], 2) for t in targets],
        "sizing": sizing,
        "assumptions": {
            **cfg.as_dict(),
            "entry_basis": entry_basis,
            "stop_basis": "structural anchor" if anchor else "1.5 x ATR",
            "atr": round(a, precision),
        },
        "warnings": warnings,
        "disclaimer": "Scenario levels derived from rules, not a prediction. Price can gap through a stop.",
    }
