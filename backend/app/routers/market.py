from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..services import market_service, universe
from ..services.providers import TIMEFRAMES

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/universe")
def get_universe() -> dict:
    cats = []
    for key, label in universe.CATEGORY_LABELS.items():
        cats.append({"id": key, "label": label,
                     "instruments": [i.public() for i in universe.INSTRUMENTS if i.category == key]})
    return {"categories": cats, "timeframes": list(TIMEFRAMES)}


@router.get("/search")
def search(q: str = Query("", max_length=40)) -> dict:
    return {"results": [i.public() for i in universe.search(q)]}


@router.get("/pulse")
async def pulse() -> dict:
    """Headline quotes for the home page."""
    symbols = ["^NSEI", "BTCUSDT", "^GSPC", "ETHUSDT"]
    return {"quotes": await market_service.get_quotes(symbols)}


class QuotesRequest(BaseModel):
    symbols: list[str] = Field(max_length=60)


@router.post("/quotes")
async def quotes(req: QuotesRequest) -> dict:
    return {"quotes": await market_service.get_quotes(req.symbols)}


@router.get("/{symbol}/quote")
async def quote(symbol: str) -> dict:
    return await market_service.get_quote(symbol)


@router.get("/{symbol}/history")
async def history(symbol: str, timeframe: str = Query("1H", pattern="^(1m|5m|15m|30m|1H|4H|1D|1W)$"),
                  limit: int = Query(500, ge=50, le=1000)) -> dict:
    r = await market_service.get_candles(symbol, timeframe, limit)
    return {"instrument": r["instrument"].public(), "timeframe": timeframe,
            "candles": r["candles"], "data_status": r["data_status"]}


@router.get("/{symbol}/depth")
async def depth(symbol: str) -> dict:
    return await market_service.get_depth(symbol)
