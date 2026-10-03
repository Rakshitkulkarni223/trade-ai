"""ExplanationAgent: turns findings into the fixed 12-section analysis and into plain-English answers.

Everything here is deterministic. It is both the offline "AI" and the fallback whenever a real
LLM answer fails the number guard.
"""
from __future__ import annotations

import re
from typing import Optional

from .common import Finding, Fmt, bars_ago

DISCLAIMER = ("Informational analysis from rules applied to market data. Not financial advice, "
              "not a prediction, and no outcome is guaranteed.")

INTENT_LABELS = {
    "analyze": "Analyze Chart", "liquidity": "Find Liquidity", "entry": "Find Entry",
    "invalidation": "Find Invalidation", "trend": "Explain Trend", "compare": "Compare",
    "swing": "Find Swing Setup", "why_wait": "Why Should I Wait?", "beginner": "Explain Like I'm a Beginner",
    "fvg": "Explain the FVG", "structure": "Explain Structure", "what_changed": "What changed?",
    "whatif": "What if…",
}


# --------------------------------------------------------------------------- intent
_PRICE_IN_TEXT = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")


def extract_level(text: str) -> Optional[float]:
    nums = [float(m.replace(",", "")) for m in _PRICE_IN_TEXT.findall(text)]
    nums = [n for n in nums if n >= 1]
    return nums[-1] if nums else None


def detect_intent(text: str) -> str:
    t = text.lower()
    if re.search(r"\bcompare\b|\bvs\.?\b|\bversus\b", t):
        return "compare"
    if "what changed" in t or "since the previous" in t or "since the last" in t:
        return "what_changed"
    if re.search(r"what (if|happens)|if (it|price|the price)|goes? (below|above)|falls? below|drops? below|breaks?", t) \
            and extract_level(t) is not None:
        return "whatif"
    if "wait" in t:
        return "why_wait"
    if re.search(r"beginner|like i'?m|eli5|simple terms|simply", t):
        return "beginner"
    if "swing" in t:
        return "swing"
    if re.search(r"invalid|stop.?loss|\bsl\b|where.*stop", t):
        return "invalidation"
    if re.search(r"\bentry\b|where to (buy|enter|sell)|\benter\b", t):
        return "entry"
    if re.search(r"fvg|fair value|imbalance|\bgap\b", t):
        return "fvg"
    if re.search(r"liquidity|sweep|stop hunt|equal (high|low)", t):
        return "liquidity"
    if re.search(r"choch|\bbos\b|structure|change of character|break of", t):
        return "structure"
    if "trend" in t:
        return "trend"
    if re.search(r"analy|chart|setup|plan|look", t):
        return "analyze"
    return "general"


# --------------------------------------------------------------------------- sections
def _sec(id_, title, body, bullets=None, refs=None) -> dict:
    return {"id": id_, "title": title, "body": body, "bullets": bullets or [], "refs": refs or []}


def build_sections(a: dict, inst, f: Fmt, F: dict[str, Finding], status: dict, quote: Optional[dict]) -> list[dict]:
    sig, plan = a["signal"], a["plan"]
    scenario = plan["status"] == "conditional"
    ctx_bits = [f"{inst.name} on the {a['timeframe']} chart, last price {f.price(a['price'])}"]
    if quote and quote.get("change_pct") is not None:
        ctx_bits[0] += f" ({f.pct(quote['change_pct'])} on the day)"
    ctx = ctx_bits[0] + f". {a['bars']} candles analysed."
    ctx_extra = [status["note"]] if status.get("note") else []

    ind = F["technical"]
    ev = sig["evidence"]
    tgt_bullets = [f"{t['name']}: {f.price(t['price'])} ({t['r']:g}R)" + (f", {t['note']}" if t["note"] else "")
                   for t in plan["targets"]]
    pre = "Scenario only, not active. " if scenario else ""

    return [
        _sec("context", "1. Market context", ctx, ctx_extra),
        _sec("trend", "2. Trend",
             f"Structure is {a['structure']['trend']}; EMA alignment is {a['indicators']['ema_alignment']}.",
             [x for x in ind.facts if "EMA" in x]),
        _sec("liquidity", "3. Liquidity", F["liquidity"].headline + ".", F["liquidity"].facts, F["liquidity"].refs),
        _sec("structure", "4. Market structure", F["structure"].headline + ".", F["structure"].facts, F["structure"].refs),
        _sec("indicators", "5. Technical indicators", "Calculated by the backend on the loaded candles.", ind.facts),
        _sec("setup", "6. Setup", f"{sig['action']}: {sig['summary']}",
             [("✓ " if w["done"] else "○ ") + w["label"] for w in sig["waiting_for"]]),
        _sec("entry", "7. Entry", f"{pre}{plan['direction'].upper()} entry {f.price(plan['entry'])} ({plan['assumptions']['entry_basis']}).",
             [], [{"kind": "plan", "id": "entry"}]),
        _sec("stop", "8. Invalidation / stop",
             f"{pre}Stop at {f.price(plan['stop'])}, {f.price(plan['risk_per_unit'])} from entry.",
             plan["warnings"], [{"kind": "plan", "id": "stop"}]),
        _sec("targets", "9. Targets", pre + "Targets are multiples of the risk distance, not predictions.",
             tgt_bullets, [{"kind": "plan", "id": "targets"}]),
        _sec("risk", "10. Risk / reward",
             "Reward-to-risk at the targets: " + " / ".join(f"{r:g}R" for r in plan["rr"]) + ".",
             F["risk"].facts[2:]),
        _sec("invalidates", "11. What would invalidate the setup?", sig["invalidation"], []),
        _sec("evidence", "12. Evidence summary",
             f"{len(ev['for'])} supporting, {len(ev['against'])} against, {len(ev['caution'])} caution, "
             f"{len(ev['missing'])} missing.",
             [f"✓ {i['label']}" for i in ev["for"]] + [f"⚠ {i['label']}" for i in ev["caution"]] +
             [f"✗ {i['label']}" for i in ev["against"]] + [f"○ {i['label']}" for i in ev["missing"]]),
    ]


# --------------------------------------------------------------------------- narrative
def narrative(a: dict, inst, f: Fmt, F: dict[str, Finding], status: dict) -> str:
    sig, st, liq = a["signal"], a["structure"], a["liquidity"]
    parts = []
    if status.get("stale"):
        parts.append("Heads up: the latest data looks delayed, so treat this as a snapshot of the last available candles.")
    parts.append(f"{inst.name} is trading at {f.price(a['price'])} on the {a['timeframe']} chart, "
                 f"with {st['trend']} market structure.")
    sw = liq["recent_sweep"]
    if sw:
        side = "sell-side" if sw["side"] == "sell_side" else "buy-side"
        parts.append(f"{side.capitalize()} liquidity around {f.price(sw['price'])} was recently swept: price traded "
                     f"through the level and closed back inside it.")
    ch = st.get("last_choch")
    if ch:
        parts.append(f"The last change of character was {ch['direction']}, closing through {f.price(ch['level'])}.")
    i = a["indicators"]
    if i["rsi"] is not None:
        parts.append(f"RSI is {i['rsi']:.0f} and price is {'above' if a['price'] > (i['ema50'] or a['price']) else 'below'} the 50 EMA.")
    if sig["action"] == "WAIT":
        miss = [w["label"].lower() for w in sig["waiting_for"] if not w["done"]]
        parts.append("Status: WAIT. Confirmation is incomplete" + (f" (still needed: {'; '.join(miss)})." if miss else "."))
    else:
        parts.append(f"Status: potential {sig['action']} setup. It remains a scenario, not a certainty.")
    parts.append(sig["invalidation"])
    return " ".join(parts)


# --------------------------------------------------------------------------- intent answers
def answer(intent: str, a: dict, inst, f: Fmt, F: dict[str, Finding], status: dict,
           level: Optional[float] = None) -> dict:
    """Returns {"text": str, "refs": [...]}. Deterministic."""
    sig, plan, st = a["signal"], a["plan"], a["structure"]
    nar = narrative(a, inst, f, F, status)

    if intent == "liquidity":
        lines = F["liquidity"].facts
        return {"text": "Liquidity on the chart:\n" + "\n".join("• " + x for x in lines), "refs": F["liquidity"].refs}

    if intent == "structure":
        return {"text": "Market structure:\n" + "\n".join("• " + x for x in F["structure"].facts), "refs": F["structure"].refs}

    if intent == "trend":
        t = F["technical"].facts
        return {"text": f"Trend: structure is {st['trend']} and EMAs are {a['indicators']['ema_alignment']}.\n" +
                        "\n".join("• " + x for x in F["structure"].facts[:3] + [x for x in t if "EMA" in x]),
                "refs": F["structure"].refs}

    if intent == "fvg":
        if not a["fvg"]:
            return {"text": "No unfilled fair value gaps were found in the loaded candles.", "refs": []}
        lines = [f"• {g['type'].capitalize()} FVG {f.price(g['low'])} to {f.price(g['high'])}, "
                 f"{g['status'].replace('_', ' ')}" for g in a["fvg"][-4:]]
        return {"text": "A fair value gap is a three-candle imbalance where price moved so fast that one side of the "
                        "market barely traded. Price often revisits these zones. Current gaps:\n" + "\n".join(lines),
                "refs": [{"kind": "fvg", "id": g["id"]} for g in a["fvg"][-4:]]}

    if intent in ("entry", "invalidation"):
        scenario = plan["status"] == "conditional"
        if intent == "entry":
            if scenario:
                txt = (f"There is no active entry: the status is WAIT. If the {plan['direction']} idea triggers, the "
                       f"reference entry is {f.price(plan['entry'])} ({plan['assumptions']['entry_basis']}), with invalidation at {f.price(plan['stop'])}. "
                       "Still needed: " + "; ".join(w["label"].lower() for w in sig["waiting_for"] if not w["done"]) + ".")
            else:
                txt = (f"Reference entry for the {plan['direction']} setup is {f.price(plan['entry'])} ({plan['assumptions']['entry_basis']}). "
                       f"Invalidation is {f.price(plan['stop'])}. Entries are scenario levels, not guarantees.")
        else:
            txt = (f"{sig['invalidation']} That level sits {f.price(plan['risk_per_unit'])} from the reference entry "
                   f"{f.price(plan['entry'])}, about {plan['assumptions']['atr'] and plan['risk_per_unit'] / plan['assumptions']['atr']:.1f} ATR.")
        return {"text": txt, "refs": [{"kind": "plan", "id": "stop"}, {"kind": "plan", "id": "entry"}]}

    if intent == "why_wait":
        if sig["action"] == "WAIT":
            lines = [("✓ " if w["done"] else "○ ") + w["label"] for w in sig["waiting_for"]]
            txt = (f"Status is WAIT because {sig['summary'].lower()}\n" + "\n".join(lines) +
                   f"\n{sig['invalidation']}")
        else:
            cautions = [i["label"] + ": " + i["detail"] for i in sig["evidence"]["caution"]]
            txt = (f"The status is {sig['action']}, not WAIT: every required condition is present. Remaining cautions:\n" +
                   ("\n".join("⚠ " + c for c in cautions) if cautions else "none flagged") + f"\n{sig['invalidation']}")
        return {"text": txt, "refs": []}

    if intent == "beginner":
        direction = "up" if st["trend"] == "bullish" else "down" if st["trend"] == "bearish" else "sideways"
        txt = (f"Think of {inst.name} as a path. Right now the path has been heading {direction}. "
               "Traders often place stop orders just beyond recent highs and lows, so price sometimes dips below a "
               "low, grabs those orders, then turns around. That is a 'liquidity sweep'.\n")
        sw = a["liquidity"]["recent_sweep"]
        txt += (f"Here, a sweep around {f.price(sw['price'])} did just happen. " if sw else "No sweep has happened recently. ")
        if sig["action"] == "WAIT":
            txt += "The checklist is not complete yet, so the sensible reading is: wait and watch rather than act. "
        else:
            txt += "The checklist is complete, so this is a candidate setup. "
        txt += f"The idea is wrong if price goes beyond {f.price(plan['stop'])}. Nothing here is a guarantee."
        return {"text": txt, "refs": []}

    if intent == "whatif" and level is not None:
        return {"text": _what_if(a, f, level), "refs": [{"kind": "plan", "id": "stop"}]}

    if intent == "swing":
        return {"text": "Swing view on the daily timeframe:\n" + nar, "refs": []}

    return {"text": nar, "refs": [r for fi in ("liquidity", "structure") for r in F[fi].refs]}


def _what_if(a: dict, f: Fmt, level: float) -> str:
    plan, sig, price = a["plan"], a["signal"], a["price"]
    stop, long = plan["stop"], plan["direction"] == "long"
    lines = [f"You asked about {f.price(level)}; price is {f.price(price)}, a move of {f.pct((level - price) / price * 100)}."]
    beyond_stop = (level <= stop) if long else (level >= stop)
    status_word = "scenario" if plan["status"] == "conditional" else "setup"
    if beyond_stop:
        lines.append(f"That is beyond the invalidation level {f.price(stop)}, so the {plan['direction']} {status_word} "
                     "would already have been invalidated before price got there.")
    else:
        lines.append(f"That is still on the valid side of the invalidation level {f.price(stop)}, so on its own "
                     f"it would not invalidate the {plan['direction']} {status_word}.")
    liq = a["liquidity"]
    levels = sorted((l for l in liq["levels"]), key=lambda l: abs(l["price"] - level))
    if levels and abs(levels[0]["price"] - level) <= (a["indicators"]["atr"] or 0) * 0.5:
        l = levels[0]
        lines.append(f"{f.price(level)} is close to {l['kind']} at {f.price(l['price'])}; levels like that often "
                     "see sharp, stop-driven moves, so a brief poke through is not the same as a sustained break.")
    elif level < price:
        below = [l for l in liq["levels"] if l["side"] == "sell_side" and l["status"] == "active" and l["price"] > level]
        if below:
            lines.append(f"On the way down it would first trade through sell-side liquidity at "
                         + ", ".join(f.price(l["price"]) for l in sorted(below, key=lambda l: -l["price"])[:2]) + ".")
    else:
        above = [l for l in liq["levels"] if l["side"] == "buy_side" and l["status"] == "active" and l["price"] < level]
        if above:
            lines.append("On the way up it would first trade through buy-side liquidity at "
                         + ", ".join(f.price(l["price"]) for l in sorted(above, key=lambda l: l["price"])[:2]) + ".")
    lines.append("This is a rules-based read of the current chart, not a forecast.")
    return " ".join(lines)


def compare(a1: dict, a2: dict, i1, i2, f1: Fmt, f2: Fmt) -> dict:
    def row(a, i, f):
        s = a["signal"]
        return {"symbol": i.symbol, "name": i.name, "price": a["price"], "trend": a["structure"]["trend"],
                "rsi": a["indicators"]["rsi"], "atr_pct": a["indicators"]["atr_pct"],
                "ema_alignment": a["indicators"]["ema_alignment"], "action": s["action"],
                "swept": (a["context"]["liquidity"]["swept"] or "none"),
                "waiting": [w["label"] for w in s["waiting_for"] if not w["done"]]}
    r1, r2 = row(a1, i1, f1), row(a2, i2, f2)
    stronger = None
    if r1["trend"] != r2["trend"]:
        stronger = r1["symbol"] if r1["trend"] == "bullish" or r2["trend"] == "bearish" else r2["symbol"]
    txt = (f"{r1['name']} ({r1['action']}): {r1['trend']} structure, RSI {r1['rsi']}, ATR {r1['atr_pct']}%.\n"
           f"{r2['name']} ({r2['action']}): {r2['trend']} structure, RSI {r2['rsi']}, ATR {r2['atr_pct']}%.\n")
    if stronger:
        txt += f"On structure alone, {stronger} currently has the stronger setup. "
    else:
        txt += "Both share the same structural trend, so the difference comes down to confirmation and volatility. "
    txt += "Different volatility means the same stop distance risks very different amounts. This is a comparison of current chart conditions, not a forecast."
    return {"text": txt, "rows": [r1, r2]}


def what_changed(prev: dict, cur: dict, f: Fmt) -> str:
    changes = []
    if prev["structure"]["trend"] != cur["structure"]["trend"]:
        changes.append(f"structure trend moved from {prev['structure']['trend']} to {cur['structure']['trend']}")
    if prev["signal"]["action"] != cur["signal"]["action"]:
        changes.append(f"status changed from {prev['signal']['action']} to {cur['signal']['action']}")
    p_sw, c_sw = prev["liquidity"]["recent_sweep"], cur["liquidity"]["recent_sweep"]
    if (c_sw and c_sw["id"]) != (p_sw and p_sw["id"]):
        changes.append("a new liquidity sweep was registered" if c_sw else "the previous sweep is no longer recent")
    pe, ce = prev["structure"]["events"], cur["structure"]["events"]
    if len(ce) > len(pe) or (ce and pe and ce[-1]["id"] != pe[-1]["id"]):
        e = ce[-1]
        changes.append(f"a new {e['direction']} {e['type']} printed at {f.price(e['level'])}")
    if len(cur["fvg"]) != len(prev["fvg"]):
        changes.append("the set of open fair value gaps changed")
    ch = (cur["price"] - prev["price"]) / prev["price"] * 100 if prev["price"] else 0
    head = f"Price moved {f.pct(ch)} on the latest candle ({f.price(prev['price'])} to {f.price(cur['price'])})."
    return head + (" Since the previous candle: " + "; ".join(changes) + "." if changes
                   else " The structure, liquidity and status are unchanged from the previous candle.")


# --------------------------------------------------------------------------- "Why?" on a chart object
def explain_ref(kind: str, id_: str, a: dict, f: Fmt) -> Optional[str]:
    if kind == "liquidity":
        l = next((x for x in a["liquidity"]["levels"] if x["id"] == id_), None)
        if not l:
            return None
        meaning = {"PDH": "the previous day's high", "PDL": "the previous day's low", "PWH": "the previous week's high",
                   "PWL": "the previous week's low", "BSL": "a swing high", "SSL": "a swing low",
                   "EQH": "a cluster of equal highs", "EQL": "a cluster of equal lows"}[l["kind"]]
        side = "buy-side" if l["side"] == "buy_side" else "sell-side"
        base = (f"{l['kind']} at {f.price(l['price'])} marks {meaning}. Stop orders tend to rest "
                f"{'above' if l['side'] == 'buy_side' else 'below'} such levels, which is why it is called {side} liquidity.")
        if l["status"] == "swept":
            return base + (f" Price traded {'above' if l['side'] == 'buy_side' else 'below'} it with a wick and then closed back "
                           "inside, which is what a sweep looks like. A sweep is a clue, not a signal by itself.")
        return base + " It has not been touched yet, so price may be drawn toward it."
    if kind == "structure":
        e = next((x for x in a["structure"]["events"] if x["id"] == id_), None)
        if not e:
            return None
        what = ("a break of structure: price closed through a swing level in the direction of the existing trend, "
                "which usually signals continuation" if e["type"] == "BOS" else
                "a change of character: price closed through a swing level against the prior trend, "
                "the first sign the trend may be turning")
        return f"This {e['direction']} {e['type']} is {what}. The level broken was {f.price(e['level'])}."
    if kind == "fvg":
        g = next((x for x in a["fvg"] if x["id"] == id_), None)
        if not g:
            return None
        return (f"A {g['type']} fair value gap between {f.price(g['low'])} and {f.price(g['high'])}: a three-candle "
                f"imbalance where price moved fast enough to leave an unbalanced zone. Status: {g['status'].replace('_', ' ')}. "
                "Price often returns to fill part of such zones; whether it respects them is not guaranteed.")
    if kind == "plan":
        p = a["plan"]
        if id_ == "stop":
            return (f"The invalidation sits at {f.price(p['stop'])}: beyond the structural level that the idea depends on, "
                    f"plus a buffer of {p['assumptions']['stop_atr_buffer']:g} ATR. If price gets there, the premise of the setup is wrong.")
        if id_ == "targets":
            return ("Targets are placed at multiples of the risk distance (" +
                    ", ".join(f"{r:g}R" for r in p["rr"]) + "). A note flags where a target sits near liquidity. They are scenarios, not forecasts.")
        return (f"Entry reference is {f.price(p['entry'])} ({p['assumptions']['entry_basis']}). "
                f"Status: {'active' if p['status'] == 'active' else 'conditional, waiting for confirmation'}.")
    if kind == "indicator":
        i = a["indicators"]
        return {"rsi": f"RSI is {i['rsi']}: above 50 leans bullish, below 50 bearish; above 70 or below 30 is stretched.",
                "ema50": f"EMA 20 is {f.price(i['ema20'])} and EMA 50 is {f.price(i['ema50'])}; alignment is {i['ema_alignment']}.",
                "ema20": f"EMA 20 is {f.price(i['ema20'])}; pullbacks in a trend often pause near it.",
                "volume": f"Volume is {i['volume_ratio']}x its 20-bar average; moves on above-average volume are better confirmed."}.get(id_)
    return None
