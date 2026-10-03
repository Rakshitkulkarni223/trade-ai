"""LLM provider abstraction (Anthropic / OpenAI / Gemini over plain HTTPS) plus a number guard.

The LLM is only ever asked to *explain* a structured analysis the backend already computed.
Whatever it returns is checked: any price-like number that is not traceable to the context is
grounds for discarding the answer in favour of the deterministic explainer.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import httpx

from ..config import get_settings

log = logging.getLogger("tradeai.llm")

SYSTEM_PROMPT = """You are the AI Market Copilot inside a charting workspace.
You explain market analysis that the application's backend has already computed. Rules:
- Use ONLY numbers, levels and facts present in the CONTEXT JSON or in the user's own message.
  Never invent, estimate or round to a price, indicator value or level that is not in the context.
- Separate facts (what the data shows) from interpretation (what it might mean). Label interpretation as such.
- Never promise profit, never call anything guaranteed, never give a win probability.
- If signal.action is WAIT, say so plainly and explain what confirmation is still missing.
- Always state what would invalidate the setup.
- If the context says data is stale or unavailable, say that first.
- Write plain English, short paragraphs, no more than 180 words unless asked for detail.
- This is information, not financial advice."""

REFUSAL = ("I can't analyze this setup because current market data is unavailable. "
           "I won't guess at prices or indicators.")


class Provider(Protocol):
    name: str
    async def complete(self, system: str, messages: list[dict], max_tokens: int = 700) -> str: ...


def _secret(v) -> str:
    return v.get_secret_value() if v else ""


@dataclass
class AnthropicProvider:
    key: str
    model: str
    name: str = "anthropic"

    async def complete(self, system, messages, max_tokens=700):
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post("https://api.anthropic.com/v1/messages",
                             headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
                             json={"model": self.model, "max_tokens": max_tokens, "system": system,
                                   "messages": messages})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))


@dataclass
class OpenAIProvider:
    key: str
    model: str
    name: str = "openai"

    async def complete(self, system, messages, max_tokens=700):
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post("https://api.openai.com/v1/chat/completions",
                             headers={"Authorization": f"Bearer {self.key}"},
                             json={"model": self.model, "max_tokens": max_tokens,
                                   "messages": [{"role": "system", "content": system}, *messages]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""


@dataclass
class GeminiProvider:
    key: str
    model: str
    name: str = "gemini"

    async def complete(self, system, messages, max_tokens=700):
        contents = [{"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [{"text": m["content"]}]} for m in messages]
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                             headers={"x-goog-api-key": self.key},
                             json={"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                                   "generationConfig": {"maxOutputTokens": max_tokens}})
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)


def get_provider() -> Optional[Provider]:
    """The configured LLM, or None meaning 'use the deterministic offline explainer'."""
    s = get_settings()
    want = s.ai_provider.lower()
    if want == "offline":
        return None
    candidates = {
        "anthropic": lambda: AnthropicProvider(_secret(s.anthropic_api_key), s.anthropic_model) if s.anthropic_api_key else None,
        "openai": lambda: OpenAIProvider(_secret(s.openai_api_key), s.openai_model) if s.openai_api_key else None,
        "gemini": lambda: GeminiProvider(_secret(s.gemini_api_key), s.gemini_model) if s.gemini_api_key else None,
    }
    order = [want] if want in candidates else list(candidates)
    for name in order:
        p = candidates[name]()
        if p and p.key:
            return p
    return None


# --------------------------------------------------------------------------- number guard
_NUM = re.compile(r"(?<![\w.])\$?₹?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w])")


def _walk_numbers(obj: Any, out: list[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, out)
    elif isinstance(obj, str):
        for m in _NUM.finditer(obj):
            try:
                out.append(float(m.group(1).replace(",", "")))
            except ValueError:
                pass


def unverified_numbers(text: str, context: Any, extra_text: str = "", rel_tol: float = 0.003) -> list[float]:
    """Numbers in `text` that are neither in `context` nor in the user's message (within tolerance).

    Values far below the instrument's price scale (bar counts, indicator periods, percentages, ratios)
    are ignored; for a high-priced asset that means anything under 100, for a sub-dollar coin nothing.
    """
    allowed: list[float] = []
    _walk_numbers(context, allowed)
    for m in _NUM.finditer(extra_text):
        allowed.append(float(m.group(1).replace(",", "")))
    price = context.get("price") if isinstance(context, dict) else None
    floor = min(100.0, price / 10) if isinstance(price, (int, float)) and price > 0 else 100.0
    bad = []
    for m in _NUM.finditer(text):
        val = float(m.group(1).replace(",", ""))
        if val < floor:
            continue
        if not any(abs(val - a) <= max(abs(a) * rel_tol, 0.011) for a in allowed):
            bad.append(val)
    return bad
