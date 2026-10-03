"""Live market feed relayed to the browser.

Crypto: Binance's public kline stream (a full, updating candle every second or so).
Stocks / indices / metals: Yahoo has no free stream, so the last price is polled every few seconds and
sent as a tick. The browser only ever talks to this backend; no keys or third-party sockets leak to it.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

import websockets

from . import providers
from .providers import BINANCE_INTERVAL, DataError
from .universe import Instrument

log = logging.getLogger("tradeai.stream")

BINANCE_STREAMS = ["wss://stream.binance.com:9443/ws", "wss://data-stream.binance.vision/ws", "wss://stream.binance.us:9443/ws"]
YAHOO_POLL_SECONDS = 5

Send = Callable[[dict], Awaitable[None]]


async def relay_binance(inst: Instrument, timeframe: str, send: Send) -> None:
    """Forward kline updates until the client goes away (send raises) or every host has failed."""
    stream = f"{inst.symbol.lower()}@kline_{BINANCE_INTERVAL[timeframe]}"
    last: Optional[Exception] = None
    for host in BINANCE_STREAMS:
        try:
            async with websockets.connect(f"{host}/{stream}", ping_interval=20, open_timeout=8) as up:
                await send({"type": "hello", "mode": "stream", "source": "binance"})
                async for raw in up:
                    k = json.loads(raw).get("k")
                    if not k:
                        continue
                    await send({"type": "kline", "closed": bool(k["x"]),
                                "candle": {"t": k["t"] // 1000, "o": float(k["o"]), "h": float(k["h"]),
                                           "l": float(k["l"]), "c": float(k["c"]), "v": float(k["v"])}})
                return
        except (OSError, websockets.WebSocketException, asyncio.TimeoutError) as exc:
            last = exc
            log.warning("binance stream %s failed: %s", host, exc)
    raise DataError(f"Live crypto stream unavailable ({last}).")


async def poll_yahoo(inst: Instrument, send: Send, seconds: int = YAHOO_POLL_SECONDS) -> None:
    await send({"type": "hello", "mode": "poll", "source": "yahoo", "interval_s": seconds})
    while True:
        try:
            q = await providers.yahoo_quote(inst)          # bypasses the cache on purpose
            await send({"type": "tick", "price": q["price"], "change_pct": q["change_pct"]})
        except DataError as exc:
            await send({"type": "status", "state": "error", "message": str(exc)})
        await asyncio.sleep(seconds)
