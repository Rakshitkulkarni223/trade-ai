from __future__ import annotations

from fastapi import APIRouter

from ..schemas.requests import ScanRequest, ScreenerQuery
from ..services import nl_rules, scanner_service

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.post("")
async def screen(req: ScanRequest) -> dict:
    rules = req.rules or scanner_service.rules_from_filters(req.filters, req.direction)
    return await scanner_service.scan(req.market, req.timeframe, rules, req.symbols)


@router.post("/parse")
async def parse(req: ScreenerQuery) -> dict:
    """Show the structured rules a plain-English query turns into, without running it."""
    return await nl_rules.parse(req.query)


@router.post("/query")
async def query(req: ScreenerQuery) -> dict:
    parsed = await nl_rules.parse(req.query)
    out = await scanner_service.scan(parsed["market"], req.timeframe, parsed["rules"])
    out["parsed"] = parsed
    return out
