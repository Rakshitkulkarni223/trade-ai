from __future__ import annotations

from .common import Finding, Fmt, bars_ago


def run(a: dict, f: Fmt) -> Finding:
    liq, n = a["liquidity"], a["bars"]
    facts, refs = [], []
    ts = a["series"]["t"]
    nb, ns, sw = liq["nearest_buy_side"], liq["nearest_sell_side"], liq["recent_sweep"]
    if nb:
        facts.append(f"Nearest buy-side liquidity (above): {nb['kind']} at {f.price(nb['price'])}.")
        refs.append({"kind": "liquidity", "id": nb["id"]})
    if ns:
        facts.append(f"Nearest sell-side liquidity (below): {ns['kind']} at {f.price(ns['price'])}.")
        refs.append({"kind": "liquidity", "id": ns["id"]})
    if sw:
        idx = ts.index(sw["swept_t"]) if sw["swept_t"] in ts else None
        ago = (n - 1 - idx) if idx is not None else None
        side = "Sell-side" if sw["side"] == "sell_side" else "Buy-side"
        facts.append(f"{side} liquidity ({sw['kind']} {f.price(sw['price'])}) was swept {bars_ago(ago)}: "
                     f"price traded through it and closed back inside.")
        refs.append({"kind": "liquidity", "id": sw["id"]})
    eq = [l for l in liq["levels"] if l["kind"] in ("EQH", "EQL") and l["status"] == "active"]
    for l in eq[:2]:
        facts.append(f"{l['kind']} cluster at {f.price(l['price'])}: equal {'highs' if l['kind'] == 'EQH' else 'lows'} "
                     "tend to attract stop orders.")
    if not facts:
        facts.append("No clear liquidity levels were found in the loaded history.")
    head = "Recent sweep" if sw else "No recent sweep"
    return Finding("liquidity", head, facts, {"levels": liq["levels"]}, refs)
