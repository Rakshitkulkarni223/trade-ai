"""Natural-language screener query -> structured rules.

With an LLM configured it asks for JSON and validates every key; otherwise (or on any doubt) a
regex parser handles the common phrasings. Either way the user sees the rules that were derived.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from . import llm

ALLOWED = {"trend": {"bullish", "bearish", "neutral"}, "sweep": {"sell_side", "buy_side", "any"},
           "bos": {"bullish", "bearish"}, "choch": {"bullish", "bearish"}, "fvg": {"bullish", "bearish", "any"},
           "ema_alignment": {"bullish", "bearish"}, "action": {"LONG", "SHORT", "WAIT", "SETUP"}}
NUMERIC = {"rsi_min", "rsi_max", "atr_pct_min", "atr_pct_max", "volume_ratio_min", "vwap_distance_pct_max",
           "price_min", "price_max"}
BOOL = {"above_ema50"}
MARKETS = {"India", "US", "Crypto", "Indices", "Metals", "All"}


def validate(raw: dict) -> dict:
    rules = {}
    for k, v in raw.items():
        if k in ALLOWED and isinstance(v, str) and v in ALLOWED[k]:
            rules[k] = v
        elif k in NUMERIC and isinstance(v, (int, float)) and not isinstance(v, bool):
            rules[k] = float(v)
        elif k in BOOL and isinstance(v, bool):
            rules[k] = v
    return rules


def parse_regex(text: str) -> tuple[Optional[str], dict]:
    t = text.lower()
    rules: dict = {}
    market = None
    if re.search(r"\bindia|indian|nse|nifty", t):
        market = "India"
    elif re.search(r"\bus\b|american|nasdaq|nyse|s&p", t):
        market = "US"
    elif re.search(r"crypto|bitcoin|coin", t):
        market = "Crypto"
    elif re.search(r"metal|gold|silver", t):
        market = "Metals"
    elif "index" in t or "indices" in t:
        market = "Indices"

    if re.search(r"bullish (market )?(structure|trend)|uptrend", t):
        rules["trend"] = "bullish"
    elif re.search(r"bearish (market )?(structure|trend)|downtrend", t):
        rules["trend"] = "bearish"
    m = re.search(r"(sell|buy)[- ]?side (liquidity )?sweep", t)
    if m:
        rules["sweep"] = f"{m.group(1)}_side"
    elif re.search(r"liquidity sweep|swept liquidity|stop hunt", t):
        rules["sweep"] = "any"
    m = re.search(r"(bullish|bearish) choch", t)
    if m:
        rules["choch"] = m.group(1)
    m = re.search(r"(bullish|bearish) bos", t)
    if m:
        rules["bos"] = m.group(1)
    m = re.search(r"(bullish|bearish)? ?(fvg|fair value gap)", t)
    if m:
        rules["fvg"] = m.group(1) or "any"
    m = re.search(r"rsi (?:is )?between (\d+(?:\.\d+)?) (?:and|&|-|to) (\d+(?:\.\d+)?)", t)
    if m:
        rules["rsi_min"], rules["rsi_max"] = float(m.group(1)), float(m.group(2))
    else:
        m = re.search(r"rsi (?:is )?(?:above|over|greater than|>) (\d+(?:\.\d+)?)", t)
        if m:
            rules["rsi_min"] = float(m.group(1))
        m = re.search(r"rsi (?:is )?(?:below|under|less than|<) (\d+(?:\.\d+)?)", t)
        if m:
            rules["rsi_max"] = float(m.group(1))
    m = re.search(r"volume (?:is )?(?:above|over|higher than) (?:the )?average", t)
    if m:
        rules["volume_ratio_min"] = 1.0
    m = re.search(r"volume (?:is )?(?:at least |above |over )?(\d+(?:\.\d+)?)x", t)
    if m:
        rules["volume_ratio_min"] = float(m.group(1))
    if re.search(r"(price )?(is )?above (the )?(ema ?50|50 ?ema|50 ?-?day ema)", t):
        rules["above_ema50"] = True
    elif re.search(r"(price )?(is )?below (the )?(ema ?50|50 ?ema)", t):
        rules["above_ema50"] = False
    m = re.search(r"atr (?:is )?(?:above|over) (\d+(?:\.\d+)?)", t)
    if m:
        rules["atr_pct_min"] = float(m.group(1))
    m = re.search(r"atr (?:is )?(?:below|under) (\d+(?:\.\d+)?)", t)
    if m:
        rules["atr_pct_max"] = float(m.group(1))
    m = re.search(r"within (\d+(?:\.\d+)?)% of vwap", t)
    if m:
        rules["vwap_distance_pct_max"] = float(m.group(1))
    if re.search(r"ema (alignment )?(is )?bullish|bullish ema", t):
        rules["ema_alignment"] = "bullish"
    return market, rules


async def parse(text: str) -> dict:
    market, rules = parse_regex(text)
    source = "rules"
    provider = llm.get_provider()
    if provider is not None:
        prompt = ("Convert the screening request into JSON with optional keys: market (India|US|Crypto|Indices|Metals|All), "
                  "trend (bullish|bearish|neutral), sweep (sell_side|buy_side|any), bos, choch (bullish|bearish), "
                  "fvg (bullish|bearish|any), ema_alignment (bullish|bearish), above_ema50 (bool), rsi_min, rsi_max, "
                  "atr_pct_min, atr_pct_max, volume_ratio_min, vwap_distance_pct_max, price_min, price_max (numbers). "
                  f"Reply with JSON only.\nRequest: {text}")
        try:
            out = await provider.complete("You translate stock screening requests into JSON. Output JSON only.",
                                          [{"role": "user", "content": prompt}], 300)
            m = re.search(r"\{.*\}", out, re.S)
            if m:
                data = json.loads(m.group(0))
                parsed = validate(data)
                if parsed:
                    rules, source = parsed, provider.name
                    if data.get("market") in MARKETS:
                        market = data["market"]
        except Exception:
            pass                                    # fall back to the regex result
    return {"market": market or "All", "rules": rules, "source": source}
