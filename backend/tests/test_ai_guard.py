"""The LLM can only restate numbers the backend computed; anything else is discarded."""
import pytest

from app.agents import orchestrator
from app.services import llm


class Stub:
    name = "stub"

    def __init__(self, text):
        self.text = text

    async def complete(self, system, messages, max_tokens=700):
        return self.text


CTX = {"price": 84576.01, "plan": {"stop": 87299.01}, "rsi": 43.2}


@pytest.mark.asyncio
async def test_grounded_answer_is_used(monkeypatch):
    monkeypatch.setattr(llm, "get_provider", lambda: Stub("Price is 84,576.01 and the stop is 87,299.01. RSI 43.2."))
    out = await orchestrator._llm_text("q", CTX, [], "analyze")
    assert out is not None and out[1] == "stub"


@pytest.mark.asyncio
async def test_invented_price_is_rejected(monkeypatch):
    monkeypatch.setattr(llm, "get_provider", lambda: Stub("Target is 95,000, a clear buy."))
    assert await orchestrator._llm_text("q", CTX, [], "analyze") is None


@pytest.mark.asyncio
async def test_user_supplied_level_is_allowed(monkeypatch):
    monkeypatch.setattr(llm, "get_provider", lambda: Stub("If price falls to 83,000 the idea is unaffected."))
    assert await orchestrator._llm_text("q", CTX, [], "what if it hits 83,000?") is not None


@pytest.mark.asyncio
async def test_provider_failure_falls_back(monkeypatch):
    class Boom(Stub):
        async def complete(self, *a, **k):
            raise RuntimeError("quota")
    monkeypatch.setattr(llm, "get_provider", lambda: Boom(""))
    assert await orchestrator._llm_text("q", CTX, [], "x") is None


def test_no_order_code_anywhere():
    """The product has no broker or order path; keep it that way."""
    import pathlib
    src = "\n".join(p.read_text() for p in pathlib.Path("app").rglob("*.py"))
    for word in ("place_order", "cancel_order", "BrokerInterface", "groww", "ENABLE_REAL_TRADING"):
        assert word.lower() not in src.lower(), word


def test_stream_rejects_unknown_timeframe():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c, c.websocket_connect("/ws/market/BTCUSDT?timeframe=9x") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "status" and msg["state"] == "error"
