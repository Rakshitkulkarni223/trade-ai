"""AI Orchestrator. Fetch -> analyse -> specialist agents -> explanation -> (optional LLM) -> guarded response.

The numbers come from the analysis engine. The LLM, when configured, only rewrites them into prose
and is discarded if it states a number the context does not contain.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from ..analysis import engine
from ..analysis.candles import Candles
from ..analysis.risk import RiskConfig
from ..config import get_settings
from ..db import models
from ..services import llm, universe
from ..services.providers import DataError, TIMEFRAMES
from . import explanation_agent as expl, liquidity_agent, market_agent, risk_agent, structure_agent, technical_agent
from .common import Fmt

log = logging.getLogger("tradeai.orchestrator")


def risk_config(overrides: Optional[dict] = None) -> RiskConfig:
    s = get_settings()
    cfg = RiskConfig(equity=s.account_size, max_risk_per_trade_pct=s.max_risk_per_trade_pct,
                     max_position_pct=s.max_position_pct, max_daily_loss_pct=s.max_daily_loss_pct)
    for k, v in (overrides or {}).items():
        if hasattr(cfg, k) and v is not None:
            setattr(cfg, k, v)
    return cfg


class Run:
    """Everything one orchestration pass produces; shared by analyze, chat and the scanner."""

    def __init__(self, raw: dict, a: dict, F: dict, f: Fmt, candles: Candles):
        self.raw, self.a, self.F, self.f, self.candles = raw, a, F, f, candles
        self.inst = raw["instrument"]
        self.status = raw["data_status"]
        self.quote = raw.get("quote")


async def run_analysis(symbol: str, timeframe: str, cfg: Optional[RiskConfig] = None,
                       with_quote: bool = True, limit: int = 500) -> Run:
    """Raises DataError if data is unavailable or too thin. Never fabricates."""
    if with_quote:
        _, raw = await market_agent.run(symbol, timeframe, limit)
    else:
        from ..services import market_service
        raw = await market_service.get_candles(symbol, timeframe, limit)
        raw["quote"] = None
    inst = raw["instrument"]
    candles = Candles.from_rows(raw["candles"])
    try:
        a = engine.analyse(candles, inst.symbol, timeframe, TIMEFRAMES[timeframe], inst.tz_offset,
                           cfg or risk_config(), inst.lot_size)
    except engine.InsufficientData as exc:
        raise DataError(str(exc)) from exc
    f = Fmt(inst, a["precision"])
    F = {"technical": technical_agent.run(a, f), "liquidity": liquidity_agent.run(a, f),
         "structure": structure_agent.run(a, f), "risk": risk_agent.run(a, f)}
    return Run(raw, a, F, f, candles)


# --------------------------------------------------------------------------- LLM wrapper
def _llm_context(run: Run, extra: Optional[dict] = None) -> dict:
    ctx = dict(run.a["context"])
    ctx["instrument"] = {"name": run.inst.name, "category": run.inst.category, "currency": run.inst.currency}
    ctx["data_status"] = {"stale": run.status["stale"], "note": run.status["note"]}
    if extra:
        ctx.update(extra)
    return ctx


class LlmResult:
    """What the model produced, or why its answer was held back. `text` is None when the caller should fall back."""
    def __init__(self, text: Optional[str] = None, provider: Optional[str] = None, note: Optional[str] = None):
        self.text, self.provider, self.note = text, provider, note


async def _llm_text(prompt: str, context: dict, history: list[dict], user_text: str) -> LlmResult:
    provider = llm.get_provider()
    if provider is None:
        return LlmResult()
    messages = history[-6:] + [{"role": "user",
                                "content": f"CONTEXT (backend-computed, authoritative):\n{json.dumps(context)}\n\n{prompt}"}]
    try:
        text = (await provider.complete(llm.SYSTEM_PROMPT, messages)).strip()
    except Exception as exc:                       # network, quota, bad key: degrade, never break the feature
        log.warning("LLM call failed (%s); using offline explainer", exc)
        return LlmResult(provider=provider.name, note="the model could not be reached")
    bad = llm.unverified_numbers(text, context, user_text)
    if bad or not text:
        log.warning("LLM answer rejected; untraceable numbers: %s", bad[:5])
        return LlmResult(provider=provider.name, note="it contained a number that could not be verified against the chart data" if bad else "it came back empty")
    return LlmResult(text, provider.name)


def card(a: dict) -> dict:
    s = a["signal"]
    return {"action": s["action"], "bias": s["bias"], "setup_type": s["setup_type"], "summary": s["summary"],
            "evidence": s["evidence"], "waiting_for": s["waiting_for"], "invalidation": s["invalidation"],
            "plan": a["plan"], "indicators": a["indicators"], "symbol": a["symbol"], "timeframe": a["timeframe"]}


# --------------------------------------------------------------------------- analyze
async def analyze(symbol: str, timeframe: str, cfg: Optional[RiskConfig] = None) -> dict:
    run = await run_analysis(symbol, timeframe, cfg)
    a, f = run.a, run.f
    sections = expl.build_sections(a, run.inst, f, run.F, run.status, run.quote)
    offline = expl.narrative(a, run.inst, f, run.F, run.status)
    text, source = offline, "offline"
    out = await _llm_text("Write the Market Copilot summary of this analysis for the user.",
                          _llm_context(run), [], "")
    if out.text:
        text, source = out.text, out.provider
    slim = {k: v for k, v in a.items() if k != "series"}
    return {
        "symbol": run.inst.symbol, "name": run.inst.name, "timeframe": timeframe,
        "instrument": run.inst.public(), "quote": run.quote, "data_status": run.status,
        "narrative": text, "narrative_source": source,
        "sections": sections, "card": card(a), "analysis": slim,
        "findings": {k: v.as_dict() for k, v in run.F.items()},
        "disclaimer": expl.DISCLAIMER,
    }


# --------------------------------------------------------------------------- chat
def _find_other_symbol(text: str, current: str, explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return universe.resolve(explicit).symbol
    t = text.lower()
    found = []
    for i in universe.INSTRUMENTS:
        base = i.symbol.lower().replace(".ns", "").replace("usdt", "")
        names = {base, i.name.lower(), i.symbol.lower()}
        if any(re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", t) for n in names if len(n) >= 2):
            found.append(i.symbol)
    others = [s for s in found if s != current]
    if others:
        return others[0]
    if current == "BTCUSDT":
        return "ETHUSDT"
    return "BTCUSDT" if current.endswith("USDT") else None


def _history(conv: models.Conversation) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in conv.messages[-8:]]


def _store(db: Session, conv: models.Conversation, user_text: str, reply: str, payload: dict,
           context: Optional[dict]) -> None:
    db.add(models.Message(conversation_id=conv.id, role="user", content=user_text))
    db.add(models.Message(conversation_id=conv.id, role="assistant", content=reply, payload=payload))
    if context is not None:
        conv.analysis_context = context
    db.commit()


async def chat(db: Session, symbol: str, timeframe: str, message: str, action: Optional[str] = None,
               conversation_id: Optional[int] = None, compare_with: Optional[str] = None) -> dict:
    conv = db.get(models.Conversation, conversation_id) if conversation_id else None
    inst = universe.resolve(symbol)
    if conv is None:
        conv = models.Conversation(symbol=inst.symbol, timeframe=timeframe)
        db.add(conv)
        db.commit()
    conv.symbol, conv.timeframe = inst.symbol, timeframe

    intent = action if action in expl.INTENT_LABELS else expl.detect_intent(message)
    user_text = message or expl.INTENT_LABELS.get(intent, "Analyze")
    tf = "1D" if intent == "swing" else timeframe
    history = _history(conv)

    try:
        run = await run_analysis(inst.symbol, tf)
    except DataError as exc:
        reply = f"{llm.REFUSAL} ({exc})"
        payload = {"intent": intent, "refused": True, "source": "backend"}
        _store(db, conv, user_text, reply, payload, None)
        return {"conversation_id": conv.id, "reply": reply, "payload": payload}

    a, f = run.a, run.f
    level = expl.extract_level(message) if intent == "whatif" else None
    extra_ctx: dict = {}
    payload: dict = {"intent": intent, "symbol": inst.symbol, "timeframe": tf, "data_status": run.status,
                     "card": card(a)}
    refs: list = []

    if intent == "compare":
        other = _find_other_symbol(message, inst.symbol, compare_with)
        if not other:
            reply = "Which instrument should I compare it with? For example: “Compare with ETH”."
            payload["source"] = "backend"
            _store(db, conv, user_text, reply, payload, a["context"])
            return {"conversation_id": conv.id, "reply": reply, "payload": payload}
        try:
            run2 = await run_analysis(other, tf, with_quote=False)
        except DataError as exc:
            reply = f"{llm.REFUSAL} (comparison instrument: {exc})"
            payload.update(refused=True, source="backend")
            _store(db, conv, user_text, reply, payload, a["context"])
            return {"conversation_id": conv.id, "reply": reply, "payload": payload}
        cmp = expl.compare(a, run2.a, run.inst, run2.inst, f, run2.f)
        base_text, payload["compare"] = cmp["text"], cmp["rows"]
        extra_ctx = {"comparison": cmp["rows"]}
    elif intent == "what_changed":
        prev_candles = run.candles.slice(0, len(run.candles) - 1)
        prev = engine.analyse(prev_candles, inst.symbol, tf, TIMEFRAMES[tf], run.inst.tz_offset,
                              risk_config(), run.inst.lot_size)
        base_text = expl.what_changed(prev, a, f)
        extra_ctx = {"previous_candle": {"price": prev["price"], "trend": prev["structure"]["trend"],
                                         "action": prev["signal"]["action"]}}
    else:
        ans = expl.answer(intent, a, run.inst, f, run.F, run.status, level)
        base_text, refs = ans["text"], ans["refs"]

    if run.status.get("stale"):
        base_text = f"Note: {run.status['note']}\n\n" + base_text

    reply, source = base_text, "offline"
    if intent != "general":
        prompt = (f"The user asked: {user_text!r} (intent: {intent}). Answer using only the context. "
                  f"A deterministic draft answer follows; improve its clarity but keep every number exactly:\n{base_text}")
    else:
        prompt = f"The user asked: {user_text!r}. Answer using only the context."
    out = await _llm_text(prompt, _llm_context(run, extra_ctx), history, user_text)
    if out.text:
        reply, source = out.text, out.provider
    elif intent == "general":
        reply = (base_text + "\n\nYou can also ask me to find liquidity, explain the trend, show the entry and "
                 "invalidation, explain why I'm saying WAIT, or compare with another market.")

    payload.update(refs=refs, source=source, disclaimer=expl.DISCLAIMER)
    if out.note:
        payload["llm_note"] = f"{out.provider} answer held back: {out.note}"
    _store(db, conv, user_text, reply, payload, a["context"])
    return {"conversation_id": conv.id, "reply": reply, "payload": payload}


def get_conversation(db: Session, conversation_id: int) -> Optional[dict]:
    conv = db.get(models.Conversation, conversation_id)
    if not conv:
        return None
    return {"id": conv.id, "symbol": conv.symbol, "timeframe": conv.timeframe,
            "messages": [{"role": m.role, "content": m.content, "payload": m.payload, "created_at": m.created_at}
                         for m in conv.messages]}
