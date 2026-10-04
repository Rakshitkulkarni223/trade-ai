"""Cached access to candles and quotes, plus the data-freshness verdict the AI must respect."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from . import providers, universe
from .cache import get_cache
from .providers import DataError, TIMEFRAMES

CANDLE_TTL = {"1m": 5, "5m": 8, "15m": 10, "30m": 15, "1H": 15, "4H": 30, "1D": 60, "1W": 300}
QUOTE_TTL = 10
DEFAULT_LIMIT = 500

SETTLE_SECONDS = 30 * 60          # right after the open, the last trade is still yesterday's: do not call that "closed"
STALE_TRADE_SECONDS = 30 * 60     # inside regular hours but no trade for this long => the market is not really trading
META_MAX_AGE = 5 * 60             # re-read the session window at most this often
CLOSED_TTL_MAX = 15 * 60


def evaluate_session(rec: dict, now: float) -> dict:
    """Open = inside the regular session AND traded recently. The second test matters for futures, whose metadata
    reports a nominal 'Sunday to Monday' session even though nothing has traded since Friday."""
    start, end, last = rec["start"], rec["end"], rec.get("last_trade")
    if not (start <= now < end):
        return {"open": False, "opens_at": start if now < start else None}
    if last is not None and now - start > SETTLE_SECONDS and now - last > STALE_TRADE_SECONDS:
        return {"open": False, "opens_at": None}
    return {"open": True, "closes_at": end}


async def market_status(inst: universe.Instrument, now: Optional[float] = None) -> dict:
    """{"open": bool, "known": bool, "opens_at": ts|None}. Crypto never closes. If the session cannot be determined the
    market is assumed open, so updates are never silently switched off on a guess."""
    now = time.time() if now is None else now
    if inst.provider == "binance":
        return {"open": True, "known": True}
    rec = providers.MARKET_META.get(inst.symbol)
    if rec is None or now - rec["fetched_at"] > META_MAX_AGE:
        try:
            res = await providers._yahoo_chart(inst.symbol, "1d", "1d")
            providers.remember_meta(inst.symbol, res.get("meta", {}))
            rec = providers.MARKET_META.get(inst.symbol)
        except DataError:
            pass
    if rec is None:
        return {"open": True, "known": False}
    return {**evaluate_session(rec, now), "known": True}


def closed_ttl(status: dict, now: Optional[float] = None) -> float:
    """While a market is closed nothing can change, so answers can be cached for a long time, but never past the open."""
    now = time.time() if now is None else now
    opens = status.get("opens_at")
    return max(30.0, min(CLOSED_TTL_MAX, opens - now)) if opens else 300.0


def validate_timeframe(tf: str) -> str:
    if tf not in TIMEFRAMES:
        raise DataError(f"Unsupported timeframe '{tf}'. Use one of: {', '.join(TIMEFRAMES)}.")
    return tf


def freshness(inst: universe.Instrument, tf: str, last_t: int, now: Optional[float] = None,
              market: Optional[dict] = None) -> dict:
    age = int((now or time.time()) - last_t)
    if market and market.get("known") and not market["open"]:
        opens = market.get("opens_at")
        try:
            when = (" It opens " + datetime.fromtimestamp(opens, tz=timezone.utc).strftime("%a %H:%M UTC") + ".") if opens else ""
        except (OverflowError, OSError, ValueError):     # a nonsense timestamp from the provider must not break the page
            when = ""
        return {"as_of": last_t, "age_seconds": age, "stale": False, "market_open": False, "opens_at": opens,
                "note": "Market is closed. Showing the last session; live updates are paused until it opens." + when}
    tf_s = TIMEFRAMES[tf]
    # Exchange-traded instruments sleep overnight and at weekends; do not call that "stale".
    grace = 0 if inst.category == "Crypto" else (4 * 86400 if tf_s < 86400 else 6 * 86400)
    stale = age > 3 * tf_s + grace
    note = None
    if stale:
        note = "The latest candle is much older than expected for this timeframe; data may be delayed."
    elif inst.category != "Crypto" and age > 3 * tf_s:
        note = "Market appears to be closed; the last candle is from the previous session."
    return {"as_of": last_t, "age_seconds": age, "stale": stale, "note": note,
            "market_open": True if (market and market.get("known")) else None, "opens_at": None}


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
        status = await market_status(inst)
        cache.set(key, rows, closed_ttl(status) if (status["known"] and not status["open"]) else CANDLE_TTL[tf])
    market = await market_status(inst)
    return {"instrument": inst, "timeframe": tf, "candles": rows,
            "data_status": freshness(inst, tf, rows[-1]["t"], market=market)}


async def get_quote(symbol: str) -> dict:
    inst = universe.resolve(symbol)
    key = f"quote:{inst.symbol}"
    cache = get_cache()
    q = cache.get(key)
    if q is None:
        q = await (providers.binance_quote(inst) if inst.provider == "binance" else providers.yahoo_quote(inst))
        q["as_of"] = int(time.time())
        status = await market_status(inst)
        cache.set(key, q, closed_ttl(status) if (status["known"] and not status["open"]) else QUOTE_TTL)
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
