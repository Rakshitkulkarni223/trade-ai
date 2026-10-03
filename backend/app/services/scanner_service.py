"""Scanner and screener share one pipeline: universe -> analysis -> feature extraction -> rules.

Every result carries the checks that produced it, so a hit is explainable rather than a bare signal.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..agents import orchestrator
from ..services import universe
from ..services.providers import DataError

log = logging.getLogger("tradeai.scanner")

RECENT = 20  # bars that count as "recent" for BOS / CHoCH


def features(run: orchestrator.Run) -> dict:
    a = run.a
    ctx, ind = a["context"], a["indicators"]
    price = a["price"]
    st = ctx["structure"]
    fvg_types = sorted({g["type"] for g in a["fvg"] if g["status"] != "filled"})
    shifts = [i for i in a["signal"]["items"] if i["key"] in ("structure",) and i["state"] == "pass"]
    return {
        "price": price, "trend": a["structure"]["trend"], "rsi": ind["rsi"], "atr_pct": ind["atr_pct"],
        "volume_ratio": ind["volume_ratio"], "ema_alignment": ind["ema_alignment"],
        "above_ema50": (price > ind["ema50"]) if ind["ema50"] else None,
        "vwap_dist_pct": ind["price_vs_vwap_pct"],
        "sweep": ctx["liquidity"]["swept"],
        "bos": st["bos"] if (st["bos_bars_ago"] is not None and st["bos_bars_ago"] <= RECENT) else None,
        "choch": st["choch"] if (st["choch_bars_ago"] is not None and st["choch_bars_ago"] <= RECENT) else None,
        "fvg": fvg_types, "action": a["signal"]["action"], "structure_confirmed": bool(shifts),
    }


def _chk(rule: str, label: str, ok: Optional[bool], detail: str) -> dict:
    return {"rule": rule, "label": label, "ok": bool(ok), "detail": detail}


def evaluate(rules: dict, ft: dict) -> list[dict]:
    """One check per rule. A missing feature (e.g. no volume data) fails the check; it never passes by default."""
    out = []
    g = rules.get
    if g("trend"):
        out.append(_chk("trend", f"{g('trend').capitalize()} structure", ft["trend"] == g("trend"), f"structure is {ft['trend']}"))
    if g("sweep"):
        want = g("sweep")
        ok = ft["sweep"] is not None and (want == "any" or ft["sweep"] == want)
        out.append(_chk("sweep", "Recent liquidity sweep" if want == "any" else f"Recent {want.replace('_', '-')} sweep", ok,
                        f"last sweep: {ft['sweep'] or 'none'}"))
    if g("bos"):
        out.append(_chk("bos", f"Recent {g('bos')} BOS", ft["bos"] == g("bos"), f"recent BOS: {ft['bos'] or 'none'}"))
    if g("choch"):
        out.append(_chk("choch", f"Recent {g('choch')} CHoCH", ft["choch"] == g("choch"), f"recent CHoCH: {ft['choch'] or 'none'}"))
    if g("fvg"):
        want = g("fvg")
        ok = bool(ft["fvg"]) if want == "any" else want in ft["fvg"]
        out.append(_chk("fvg", "Open fair value gap" if want == "any" else f"Open {want} FVG", ok,
                        "open FVGs: " + (", ".join(ft["fvg"]) or "none")))
    if g("rsi_min") is not None or g("rsi_max") is not None:
        lo, hi = g("rsi_min", 0), g("rsi_max", 100)
        v = ft["rsi"]
        out.append(_chk("rsi", f"RSI between {lo:g} and {hi:g}", v is not None and lo <= v <= hi,
                        f"RSI {v if v is not None else 'n/a'}"))
    if g("atr_pct_min") is not None or g("atr_pct_max") is not None:
        lo, hi = g("atr_pct_min", 0), g("atr_pct_max", 1e9)
        v = ft["atr_pct"]
        out.append(_chk("atr", f"ATR {lo:g}%–{hi:g}% of price", v is not None and lo <= v <= hi,
                        f"ATR {v if v is not None else 'n/a'}%"))
    if g("volume_ratio_min") is not None:
        v = ft["volume_ratio"]
        out.append(_chk("volume", f"Volume ≥ {g('volume_ratio_min'):g}x average", v is not None and v >= g("volume_ratio_min"),
                        f"volume {v if v is not None else 'n/a'}x average"))
    if g("above_ema50") is not None:
        want = g("above_ema50")
        v = ft["above_ema50"]
        out.append(_chk("ema50", f"Price {'above' if want else 'below'} EMA 50", v is not None and v == want,
                        "above EMA 50" if v else "below EMA 50" if v is not None else "n/a"))
    if g("ema_alignment"):
        out.append(_chk("ema_alignment", f"EMAs aligned {g('ema_alignment')}", ft["ema_alignment"] == g("ema_alignment"),
                        f"alignment {ft['ema_alignment']}"))
    if g("vwap_distance_pct_max") is not None:
        v = ft["vwap_dist_pct"]
        lim = g("vwap_distance_pct_max")
        out.append(_chk("vwap", f"Within {lim:g}% of VWAP", v is not None and abs(v) <= lim,
                        f"{v if v is not None else 'n/a'}% from VWAP"))
    if g("price_min") is not None or g("price_max") is not None:
        lo, hi = g("price_min", 0), g("price_max", 1e18)
        out.append(_chk("price", "Price in range", lo <= ft["price"] <= hi, f"price {ft['price']}"))
    if g("action"):
        want = g("action")
        ok = ft["action"] != "WAIT" if want == "SETUP" else ft["action"] == want
        out.append(_chk("action", f"Status {want}", ok, f"status {ft['action']}"))
    return out


FILTERS = {
    "sweep": "Liquidity sweep", "structure": "Bullish/bearish structure", "volume": "Volume confirmation",
    "fvg": "Fair value gap", "rsi": "RSI confirmation",
}


def rules_from_filters(filters: list[str], direction: str = "long") -> dict:
    """Translate AI Lab checkboxes into rules. Direction decides which side each filter looks at."""
    long = direction != "short"
    r: dict = {}
    if "sweep" in filters:
        r["sweep"] = "sell_side" if long else "buy_side"
    if "structure" in filters:
        r["trend"] = "bullish" if long else "bearish"
    if "volume" in filters:
        r["volume_ratio_min"] = 1.0
    if "fvg" in filters:
        r["fvg"] = "bullish" if long else "bearish"
    if "rsi" in filters:
        r.update({"rsi_min": 50, "rsi_max": 70} if long else {"rsi_min": 30, "rsi_max": 50})
    return r


async def scan(market: str, timeframe: str, rules: dict, symbols: Optional[list[str]] = None,
               max_symbols: int = 60) -> dict:
    inst_list = [universe.resolve(s) for s in symbols] if symbols else universe.by_market(market)
    inst_list = inst_list[:max_symbols]
    sem = asyncio.Semaphore(6)
    unavailable: list[dict] = []

    async def one(inst: universe.Instrument) -> Optional[dict]:
        async with sem:
            try:
                run = await orchestrator.run_analysis(inst.symbol, timeframe, with_quote=False, limit=400)
            except DataError as exc:
                unavailable.append({"symbol": inst.symbol, "reason": str(exc)})
                return None
            except Exception as exc:  # one bad symbol must not sink the scan
                log.warning("scan failed for %s: %s", inst.symbol, exc)
                unavailable.append({"symbol": inst.symbol, "reason": "analysis failed"})
                return None
        ft = features(run)
        checks = evaluate(rules, ft)
        sig = run.a["signal"]
        plan = run.a["plan"]
        return {
            "symbol": inst.symbol, "name": inst.name, "category": inst.category, "price": ft["price"],
            "currency_symbol": universe.CURRENCY_SYMBOL.get(inst.currency, ""),
            "action": sig["action"], "bias": sig["bias"], "setup_type": sig["setup_type"],
            "summary": sig["summary"], "checks": checks, "matched": all(c["ok"] for c in checks),
            "features": ft,
            "supporting": [i["label"] for i in sig["evidence"]["for"]],
            "waiting_for": [w["label"] for w in sig["waiting_for"] if not w["done"]],
            "plan": {"direction": plan["direction"], "status": plan["status"], "entry": plan["entry"],
                     "stop": plan["stop"], "tp1": plan["targets"][0]["price"]} if sig["action"] != "WAIT" else None,
            "data_status": run.status,
        }

    rows = [r for r in await asyncio.gather(*(one(i) for i in inst_list)) if r]
    matched = [r for r in rows if r["matched"]]
    order = {"LONG": 0, "SHORT": 0, "WAIT": 1}
    matched.sort(key=lambda r: (order[r["action"]], r["symbol"]))
    funnel = {"scanned": len(rows),
              "liquidity_events": sum(1 for r in rows if r["features"]["sweep"]),
              "structure_confirmations": sum(1 for r in rows if r["features"]["structure_confirmed"]),
              "potential_setups": sum(1 for r in rows if r["action"] != "WAIT"),
              "matched": len(matched)}
    return {"market": market, "timeframe": timeframe, "rules": rules, "funnel": funnel,
            "results": matched, "unavailable": unavailable}
