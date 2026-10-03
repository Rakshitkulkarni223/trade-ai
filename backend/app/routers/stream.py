from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import universe, websocket_service as ws_svc
from ..services.providers import DataError, TIMEFRAMES

router = APIRouter(tags=["stream"])
log = logging.getLogger("tradeai.stream")


@router.websocket("/ws/market/{symbol}")
async def market_stream(ws: WebSocket, symbol: str, timeframe: str = "1H") -> None:
    await ws.accept()
    if timeframe not in TIMEFRAMES:
        await ws.send_json({"type": "status", "state": "error", "message": f"Unsupported timeframe {timeframe}."})
        await ws.close()
        return
    inst = universe.resolve(symbol)

    async def send(msg: dict) -> None:
        await ws.send_json(msg)

    async def watch_client() -> None:           # returns when the browser disconnects
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            while True:
                await ws.receive_text()

    feed = asyncio.create_task(ws_svc.relay_binance(inst, timeframe, send) if inst.provider == "binance"
                               else ws_svc.poll_yahoo(inst, send))
    gone = asyncio.create_task(watch_client())
    try:
        done, _ = await asyncio.wait({feed, gone}, return_when=asyncio.FIRST_COMPLETED)
        if feed in done and feed.exception():
            exc = feed.exception()
            if isinstance(exc, DataError):
                with contextlib.suppress(Exception):
                    await ws.send_json({"type": "status", "state": "error", "message": str(exc)})
            elif not isinstance(exc, (WebSocketDisconnect, RuntimeError)):
                log.warning("stream for %s ended: %r", symbol, exc)
    finally:
        for t in (feed, gone):
            t.cancel()
        with contextlib.suppress(Exception):
            await ws.close()
