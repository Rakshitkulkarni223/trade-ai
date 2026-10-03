from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import orchestrator
from ..db import models
from ..db.database import get_session
from ..schemas.requests import WatchlistAdd
from ..services import market_service, scanner_service, universe
from ..services.providers import DataError

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

DEFAULTS = ["BTCUSDT", "ETHUSDT", "RELIANCE.NS", "TCS.NS", "AAPL"]


def seed_defaults(db: Session) -> None:
    if db.scalar(select(models.WatchlistItem).limit(1)) is None:
        for i, s in enumerate(DEFAULTS):
            db.add(models.WatchlistItem(symbol=s, position=i))
        db.commit()


async def _row(symbol: str, timeframe: str) -> dict:
    inst = universe.resolve(symbol)
    row: dict = {"symbol": inst.symbol, "name": inst.name, "category": inst.category,
                 "currency_symbol": universe.CURRENCY_SYMBOL.get(inst.currency, "")}
    try:
        q = await market_service.get_quote(symbol)
        row.update(price=q["price"], change_pct=q["change_pct"])
    except DataError as exc:
        row["error"] = str(exc)
    try:
        run = await orchestrator.run_analysis(symbol, timeframe, with_quote=False, limit=300)
        ft = scanner_service.features(run)
        row.update(trend=ft["trend"], liquidity=("swept " + ft["sweep"].replace("_", "-")) if ft["sweep"] else "—",
                   status=ft["action"], summary=run.a["signal"]["summary"])
        row.setdefault("price", run.a["price"])
    except DataError:
        row.update(trend=None, liquidity=None, status=None)
    return row


@router.get("")
async def get_watchlist(timeframe: str = Query("1H", pattern="^(1m|5m|15m|30m|1H|4H|1D|1W)$"),
                        db: Session = Depends(get_session)) -> dict:
    seed_defaults(db)
    items = db.scalars(select(models.WatchlistItem).order_by(models.WatchlistItem.position,
                                                            models.WatchlistItem.added_at)).all()
    rows = await asyncio.gather(*(_row(i.symbol, timeframe) for i in items))
    return {"timeframe": timeframe, "items": list(rows)}


@router.post("")
def add(req: WatchlistAdd, db: Session = Depends(get_session)) -> dict:
    inst = universe.resolve(req.symbol)
    if db.get(models.WatchlistItem, inst.symbol) is None:
        n = len(db.scalars(select(models.WatchlistItem)).all())
        db.add(models.WatchlistItem(symbol=inst.symbol, position=n))
        db.commit()
    return {"symbol": inst.symbol}


@router.delete("/{symbol}")
def remove(symbol: str, db: Session = Depends(get_session)) -> dict:
    item: Optional[models.WatchlistItem] = db.get(models.WatchlistItem, universe.resolve(symbol).symbol)
    if item is None:
        raise HTTPException(404, "Not in the watchlist.")
    db.delete(item)
    db.commit()
    return {"removed": item.symbol}
