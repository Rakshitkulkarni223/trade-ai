"""Paper analysis: follow an AI plan on paper and see what the later candles did to it.
No orders exist anywhere in this application; outcomes are computed from market data."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import orchestrator
from ..db import models
from ..db.database import get_session
from ..schemas.requests import TrackSetup
from ..services import market_service, outcome
from ..services.providers import DataError

router = APIRouter(prefix="/api/paper", tags=["paper-analysis"])


def _public(s: models.TrackedSetup, result: dict | None) -> dict:
    return {"id": s.id, "symbol": s.symbol, "timeframe": s.timeframe, "direction": s.direction, "entry": s.entry,
            "stop": s.stop, "targets": s.targets, "created_at": s.created_at, "entry_t": s.entry_t,
            "note": s.note, "evidence": s.evidence, "result": result}


@router.post("/setups")
async def track(req: TrackSetup, db: Session = Depends(get_session)) -> dict:
    cfg = orchestrator.risk_config({"equity": req.account_size, "max_risk_per_trade_pct": req.max_risk_per_trade_pct,
                                    "max_position_pct": req.max_position_pct})
    run = await orchestrator.run_analysis(req.symbol, req.timeframe, cfg, with_quote=False)
    plan, sig = run.a["plan"], run.a["signal"]
    if sig["action"] == "WAIT":
        raise HTTPException(422, "Nothing to track yet: the current status is WAIT, so there is no active plan. "
                                 "Track a setup once the required confirmations are in.")
    row = models.TrackedSetup(symbol=run.inst.symbol, timeframe=req.timeframe, direction=plan["direction"],
                              entry=plan["entry"], stop=plan["stop"], targets=plan["targets"],
                              entry_t=run.a["as_of"], note=req.note,
                              evidence={"summary": sig["summary"], "for": [i["label"] for i in sig["evidence"]["for"]],
                                        "caution": [i["label"] for i in sig["evidence"]["caution"]]})
    db.add(row)
    db.commit()
    return _public(row, outcome.evaluate(row.direction, row.entry, row.stop, row.targets, [], row.entry_t))


@router.get("/setups")
async def list_setups(db: Session = Depends(get_session)) -> dict:
    rows = db.scalars(select(models.TrackedSetup).order_by(models.TrackedSetup.id.desc())).all()
    out = []
    for s in rows:
        if s.closed and s.result:
            out.append(_public(s, s.result))
            continue
        try:
            data = await market_service.get_candles(s.symbol, s.timeframe, 500)
            res = outcome.evaluate(s.direction, s.entry, s.stop, s.targets, data["candles"], s.entry_t)
        except DataError as exc:
            res = {"state": "unknown", "closed": False, "note": f"Could not refresh: {exc}"}
        if res.get("closed"):
            s.closed, s.result = 1, res
            db.commit()
        out.append(_public(s, res))
    closed = [o for o in out if o["result"].get("closed") and o["result"].get("realised_r") is not None]
    summary = {"total": len(out), "open": sum(1 for o in out if not o["result"].get("closed")),
               "closed": len(closed), "net_r": round(sum(o["result"]["realised_r"] for o in closed), 2),
               "note": "Idealised study results: fills at plan entry, no fees or slippage, stop wins ties."}
    return {"setups": out, "summary": summary}


@router.delete("/setups/{setup_id}")
def delete(setup_id: int, db: Session = Depends(get_session)) -> dict:
    s = db.get(models.TrackedSetup, setup_id)
    if s is None:
        raise HTTPException(404, "Setup not found.")
    db.delete(s)
    db.commit()
    return {"deleted": setup_id}
