"""Shared types and formatting for the agents. Every agent returns a Finding: a headline,
human-readable facts, and the structured data those facts came from."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..services.universe import CURRENCY_SYMBOL, Instrument


@dataclass
class Finding:
    agent: str
    headline: str
    facts: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    refs: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"agent": self.agent, "headline": self.headline, "facts": self.facts,
                "data": self.data, "refs": self.refs}


class Fmt:
    """Price formatting bound to one instrument."""

    def __init__(self, inst: Instrument, precision: int):
        self.sym = CURRENCY_SYMBOL.get(inst.currency, "")
        self.p = precision

    def price(self, v: Optional[float]) -> str:
        if v is None:
            return "n/a"
        return f"{self.sym}{v:,.{self.p}f}"

    def pct(self, v: Optional[float], d: int = 2) -> str:
        return "n/a" if v is None else f"{v:+.{d}f}%"


def when(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b %H:%M UTC")


def bars_ago(n: Optional[int]) -> str:
    if n is None:
        return "n/a"
    return "on the latest candle" if n == 0 else f"{n} candle{'s' if n != 1 else ''} ago"
