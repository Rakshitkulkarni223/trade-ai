from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..agents import orchestrator

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

TF = "^(1m|5m|15m|30m|1H|4H|1D|1W)$"


async def _run(symbol: str, timeframe: str, account_size: Optional[float], risk_pct: Optional[float]):
    cfg = orchestrator.risk_config({"equity": account_size, "max_risk_per_trade_pct": risk_pct})
    return await orchestrator.run_analysis(symbol, timeframe, cfg)


@router.get("/{symbol}")
async def full(symbol: str, timeframe: str = Query("1H", pattern=TF),
               account_size: Optional[float] = Query(None, gt=0),
               risk_pct: Optional[float] = Query(None, gt=0, le=10)) -> dict:
    """Everything the chart needs: indicator series, overlays with timestamps, signal and plan."""
    run = await _run(symbol, timeframe, account_size, risk_pct)
    return {"instrument": run.inst.public(), "quote": run.quote, "data_status": run.status, **run.a}


@router.get("/{symbol}/liquidity")
async def liquidity(symbol: str, timeframe: str = Query("1H", pattern=TF)) -> dict:
    run = await _run(symbol, timeframe, None, None)
    return {"symbol": run.inst.symbol, "price": run.a["price"], "data_status": run.status, **run.a["liquidity"]}


@router.get("/{symbol}/structure")
async def structure(symbol: str, timeframe: str = Query("1H", pattern=TF)) -> dict:
    run = await _run(symbol, timeframe, None, None)
    return {"symbol": run.inst.symbol, "data_status": run.status, **run.a["structure"]}


@router.get("/{symbol}/fvg")
async def fvg(symbol: str, timeframe: str = Query("1H", pattern=TF)) -> dict:
    run = await _run(symbol, timeframe, None, None)
    return {"symbol": run.inst.symbol, "data_status": run.status, "fvg": run.a["fvg"]}


@router.get("/{symbol}/indicators")
async def indicators(symbol: str, timeframe: str = Query("1H", pattern=TF)) -> dict:
    run = await _run(symbol, timeframe, None, None)
    return {"symbol": run.inst.symbol, "data_status": run.status, "indicators": run.a["indicators"]}
