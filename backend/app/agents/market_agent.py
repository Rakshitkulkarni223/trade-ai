"""MarketAgent: the only agent that touches the network. Fetches candles and a quote."""
from __future__ import annotations

from typing import Optional

from ..services import market_service
from ..services.providers import DataError
from .common import Finding, when


async def run(symbol: str, timeframe: str, limit: int = 500) -> tuple[Finding, dict]:
    """Returns (finding, raw) where raw has instrument, candles, data_status. Raises DataError."""
    raw = await market_service.get_candles(symbol, timeframe, limit)
    quote: Optional[dict] = None
    try:
        quote = await market_service.get_quote(symbol)
    except DataError:
        pass                                            # quote is a nicety; candles are what we analyse
    inst, status = raw["instrument"], raw["data_status"]
    facts = [f"{inst.name} ({inst.symbol}) on {timeframe}, {len(raw['candles'])} candles, "
             f"latest candle opened {when(status['as_of'])}."]
    if status["note"]:
        facts.append(status["note"])
    raw["quote"] = quote
    return Finding("market", f"{inst.name} {timeframe}", facts,
                   {"data_status": status, "quote": quote, "category": inst.category}), raw
