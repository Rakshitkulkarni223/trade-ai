"""Cached access to candles and quotes, plus the data-freshness verdict the AI must respect."""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from . import providers, universe
from .cache import get_cache
from .providers import DataError, TIMEFRAMES

CANDLE_TTL = {"1m": 5, "5m": 8, "15m": 10, "30m": 15, "1H": 15, "4H": 30, "1D": 60, "1W": 300}
QUOTE_TTL = 10
DEFAULT_LIMIT = 500


def validate_timeframe(tf: str) -> str:
    if tf not in TIMEFRAMES:
        raise DataError(f"Unsupported timeframe '{tf}'. Use one of: {', '.join(TIMEFRAMES)}.")
    return tf


def freshness(inst: universe.Instrument, tf: str, last_t: int, now: Optional[float] = None) -> dict:
    age = int((now or time.time()) - last_t)
    tf_s = TIMEFRAMES[tf]
    # Exchange-traded instruments sleep overnight and at weekends; do not call that "stale".
    grace = 0 if inst.category == "Crypto" else (4 * 86400 if tf_s < 86400 else 6 * 86400)
    stale = age > 3 * tf_s + grace
    note = None
    if stale:
        note = "The latest candle is much older than expected for this timeframe; data may be delayed."
    elif inst.category != "Crypto" and age > 3 * tf_s:
        note = "Market appears to be closed; the last candle is from the previous session."
    return {"as_of": last_t, "age_seconds": age, "stale": stale, "note": note}


async def get_candles(symbol: str, tf: str, limit: int = DEFAULT_LIMIT) -> dict:
    tf = validate_timeframe(tf)
    inst = universe.resolve(symbol)
    key = f"candles:{inst.symbol}:{tf}:{limit}"
    cache = get_cache()
    rows = cache.get(key)
    if rows is None:
        fetch = providers.binance_candles if inst.provider == "binance" else providers.yahoo_candles
        rows = await fetch(inst, tf, limit)
        if not rows:
            raise DataError(f"No candles returned for {inst.symbol}.")
        cache.set(key, rows, CANDLE_TTL[tf])
    return {"instrument": inst, "timeframe": tf, "candles": rows,
            "data_status": freshness(inst, tf, rows[-1]["t"])}


async def get_quote(symbol: str) -> dict:
    inst = universe.resolve(symbol)
    key = f"quote:{inst.symbol}"
    cache = get_cache()
    q = cache.get(key)
    if q is None:
        q = await (providers.binance_quote(inst) if inst.provider == "binance" else providers.yahoo_quote(inst))
        q["as_of"] = int(time.time())
        cache.set(key, q, QUOTE_TTL)
    return {"symbol": inst.symbol, "name": inst.name, "currency": inst.currency,
            "currency_symbol": universe.CURRENCY_SYMBOL.get(inst.currency, ""), **q}


async def get_quotes(symbols: list[str]) -> list[dict]:
    """Quotes for many symbols concurrently; a failing symbol yields an error row, not an exception."""
    async def one(s: str) -> dict:
        try:
            return await get_quote(s)
        except DataError as exc:
            return {"symbol": s, "error": str(exc)}
    return list(await asyncio.gather(*(one(s) for s in symbols)))


async def get_depth(symbol: str) -> dict:
    inst = universe.resolve(symbol)
    if inst.provider != "binance":
        raise DataError("Market depth is only available for crypto instruments.")
    return {"symbol": inst.symbol, **await providers.binance_depth(inst)}
