from __future__ import annotations

from .common import Finding, Fmt


def run(a: dict, f: Fmt) -> Finding:
    p, s = a["plan"], a["signal"]
    if s["action"] == "WAIT":
        # No setup, no levels: showing a "what if" entry and stop invites people to trade something that is not there.
        return Finding("risk", "No active setup",
                       ["No entry, stop or targets are shown because no setup is confirmed.",
                        "They appear only when every required condition is met on a closed candle."],
                       {"plan": None, "signal_action": "WAIT"}, [])
    st = s.get("state")
    lead = "Plan"
    facts = [
        f"{lead} ({p['direction'].upper()}): entry {f.price(p['entry'])}, invalidation {f.price(p['stop'])}.",
        "Targets: " + ", ".join(f"{t['name']} {f.price(t['price'])} ({t['r']:g}R)" for t in p["targets"]) + ".",
        f"Risk per unit {f.price(p['risk_per_unit'])}.",
    ]
    sz = p["sizing"]
    if sz["quantity"]:
        facts.append(f"With an account of {f.price(p['assumptions']['equity'])} risking "
                     f"{p['assumptions']['max_risk_per_trade_pct']:g}%, size is {sz['quantity']:g} units "
                     f"(about {f.price(sz['position_value'])}, {sz['position_pct']:.1f}% of the account)."
                     + (" Capped by the maximum position size." if sz["capped"] else ""))
    if st:
        facts.append(f"Triggered {st['age_bars']} candle(s) ago; the levels stay fixed until the stop is hit, the last target "
                     "is reached, 30 candles pass, or the Supertrend turns against it.")
    facts += p["warnings"]
    facts.append(p["disclaimer"])
    return Finding("risk", "Entry, invalidation and targets", facts,
                   {"plan": p, "signal_action": s["action"]},
                   [{"kind": "plan", "id": "plan"}])
