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
    """Offer the starter list exactly once. Seeding whenever the list is empty would bring the defaults back every time
    someone deliberately removes everything."""
    if db.get(models.AppFlag, "watchlist_seeded") is not None:
        return
    if db.scalar(select(models.WatchlistItem).limit(1)) is None:
        for i, s in enumerate(DEFAULTS):
            db.add(models.WatchlistItem(symbol=s, position=i))
    db.add(models.AppFlag(key="watchlist_seeded", value="1"))
    db.commit()


async def resolve_for_watchlist(raw: str) -> universe.Instrument:
    """The instrument a typed ticker really is, or a 422 saying what was tried.
    Catalogue symbols need no check. An unknown bare ticker is also tried as an NSE (.NS) and BSE (.BO) listing, because
    that is what people typing 'ESDS' or 'IRCTC' mean."""
    known = universe.lookup(raw)
    if known:
        return known
    s = raw.strip().upper()
    bare = not any(ch in s for ch in ".^=-") and not s.endswith("USDT")
    candidates = [s] + ([f"{s}.NS", f"{s}.BO"] if bare else [])
    for cand in candidates:
        try:
            await market_service.get_quote(cand)
            return universe.resolve(cand)
        except DataError:
            continue
    hint = f" For Indian stocks add the exchange, e.g. {s}.NS." if bare else ""
    raise HTTPException(422, f"Couldn't find “{raw.strip()}” on Yahoo Finance or Binance (tried {', '.join(candidates)}).{hint}")


async def _row(symbol: str, timeframe: str) -> dict:
    inst = universe.resolve(symbol)
    row: dict = {"symbol": inst.symbol, "name": inst.name, "category": inst.category,
                 "currency_symbol": universe.CURRENCY_SYMBOL.get(inst.currency, "")}
    status = await market_service.market_status(inst)
    row["market_open"] = status["open"] if status.get("known") else None
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


@router.get("/symbols")
def symbols(db: Session = Depends(get_session)) -> dict:
    """Just the symbols, no prices or analysis: cheap enough for every Watch button to ask."""
    seed_defaults(db)
    rows = db.scalars(select(models.WatchlistItem.symbol).order_by(models.WatchlistItem.position)).all()
    return {"symbols": list(rows)}


@router.post("")
async def add(req: WatchlistAdd, db: Session = Depends(get_session)) -> dict:
    inst = await resolve_for_watchlist(req.symbol)
    already = db.get(models.WatchlistItem, inst.symbol) is not None
    if not already:
        n = len(db.scalars(select(models.WatchlistItem)).all())
        db.add(models.WatchlistItem(symbol=inst.symbol, position=n))
        db.commit()
    return {"symbol": inst.symbol, "name": inst.name, "added": not already,
            "resolved_from": req.symbol.strip().upper() if inst.symbol != req.symbol.strip().upper() else None}


@router.delete("/{symbol}")
def remove(symbol: str, db: Session = Depends(get_session)) -> dict:
    item: Optional[models.WatchlistItem] = db.get(models.WatchlistItem, universe.resolve(symbol).symbol)
    if item is None:
        raise HTTPException(404, "Not in the watchlist.")
    db.delete(item)
    db.commit()
    return {"removed": item.symbol}
