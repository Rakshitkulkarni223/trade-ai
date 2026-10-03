from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents import explanation_agent as expl, orchestrator
from ..db.database import get_session
from ..schemas.requests import AnalyzeRequest, ChatRequest, ExplainRequest, ScanRequest
from ..services import llm, scanner_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status")
def status() -> dict:
    p = llm.get_provider()
    return {"provider": p.name if p else "offline", "llm": p is not None,
            "note": None if p else "No LLM key configured: answers come from the deterministic explainer."}


@router.post("/analyze")
async def analyze(req: AnalyzeRequest) -> dict:
    cfg = orchestrator.risk_config({"equity": req.account_size, "max_risk_per_trade_pct": req.max_risk_per_trade_pct,
                                    "max_position_pct": req.max_position_pct})
    return await orchestrator.analyze(req.symbol, req.timeframe, cfg)


@router.post("/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_session)) -> dict:
    if not req.message.strip() and not req.action:
        raise HTTPException(422, "Send a message or an action.")
    return await orchestrator.chat(db, req.symbol, req.timeframe, req.message, req.action,
                                   req.conversation_id, req.compare_with)


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: int, db: Session = Depends(get_session)) -> dict:
    c = orchestrator.get_conversation(db, conversation_id)
    if not c:
        raise HTTPException(404, "Conversation not found.")
    return c


@router.post("/explain")
async def explain(req: ExplainRequest) -> dict:
    run = await orchestrator.run_analysis(req.symbol, req.timeframe, with_quote=False)
    text = expl.explain_ref(req.ref_kind, req.ref_id, run.a, run.f)
    if text is None:
        raise HTTPException(404, "That chart object is no longer part of the current analysis.")
    return {"text": text, "ref": {"kind": req.ref_kind, "id": req.ref_id}, "data_status": run.status,
            "disclaimer": expl.DISCLAIMER}


@router.post("/scan")
async def scan(req: ScanRequest) -> dict:
    rules = req.rules if req.rules is not None else scanner_service.rules_from_filters(req.filters, req.direction)
    out = await scanner_service.scan(req.market, req.timeframe, rules, req.symbols)
    out["disclaimer"] = expl.DISCLAIMER
    return out
