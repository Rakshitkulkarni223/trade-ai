"""Runs every detector over a candle set and assembles one analysis payload.

The payload has two audiences: the chart (series, overlays with timestamps) and the AI
(`context`, a compact structured summary). Both come from the same numbers, so the AI can
only talk about what the chart shows.
"""
from __future__ import annotations

from typing import Optional

import time

import numpy as np

from . import fair_value_gap, indicators as ind, liquidity, market_structure, signals
from .candles import Candles, fmt_price as _p
from .risk import RiskConfig
from .trade_plan import build_plan

MIN_CANDLES = 60


class InsufficientData(ValueError):
    pass


def price_precision(price: float) -> int:
    if price >= 10:
        return 2
    if price >= 1:
        return 4
    return 6


def _t(c: Candles, i: int) -> int:
    return int(c.t[max(0, min(i, len(c) - 1))])


def analyse(c: Candles, symbol: str, timeframe: str, tf_seconds: int,
            session_offset_s: int = 0, cfg: Optional[RiskConfig] = None,
            lot_size: float = 0.0) -> dict:
    n = len(c)
    if n < MIN_CANDLES:
        raise InsufficientData(f"Only {n} candles available; at least {MIN_CANDLES} are needed.")
    cfg = cfg or RiskConfig()
    price = float(c.c[-1])
    prec = price_precision(price)

    # ---- indicators
    ema20, ema50 = ind.ema(c.c, 20), ind.ema(c.c, 50)
    sma200 = ind.sma(c.c, 200)
    rsi14 = ind.rsi(c.c, 14)
    atr14 = ind.atr(c.h, c.l, c.c, 14)
    vwap = ind.vwap(c)
    vol_ratio = ind.volume_ratio(c.v, 20)
    bb_u, bb_m, bb_l = ind.bollinger(c.c, 20, 2.0)
    macd_line, macd_sig, macd_hist = ind.macd(c.c)

    # A candle that is still forming has only partial volume; judge volume on the last completed one.
    forming = int(c.t[-1]) + tf_seconds > time.time()
    vr = vol_ratio[:-1] if forming else vol_ratio
    snap = signals.Snapshot(price=price, ema20=ind.last(ema20), ema50=ind.last(ema50),
                            rsi=ind.last(rsi14), atr=ind.last(atr14),
                            volume_ratio=ind.last(vr) if c.v[-20:].sum() > 0 else None,
                            vwap=ind.last(vwap))

    # ---- detectors
    st = market_structure.analyse(c, k=3)
    lm = liquidity.build(c, st, atr14, tf_seconds, session_offset_s)
    fvgs = fair_value_gap.detect(c, atr14)
    sig = signals.decide(c, snap, st, lm, fvgs)

    # ---- plan (active for LONG/SHORT, a clearly-labelled scenario for WAIT)
    direction = sig["considered_direction"]
    targets_liq = [l.price for l in lm.active("buy_side" if direction == "long" else "sell_side")]
    entry, entry_basis = price, "last close"
    waiting_on_extension = any(i["key"] == "extension" and i["state"] == "pending" for i in sig["items"])
    if (sig["action"] == "WAIT" and waiting_on_extension and snap.ema20 is not None
            and ((direction == "long" and snap.ema20 < price) or (direction == "short" and snap.ema20 > price))):
        entry, entry_basis = snap.ema20, "retest of the 20 EMA"      # price is stretched: the scenario is the pullback
    plan = build_plan(direction, entry, snap.atr, sig["anchor"], cfg, targets_liq, lot_size,
                      status="active" if sig["action"] != "WAIT" else "conditional", precision=prec,
                      entry_basis=entry_basis)
    if sig["action"] != "WAIT" and snap.atr and plan["risk_per_unit"] / snap.atr > cfg.max_stop_atr:
        signals.gate_wide_stop(sig, plan["risk_per_unit"] / snap.atr, cfg.max_stop_atr)
        plan["status"] = "conditional"
    if sig["action"] == "WAIT":
        sig["invalidation"] = (f"The {direction} idea is invalid if price trades beyond {_p(plan['stop'])}"
                               " before confirmation arrives.")
    else:
        sig["invalidation"] = (f"The setup is invalidated if price closes {'below' if direction == 'long' else 'above'}"
                               f" {_p(plan['stop'])}.")

    # ---- serialise detectors with timestamps
    swings = [{"t": _t(c, s.index), "price": s.price, "kind": s.kind, "label": s.label}
              for s in st.swings[-40:]]
    events = [{"id": f"{e.type}-{e.index}", "type": e.type, "direction": e.direction, "t": _t(c, e.index),
               "level": e.level, "level_t": _t(c, e.level_index)} for e in st.events[-12:]]
    levels = [{"id": l.id, "kind": l.kind, "side": l.side, "price": round(l.price, prec),
               "t": _t(c, l.index), "status": l.status,
               "swept_t": _t(c, l.swept_index) if l.swept_index is not None else None,
               "reclaimed": l.reclaimed} for l in lm.levels]
    fvg_out = [{"id": f"FVG-{g.index}", "type": g.type, "low": round(g.low, prec), "high": round(g.high, prec),
                "t": _t(c, g.index), "status": g.status, "size": round(g.size, prec)} for g in fvgs]

    nb, ns = lm.nearest("buy_side"), lm.nearest("sell_side")
    recent = lm.recent_sweep(n)
    last_bos, last_choch = st.last_event("BOS"), st.last_event("CHoCH")

    indicators_snapshot = {
        "rsi": _r(snap.rsi, 1), "ema20": _r(snap.ema20, prec), "ema50": _r(snap.ema50, prec),
        "sma200": _r(ind.last(sma200), prec), "atr": _r(snap.atr, prec),
        "atr_pct": _r(snap.atr / price * 100, 2) if snap.atr else None,
        "vwap": _r(snap.vwap, prec), "volume_ratio": _r(snap.volume_ratio, 2),
        "macd_hist": _r(ind.last(macd_hist), prec),
        "ema_alignment": _ema_alignment(price, snap.ema20, snap.ema50),
        "price_vs_vwap_pct": _r((price - snap.vwap) / snap.vwap * 100, 2) if snap.vwap else None,
    }

    context = {  # the §22 shape, sent to the AI instead of raw candles
        "symbol": symbol, "timeframe": timeframe, "price": round(price, prec),
        "as_of": int(c.t[-1]), "trend": st.trend,
        "rsi": indicators_snapshot["rsi"], "atr": indicators_snapshot["atr"],
        "liquidity": {
            "buy_side": [round(l.price, prec) for l in lm.active("buy_side")],
            "sell_side": [round(l.price, prec) for l in lm.active("sell_side")],
            "nearest_buy_side": round(nb.price, prec) if nb else None,
            "nearest_sell_side": round(ns.price, prec) if ns else None,
            "swept": recent.side if recent else None,
            "swept_level": round(recent.price, prec) if recent else None,
            "swept_bars_ago": (n - 1 - recent.swept_index) if recent else None,
        },
        "structure": {
            "trend": st.trend,
            "bos": last_bos.direction if last_bos else None,
            "bos_bars_ago": (n - 1 - last_bos.index) if last_bos else None,
            "choch": last_choch.direction if last_choch else None,
            "choch_bars_ago": (n - 1 - last_choch.index) if last_choch else None,
        },
        "fvg": [{"type": g["type"], "low": g["low"], "high": g["high"], "status": g["status"]} for g in fvg_out[-4:]],
        "indicators": indicators_snapshot,
        "signal": {"action": sig["action"], "setup_type": sig["setup_type"],
                   "direction_considered": direction, "summary": sig["summary"],
                   "waiting_for": sig["waiting_for"], "invalidation": sig["invalidation"]},
        "evidence": {k: [i["label"] + ": " + i["detail"] for i in v] for k, v in sig["evidence"].items()},
        "plan": {"status": plan["status"], "entry": plan["entry"], "stop": plan["stop"],
                 "targets": {t["name"]: t["price"] for t in plan["targets"]}, "rr": plan["rr"]},
    }

    return {
        "symbol": symbol, "timeframe": timeframe, "bars": n, "price": round(price, prec),
        "as_of": int(c.t[-1]), "precision": prec,
        "indicators": indicators_snapshot,
        "series": {
            "t": [int(x) for x in c.t],
            "ema20": ind.clean(ema20, prec), "ema50": ind.clean(ema50, prec),
            "vwap": ind.clean(vwap, prec),
            "bb_upper": ind.clean(bb_u, prec), "bb_lower": ind.clean(bb_l, prec),
            "rsi": ind.clean(rsi14, 2),
        },
        "structure": {"trend": st.trend, "swings": swings, "events": events,
                      "last_bos": events and next((e for e in reversed(events) if e["type"] == "BOS"), None) or None,
                      "last_choch": events and next((e for e in reversed(events) if e["type"] == "CHoCH"), None) or None},
        "liquidity": {"levels": levels,
                      "nearest_buy_side": levels_by_id(levels, nb.id) if nb else None,
                      "nearest_sell_side": levels_by_id(levels, ns.id) if ns else None,
                      "recent_sweep": levels_by_id(levels, recent.id) if recent else None},
        "fvg": fvg_out,
        "signal": sig,
        "plan": plan,
        "context": context,
    }


def levels_by_id(levels: list[dict], id_: str) -> Optional[dict]:
    return next((l for l in levels if l["id"] == id_), None)


def _r(v, d):
    return None if v is None else round(float(v), d)


def _ema_alignment(price, e20, e50) -> str:
    if e20 is None or e50 is None:
        return "unknown"
    if price > e20 > e50:
        return "bullish"
    if price < e20 < e50:
        return "bearish"
    return "mixed"
