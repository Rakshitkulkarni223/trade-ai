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
    # Supertrend (ATR 10 x 3): current direction, bars since the last flip, length of the run before it
    st_dir: int = 0                      # 1 up, -1 down, 0 unknown
    st_flip_ago: Optional[int] = None
    st_prev_run: Optional[int] = None
    st_line: Optional[float] = None


SUPERTREND_FRESH_BARS = 3     # a Buy/Sell counts as an entry trigger for this many closed candles
WHIPSAW_BARS = 5              # a flip that follows the previous flip this quickly is noise, not a trend change


def _lc(label: str) -> str:
    """Lower-case only the first letter so acronyms such as BOS and CHoCH survive inside a sentence."""
    return label[:1].lower() + label[1:]


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
    brk = st.last_event(None, w["bias"])          # a BOS or a CHoCH in this direction both count as a break
    fresh = brk is not None and n - 1 - brk.index <= BOS_RECENT_BARS
    ok = trend_ok and fresh
    items.append(_item("structure", f"{w['bias'].capitalize()} trend with a recent structure break",
                       "pass" if ok else "pending",
                       (f"Structure is {st.trend}; last {w['bias']} {brk.type} was {n - 1 - brk.index} candle(s) ago."
                        if brk else f"Structure is {st.trend}; no {w['bias']} structure break found."),
                       {"kind": "structure", "id": f"{brk.type}-{brk.index}"} if brk else None, True))

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


def _supertrend_agree(direction: str, snap: Snapshot) -> dict:
    """Required for every setup: the Supertrend must already point the trade's way."""
    want = 1 if direction == "long" else -1
    word = "up" if direction == "long" else "down"
    ok = snap.st_dir == want
    since = f" for {snap.st_flip_ago} candle(s)" if (ok and snap.st_flip_ago is not None) else ""
    return _item("supertrend", f"Supertrend is {word}", "pass" if ok else "pending",
                 (f"Supertrend has been {word}{since}." if ok else
                  f"Supertrend is {'down' if snap.st_dir == -1 else 'not yet defined' if snap.st_dir == 0 else 'up'}; "
                  f"it must turn {word} first."),
                 {"kind": "indicator", "id": "supertrend"}, True)


def _supertrend_flip_items(direction: str, snap: Snapshot) -> tuple[list[dict], Optional[float]]:
    """The Buy / Sell signal itself: a fresh flip, not a whipsaw, with the Supertrend line as the natural stop."""
    want = 1 if direction == "long" else -1
    word, label = ("up", "Buy") if direction == "long" else ("down", "Sell")
    fresh = snap.st_dir == want and snap.st_flip_ago is not None and snap.st_flip_ago <= SUPERTREND_FRESH_BARS
    items = [_item("supertrend", f"Supertrend {label} signal", "pass" if fresh else "pending",
                   (f"Supertrend flipped {word} {snap.st_flip_ago} candle(s) ago." if fresh else
                    f"No fresh {label} signal (a flip must be within the last {SUPERTREND_FRESH_BARS} closed candles)."),
                   {"kind": "indicator", "id": "supertrend"}, True)]
    if fresh:
        calm = snap.st_prev_run is None or snap.st_prev_run >= WHIPSAW_BARS
        items.append(_item("whipsaw", "Not a whipsaw", "pass" if calm else "pending",
                           (f"The previous trend lasted {snap.st_prev_run} candles." if calm else
                            f"The previous trend lasted only {snap.st_prev_run} candles; flips this close together are noise."),
                           {"kind": "indicator", "id": "supertrend"}, True))
    else:
        items.append(_item("whipsaw", "Not a whipsaw", "pending", "Checked once a Buy/Sell signal appears.", None, True))
    return items, snap.st_line


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


def _hint_for(item: dict, direction: str, setup: str, c: Candles, snap: Snapshot, st: Structure,
              lm: LiquidityMap, fvgs: list[FVG]) -> Optional[str]:
    """What would satisfy a missing condition, in plain words and with the level to watch.
    These are levels to watch, not entries: no stop or targets are implied."""
    k, long, w = item["key"], direction == "long", _dir_words(direction)
    atr = snap.atr or 0.0
    above, below = ("above", "below") if long else ("below", "above")
    if k == "extension":
        if setup == "trend_pullback" and snap.ema20 and atr:
            limit_px = snap.ema20 + (MAX_EXTENSION_ATR * atr if long else -MAX_EXTENSION_ATR * atr)
            dist = abs(snap.price - snap.ema20) / atr
            return (f"Price needs to ease back to about {_p(limit_px)} or {'lower' if long else 'higher'} "
                    f"(within {MAX_EXTENSION_ATR:g} ATR of the 20 EMA at {_p(snap.ema20)}). It is {dist:.1f} ATR away now.")
        return "Wait for price to retest the level that confirmed the setup instead of chasing the move."
    if k == "supertrend":
        want = 1 if long else -1
        if setup == "supertrend_flip" and snap.st_dir == want and snap.st_flip_ago is not None:
            return (f"The last Supertrend flip is {snap.st_flip_ago} candles old; entries are only taken within "
                    f"{SUPERTREND_FRESH_BARS} candles of a flip. Wait for the next one.")
        if snap.st_line is not None and snap.st_dir != want:
            return (f"Needs a candle to close {above} the Supertrend line at {_p(snap.st_line)}, which turns it "
                    f"{'up (a Buy)' if long else 'down (a Sell)'}.")
        return None
    if k == "whipsaw":
        return (f"The trend before this flip held only {snap.st_prev_run} candles. Wait for a trend that holds "
                f"{WHIPSAW_BARS}+ candles.") if snap.st_prev_run is not None else None
    if k == "structure":
        swings = [x for x in st.swings if x.kind == ("high" if long else "low")]
        if swings:
            lvl = swings[-1].price
            return f"A close {above} the latest swing {'high' if long else 'low'} ({_p(lvl)}) would confirm a {w['bias']} structure break."
        return None
    if k == "pullback":
        bits = []
        if snap.ema20:
            bits.append(f"the 20 EMA ({_p(snap.ema20)})")
        gap = next((g for g in reversed(fvgs) if g.type == w["bias"] and g.status != "filled"), None)
        if gap:
            bits.append(f"the open {gap.type} FVG {_p(gap.low)}–{_p(gap.high)}")
        return ("Price needs to reach " + " or ".join(bits) + ".") if bits else None
    if k == "ema_trend" and snap.ema50 is not None:
        return f"Needs a close {above} the 50 EMA ({_p(snap.ema50)})."
    if k == "sweep":
        near = lm.nearest(w["side"])
        return (f"Needs a wick through {near.kind} at {_p(near.price)} that closes back inside.") if near else None
    if k == "reclaim":
        return "Comes after a sweep: price must close back inside the swept level."
    return None


def _bucket(items: list[dict]) -> dict:
    return {
        "for": [i for i in items if i["state"] == "pass"],
        "against": [i for i in items if i["state"] == "fail"],
        "caution": [i for i in items if i["state"] == "warn"],
        "missing": [i for i in items if i["state"] == "pending"],
    }


def _evaluate_candidate(setup: str, direction: str, c, snap, st, lm, fvgs):
    if setup == "supertrend_flip":
        core, anchor = _supertrend_flip_items(direction, snap)
    elif setup == "liquidity_sweep_reversal":
        core, anchor = _reversal_items(direction, c, snap, st, lm)
        core.append(_supertrend_agree(direction, snap))
    else:
        core, anchor = _pullback_items(direction, c, snap, st, fvgs)
        core.append(_supertrend_agree(direction, snap))
    items = core + _common_items(direction, snap, fvgs)
    for it in items:
        if it["required"] and it["state"] != "pass":
            it["hint"] = _hint_for(it, direction, setup, c, snap, st, lm, fvgs)
    required = [i for i in items if i["required"]]
    passed = sum(1 for i in required if i["state"] == "pass")
    # momentum flatly against the idea blocks it even if structure lines up
    blocked = any(i["key"] == "momentum" and i["state"] == "fail" for i in items)
    complete = passed == len(required) and not blocked
    return {"setup": setup, "direction": direction, "items": items, "anchor": anchor,
            "passed": passed, "total": len(required), "complete": complete, "blocked": blocked}


def decide(c: Candles, snap: Snapshot, st: Structure, lm: LiquidityMap, fvgs: list[FVG]) -> dict:
    order = {"supertrend_flip": 0, "liquidity_sweep_reversal": 1, "trend_pullback": 2}
    cands = [_evaluate_candidate(s, d, c, snap, st, lm, fvgs) for s in order for d in ("long", "short")]

    complete = [x for x in cands if x["complete"]]
    if complete:
        # the Supertrend signal first, then a sweep reversal, then a pullback; ties go to the structural direction
        complete.sort(key=lambda x: (order[x["setup"]], _dir_words(x["direction"])["bias"] != st.trend))
        chosen, action = complete[0], complete[0]["direction"].upper()
    else:
        trend_dir = {"bullish": "long", "bearish": "short"}.get(st.trend)
        cands.sort(key=lambda x: (-x["passed"], x["direction"] != trend_dir, order[x["setup"]]))
        chosen, action = cands[0], "WAIT"

    direction = chosen["direction"]
    items = chosen["items"]
    waiting = [{"label": i["label"], "done": i["state"] == "pass", "hint": i.get("hint")} for i in items if i["required"]]
    pending = [i for i in items if i["required"] and i["state"] != "pass"]

    if action == "WAIT":
        summary = ("Confirmation is incomplete. Waiting for: " +
                   "; ".join(_lc(i["label"]) for i in pending) + ".") if pending else \
            "Momentum is working against the idea, so it is on hold."
        if chosen["blocked"]:
            summary += " Momentum currently argues against it."
    else:
        word = "bullish" if direction == "long" else "bearish"
        summary = f"Potential {word} setup ({chosen['setup'].replace('_', ' ')}): all required conditions are present."

    names = {"supertrend_flip": "Supertrend " + ("Buy" if direction == "long" else "Sell") + " signal",
             "liquidity_sweep_reversal": "Liquidity-sweep reversal", "trend_pullback": "Trend pullback"}
    if action != "WAIT":
        headline = f"{names[chosen['setup']]} confirmed on a closed candle: every required condition is met."
    elif pending:
        p0 = pending[0]
        headline = p0.get("hint") or p0["detail"]
    else:
        headline = "Momentum is working against the idea, so it is on hold."
    return {
        "headline": headline,
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
    item["hint"] = (f"The structural stop would be {risk_atr:.1f} ATR away (limit {max_atr:g}). Wait for price to move closer "
                    "to it or for tighter structure to form.")
    sig["waiting_for"].append({"label": item["label"], "done": False, "hint": item["hint"]})
    sig["headline"] = item["hint"]
    sig["action"] = "WAIT"
    sig["summary"] = ("Confirmation is incomplete. Waiting for: " +
                      "; ".join(_lc(w["label"]) for w in sig["waiting_for"] if not w["done"]) + ".")
