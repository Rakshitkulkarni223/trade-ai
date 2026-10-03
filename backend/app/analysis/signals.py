"""Turns detector output into an explainable LONG / SHORT / WAIT decision.

There is no probability and no score. Each candidate setup has *required* conditions;
if any is outstanding the answer is WAIT and the outstanding conditions are listed.
Evidence is bucketed into: supporting, against, caution, missing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .candles import Candles, fmt_price as _p
from .fair_value_gap import FVG
from .liquidity import LiquidityMap, RECLAIM_WINDOW
from .market_structure import Structure

BOS_RECENT_BARS = 40
MAX_EXTENSION_ATR = 2.5   # beyond this from the level that confirmed the setup, entry is a chase


@dataclass
class Snapshot:
    price: float
    ema20: Optional[float]
    ema50: Optional[float]
    rsi: Optional[float]
    atr: Optional[float]
    volume_ratio: Optional[float]
    vwap: Optional[float]


def _item(key: str, label: str, state: str, detail: str, ref: Optional[dict] = None,
          required: bool = False) -> dict:
    return {"key": key, "label": label, "state": state, "detail": detail,
            "ref": ref, "required": required}


def _dir_words(direction: str) -> dict:
    if direction == "long":
        return dict(side="sell_side", swept="Sell-side", bias="bullish", ema_rel="above", rsi_ok=">50")
    return dict(side="buy_side", swept="Buy-side", bias="bearish", ema_rel="below", rsi_ok="<50")


def _reversal_items(direction: str, c: Candles, snap: Snapshot, st: Structure,
                    lm: LiquidityMap) -> tuple[list[dict], Optional[float]]:
    w = _dir_words(direction)
    n = len(c)
    items: list[dict] = []
    anchor = None

    sweep = lm.recent_sweep(n, side=w["side"])
    if sweep:
        ago = n - 1 - (sweep.swept_index or 0)
        items.append(_item("sweep", f"{w['swept']} liquidity swept", "pass",
                           f"{sweep.kind} at {_p(sweep.price)} was pierced {ago} candle(s) ago and price closed back inside.",
                           {"kind": "liquidity", "id": sweep.id}, True))
        j = sweep.swept_index or 0
        window = slice(j, min(j + RECLAIM_WINDOW + 1, n))
        anchor = float(c.l[window].min()) if direction == "long" else float(c.h[window].max())
    else:
        nearest = lm.nearest(w["side"])
        where = f" The nearest is {nearest.kind} at {_p(nearest.price)}." if nearest else ""
        items.append(_item("sweep", f"{w['swept']} liquidity swept", "pending",
                           f"No recent sweep of {w['side'].replace('_', '-')} liquidity.{where}",
                           {"kind": "liquidity", "id": nearest.id} if nearest else None, True))

    shift = None
    if sweep:
        for e in reversed(st.events):
            if e.direction == w["bias"] and e.index >= (sweep.swept_index or 0):
                shift = e
                break
    if shift:
        items.append(_item("structure", f"{w['bias'].capitalize()} {shift.type}", "pass",
                           f"Price closed through the swing at {_p(shift.level)}, shifting structure {w['bias']}.",
                           {"kind": "structure", "id": f"{shift.type}-{shift.index}"}, True))
    else:
        items.append(_item("structure", f"{w['bias'].capitalize()} CHoCH / BOS after the sweep", "pending",
                           "No close through the opposing swing since the sweep.", None, True))

    if sweep:
        ok = (snap.price > sweep.price) if direction == "long" else (snap.price < sweep.price)
        items.append(_item("reclaim", "Price holds back inside the level", "pass" if ok else "pending",
                           (f"Price {_p(snap.price)} is {w['ema_rel']} the swept level {_p(sweep.price)}." if ok else
                            f"Price {_p(snap.price)} has not closed back {w['ema_rel']} {_p(sweep.price)}."),
                           {"kind": "liquidity", "id": sweep.id}, True))
        if ok and snap.atr:
            ref_level = shift.level if shift else sweep.price
            dist = abs(snap.price - ref_level) / snap.atr
            far = dist > MAX_EXTENSION_ATR
            what = "the structure-shift level" if shift else "the swept level"
            items.append(_item("extension", "Entry is not extended", "pending" if far else "pass",
                               (f"Price is {dist:.1f} ATR beyond {what}; wait for a retest rather than chase."
                                if far else f"Price is {dist:.1f} ATR from {what}."),
                               {"kind": "liquidity", "id": sweep.id}, True))
    else:
        items.append(_item("reclaim", "Price holds back inside the level", "pending",
                           "Nothing to reclaim yet.", None, True))
    return items, anchor


def _pullback_items(direction: str, c: Candles, snap: Snapshot, st: Structure,
                    fvgs: list[FVG]) -> tuple[list[dict], Optional[float]]:
    w = _dir_words(direction)
    n = len(c)
    items: list[dict] = []
    long = direction == "long"

    trend_ok = st.trend == w["bias"]
    bos = st.last_event("BOS", w["bias"])
    fresh = bos is not None and n - 1 - bos.index <= BOS_RECENT_BARS
    ok = trend_ok and fresh
    items.append(_item("structure", f"{w['bias'].capitalize()} trend with a recent BOS",
                       "pass" if ok else "pending",
                       (f"Structure is {st.trend}; last {w['bias']} BOS was {n - 1 - bos.index} candle(s) ago."
                        if bos else f"Structure is {st.trend}; no {w['bias']} BOS found."),
                       {"kind": "structure", "id": f"BOS-{bos.index}"} if bos else None, True))

    atr = snap.atr or 0.0
    zone_ref, zone_txt, near = None, "No pullback zone nearby.", False
    if atr and snap.ema20:
        recent_lo, recent_hi = float(c.l[-3:].min()), float(c.h[-3:].max())
        touched = (recent_lo <= snap.ema20 + 0.5 * atr and snap.price > snap.ema20 - 0.25 * atr) if long \
            else (recent_hi >= snap.ema20 - 0.5 * atr and snap.price < snap.ema20 + 0.25 * atr)
        if touched:
            near, zone_txt = True, f"Price pulled back to the 20 EMA ({_p(snap.ema20)})."
        for g in fvgs:
            if g.type != w["bias"] or g.status == "filled":
                continue
            inside = (recent_lo <= g.high and snap.price >= g.low) if long else (recent_hi >= g.low and snap.price <= g.high)
            if inside:
                near, zone_ref = True, {"kind": "fvg", "id": f"FVG-{g.index}"}
                zone_txt = f"Price is reacting to an unmitigated {g.type} FVG {_p(g.low)}–{_p(g.high)}."
                break
    items.append(_item("pullback", f"Pullback into {'support' if long else 'resistance'} zone", "pass" if near else "pending",
                       zone_txt, zone_ref, True))

    if atr and snap.ema20:
        dist = abs(snap.price - snap.ema20) / atr
        far = dist > MAX_EXTENSION_ATR
        items.append(_item("extension", "Entry is not extended", "pending" if far else "pass",
                           (f"Price is {dist:.1f} ATR from the 20 EMA; wait for a pullback rather than chase."
                            if far else f"Price is {dist:.1f} ATR from the 20 EMA."),
                           {"kind": "indicator", "id": "ema20"}, True))

    ema_ok = snap.ema50 is not None and ((snap.price > snap.ema50) if long else (snap.price < snap.ema50))
    items.append(_item("ema_trend", f"Price {w['ema_rel']} EMA 50", "pass" if ema_ok else "fail",
                       (f"Price {_p(snap.price)} vs EMA 50 {_p(snap.ema50)}." if snap.ema50 is not None
                        else "Not enough history for EMA 50."), {"kind": "indicator", "id": "ema50"}, True))

    # structural anchor: the swing the pullback must not lose
    kind = "low" if long else "high"
    cands = [s for s in st.swings if s.kind == kind and ((s.price < snap.price) if long else (s.price > snap.price))]
    anchor = cands[-1].price if cands else None
    return items, anchor


def _common_items(direction: str, snap: Snapshot, fvgs: list[FVG]) -> list[dict]:
    w = _dir_words(direction)
    long = direction == "long"
    items: list[dict] = []

    if snap.rsi is not None:
        if (snap.rsi > 50) == long:
            state = "pass"
            detail = f"RSI {snap.rsi:.1f}, momentum favours {w['bias']}."
        elif (long and snap.rsi >= 45) or (not long and snap.rsi <= 55):
            state, detail = "warn", f"RSI {snap.rsi:.1f} is near neutral; momentum has not clearly turned."
        else:
            state, detail = "fail", f"RSI {snap.rsi:.1f} points the other way."
        items.append(_item("momentum", "Momentum (RSI)", state, detail, {"kind": "indicator", "id": "rsi"}))

    if snap.volume_ratio is not None:
        v = snap.volume_ratio
        state = "pass" if v >= 1.2 else ("warn" if v >= 0.8 else "fail")
        word = "above average" if v >= 1.2 else ("moderate" if v >= 0.8 else "below average")
        items.append(_item("volume", "Volume confirmation", state,
                           f"Volume is {v:.2f}x its 20-bar average ({word}).", {"kind": "indicator", "id": "volume"}))

    live = [g for g in fvgs if g.type == w["bias"] and g.status != "filled"]
    if live:
        g = live[-1]
        items.append(_item("fvg", f"Unmitigated {g.type} FVG nearby", "info",
                           f"{_p(g.low)}–{_p(g.high)} ({g.status.replace('_', ' ')}).",
                           {"kind": "fvg", "id": f"FVG-{g.index}"}))
    return items


def _bucket(items: list[dict]) -> dict:
    return {
        "for": [i for i in items if i["state"] == "pass"],
        "against": [i for i in items if i["state"] == "fail"],
        "caution": [i for i in items if i["state"] == "warn"],
        "missing": [i for i in items if i["state"] == "pending"],
    }


def _evaluate_candidate(setup: str, direction: str, c, snap, st, lm, fvgs):
    if setup == "liquidity_sweep_reversal":
        core, anchor = _reversal_items(direction, c, snap, st, lm)
    else:
        core, anchor = _pullback_items(direction, c, snap, st, fvgs)
    items = core + _common_items(direction, snap, fvgs)
    required = [i for i in items if i["required"]]
    passed = sum(1 for i in required if i["state"] == "pass")
    # momentum flatly against the idea blocks it even if structure lines up
    blocked = any(i["key"] == "momentum" and i["state"] == "fail" for i in items)
    complete = passed == len(required) and not blocked
    return {"setup": setup, "direction": direction, "items": items, "anchor": anchor,
            "passed": passed, "total": len(required), "complete": complete, "blocked": blocked}


def decide(c: Candles, snap: Snapshot, st: Structure, lm: LiquidityMap, fvgs: list[FVG]) -> dict:
    cands = [_evaluate_candidate(s, d, c, snap, st, lm, fvgs)
             for s in ("liquidity_sweep_reversal", "trend_pullback") for d in ("long", "short")]

    complete = [x for x in cands if x["complete"]]
    if complete:
        # reversal wins ties; otherwise the direction aligned with structure
        complete.sort(key=lambda x: (x["setup"] != "liquidity_sweep_reversal",
                                     _dir_words(x["direction"])["bias"] != st.trend))
        chosen, action = complete[0], complete[0]["direction"].upper()
    else:
        trend_dir = {"bullish": "long", "bearish": "short"}.get(st.trend)
        cands.sort(key=lambda x: (-x["passed"], x["direction"] != trend_dir, x["setup"] != "liquidity_sweep_reversal"))
        chosen, action = cands[0], "WAIT"

    direction = chosen["direction"]
    items = chosen["items"]
    waiting = [{"label": i["label"], "done": i["state"] == "pass"} for i in items if i["required"]]
    pending = [i for i in items if i["required"] and i["state"] != "pass"]

    if action == "WAIT":
        summary = ("Confirmation is incomplete. Waiting for: " +
                   "; ".join(i["label"].lower() for i in pending) + ".") if pending else \
            "Momentum is working against the idea, so it is on hold."
        if chosen["blocked"]:
            summary += " Momentum currently argues against it."
    else:
        word = "bullish" if direction == "long" else "bearish"
        summary = f"Potential {word} setup ({chosen['setup'].replace('_', ' ')}): all required conditions are present."

    return {
        "action": action,
        "bias": st.trend,
        "considered_direction": direction,
        "setup_type": chosen["setup"],
        "summary": summary,
        "items": items,
        "evidence": _bucket(items),
        "waiting_for": waiting,
        "anchor": chosen["anchor"],
        "evidence_counts": {k: len(v) for k, v in _bucket(items).items()},
    }


def gate_wide_stop(sig: dict, risk_atr: float, max_atr: float) -> None:
    """An invalidation level that is many ATRs from price is not a setup, it is a wish. Downgrade to WAIT."""
    item = _item("stop_distance", "Invalidation is close enough to trade", "pending",
                 f"The structural invalidation is {risk_atr:.1f} ATR from entry (limit {max_atr:g}). "
                 "Wait for price to return toward the level, or for tighter structure to form.", None, True)
    sig["items"].append(item)
    sig["evidence"] = _bucket(sig["items"])
    sig["evidence_counts"] = {k: len(v) for k, v in sig["evidence"].items()}
    sig["waiting_for"].append({"label": item["label"], "done": False})
    sig["action"] = "WAIT"
    sig["summary"] = ("Confirmation is incomplete. Waiting for: " +
                      "; ".join(w["label"].lower() for w in sig["waiting_for"] if not w["done"]) + ".")
