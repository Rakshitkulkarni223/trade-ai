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
from .risk import RiskConfig, position_size
from .signal_memory import SignalMemory
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


def analyse(c_all: Candles, symbol: str, timeframe: str, tf_seconds: int,
            session_offset_s: int = 0, cfg: Optional[RiskConfig] = None,
            lot_size: float = 0.0, memory: Optional[SignalMemory] = None,
            now: Optional[float] = None) -> dict:
    """Signals, levels and the plan come from CLOSED candles only. A candle that is still forming can flip a
    reading back and forth with every tick, which is exactly what makes a signal untrustworthy; the live price is
    reported separately and the setup waits for the candle to close."""
    now = time.time() if now is None else now
    forming = len(c_all) > 0 and int(c_all.t[-1]) + tf_seconds > now
    c = c_all.slice(0, len(c_all) - 1) if forming else c_all
    n = len(c)
    if n < MIN_CANDLES:
        raise InsufficientData(f"Only {n} candles available; at least {MIN_CANDLES} are needed.")
    cfg = cfg or RiskConfig()
    live_price = float(c_all.c[-1])
    price = float(c.c[-1])                  # last closed candle: the reference for entry and structure
    prec = price_precision(live_price)

    # ---- indicators
    ema20, ema50 = ind.ema(c.c, 20), ind.ema(c.c, 50)
    sma200 = ind.sma(c.c, 200)
    rsi14 = ind.rsi(c.c, 14)
    atr14 = ind.atr(c.h, c.l, c.c, 14)
    vwap = ind.vwap(c)
    vol_ratio = ind.volume_ratio(c.v, 20)
    bb_u, bb_m, bb_l = ind.bollinger(c.c, 20, 2.0)
    macd_line, macd_sig, macd_hist = ind.macd(c.c)

    # Supertrend (ATR 10, x3, hl2): the trend filter and the Buy / Sell trigger
    st_trend, st_up, st_dn, st_buy, st_sell = ind.supertrend(c.h, c.l, c.c, 10, 3.0)
    flips = np.where(st_buy | st_sell)[0]
    st_dir = int(st_trend[-1])
    st_line = ind.last(st_up if st_dir == 1 else st_dn)

    snap = signals.Snapshot(price=price, ema20=ind.last(ema20), ema50=ind.last(ema50),
                            rsi=ind.last(rsi14), atr=ind.last(atr14),
                            volume_ratio=ind.last(vol_ratio) if c.v[-20:].sum() > 0 else None,
                            vwap=ind.last(vwap), st_dir=st_dir,
                            st_flip_ago=(n - 1 - int(flips[-1])) if len(flips) else None,
                            st_prev_run=(int(flips[-1] - flips[-2])) if len(flips) >= 2 else None,
                            st_line=st_line)

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
    state = None
    if memory is not None:
        sig, plan, state = memory.apply(f"{symbol}|{timeframe}", sig, plan, c, st_dir)
        direction = sig["considered_direction"]
        # account settings can change while a setup is live; levels stay, the size follows the current settings
        plan["sizing"] = position_size(cfg.equity, cfg.max_risk_per_trade_pct, plan["entry"], plan["stop"],
                                       cfg.max_position_pct, lot_size)
    sig["state"] = state
    sig["market_read"] = _market_read(st.trend, st_dir, snap, price)
    if sig.get("held") and state:
        sig["headline"] = (f"{sig['action']} setup still active, triggered {state['age_bars']} candle(s) ago. "
                           "Its levels stay fixed until stopped, completed or expired.")
    if sig["action"] == "WAIT":
        sig["invalidation"] = ("No setup is active, so there is nothing to invalidate yet. "
                               "Levels appear once every required condition is met on a closed candle.")
    else:
        sig["invalidation"] = (f"The setup is invalidated if a candle closes {'below' if direction == 'long' else 'above'}"
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
        "symbol": symbol, "timeframe": timeframe, "price": round(live_price, prec),
        "last_closed_close": round(price, prec), "analysis_basis": "closed candles only",
        "as_of": int(c.t[-1]), "trend": st.trend,
        "supertrend": {"direction": "up" if st_dir == 1 else "down" if st_dir == -1 else "unknown",
                       "flipped_bars_ago": snap.st_flip_ago, "line": _r(st_line, prec)},
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
        "signal": {"action": sig["action"], "setup_type": sig["setup_type"], "headline": sig["headline"],
                   "market_read": sig["market_read"],
                   "direction_considered": direction, "summary": sig["summary"],
                   "waiting_for": sig["waiting_for"], "invalidation": sig["invalidation"]},
        "evidence": {k: [i["label"] + ": " + i["detail"] for i in v] for k, v in sig["evidence"].items()},
        # With no active setup there are no entry numbers to quote: giving the model scenario levels invites it to
        # present them as advice.
        "plan": ({"entry": plan["entry"], "stop": plan["stop"],
                  "targets": {t["name"]: t["price"] for t in plan["targets"]}, "rr": plan["rr"],
                  "since_candle_t": state["since_t"] if state else None}
                 if sig["action"] != "WAIT" else None),
    }

    return {
        "symbol": symbol, "timeframe": timeframe, "bars": n, "price": round(live_price, prec),
        "closed_price": round(price, prec), "forming_candle": forming,
        "as_of": int(c.t[-1]), "precision": prec,
        "indicators": indicators_snapshot,
        "series": {
            "t": [int(x) for x in c.t],
            "ema20": ind.clean(ema20, prec), "ema50": ind.clean(ema50, prec),
            "vwap": ind.clean(vwap, prec),
            "bb_upper": ind.clean(bb_u, prec), "bb_lower": ind.clean(bb_l, prec),
            "rsi": ind.clean(rsi14, 2),
            "st_up": ind.clean(st_up, prec), "st_dn": ind.clean(st_dn, prec),
        },
        "supertrend": {
            "period": 10, "multiplier": 3.0,
            "direction": "up" if st_dir == 1 else "down" if st_dir == -1 else "unknown",
            "signals": [{"t": _t(c, int(i)), "type": "buy" if st_buy[i] else "sell",
                         "price": round(float(st_up[i] if st_buy[i] else st_dn[i]), prec)} for i in flips[-12:]],
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


def _market_read(trend: str, st_dir: int, snap, price: float) -> list[str]:
    """Three or four plain facts, always shown with the verdict. Deterministic, so reading it costs nothing."""
    read = []
    stn = {1: "up", -1: "down"}.get(st_dir)
    since = f" for {snap.st_flip_ago} candles" if snap.st_flip_ago is not None and stn else ""
    read.append(f"Structure is {trend}" + (f"; Supertrend is {stn}{since}." if stn else "."))
    if snap.rsi is not None:
        note = (" (stretched: moves like this often pause or pull back)" if snap.rsi >= 70
                else " (oversold: selling is stretched)" if snap.rsi <= 30 else "")
        read.append(f"RSI is {snap.rsi:.0f}{note}.")
    if snap.atr and snap.ema20:
        d = (price - snap.ema20) / snap.atr
        read.append(f"Price is {abs(d):.1f} ATR {'above' if d > 0 else 'below'} its 20 EMA.")
    if snap.volume_ratio is not None:
        read.append(f"Volume is {snap.volume_ratio:.2f}x its 20-candle average.")
    return read


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
