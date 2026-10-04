from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    return create_engine(url, **kwargs)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _ensure_columns(eng=None) -> None:
    """create_all never alters an existing table, so add columns introduced after a database was first created."""
    from sqlalchemy import inspect, text
    eng = eng or engine
    insp = inspect(eng)
    if "ai_conversations" not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns("ai_conversations")}
    with eng.begin() as conn:
        if "title" not in have:
            conn.execute(text("ALTER TABLE ai_conversations ADD COLUMN title VARCHAR(120)"))
        if "updated_at" not in have:
            conn.execute(text("ALTER TABLE ai_conversations ADD COLUMN updated_at INTEGER"))
            conn.execute(text("UPDATE ai_conversations SET updated_at = created_at"))


def init_db() -> None:
    from . import models  # noqa: F401  (registers tables)
    Base.metadata.create_all(engine)
    _ensure_columns()


def get_session() -> Iterator[Session]:
    with SessionLocal() as s:
        yield s
