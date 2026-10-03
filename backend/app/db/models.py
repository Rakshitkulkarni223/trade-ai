"""Persistent state. There is one local user, so rows are not user-scoped."""
from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> int:
    return int(time.time())


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    added_at: Mapped[int] = mapped_column(Integer, default=_now)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Conversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[int] = mapped_column(Integer, default=_now)
    # last structured context the AI saw; lets follow-ups reason about the same chart
    analysis_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.id",
                                                     cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "ai_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id"))
    role: Mapped[str] = mapped_column(String(12))          # user | assistant
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # structured analysis, if any
    created_at: Mapped[int] = mapped_column(Integer, default=_now)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class TrackedSetup(Base):
    """A plan the user chose to follow on paper. Outcomes are computed from later candles; no orders exist."""
    __tablename__ = "tracked_setups"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    direction: Mapped[str] = mapped_column(String(8))
    entry: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    targets: Mapped[list] = mapped_column(JSON)            # [{"name","price","r"}]
    created_at: Mapped[int] = mapped_column(Integer, default=_now)
    entry_t: Mapped[int] = mapped_column(Integer)          # candle time the plan was based on
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    closed: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # cached outcome once closed
