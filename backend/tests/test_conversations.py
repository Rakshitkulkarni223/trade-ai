"""Chat history: titles, listing, rename, delete, and upgrading a database made before these columns existed."""
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.agents import orchestrator
from app.db import database, models
from app.main import app


@pytest.fixture()
def db():
    database.init_db()
    with database.SessionLocal() as s:
        s.query(models.Message).delete()
        s.query(models.Conversation).delete()
        s.commit()
        yield s


def _conv(db, symbol="BTCUSDT", tf="1H", asks=("Why should I wait?",), when=None):
    c = models.Conversation(symbol=symbol, timeframe=tf)
    db.add(c)
    db.commit()
    for a in asks:
        orchestrator._store(db, c, a, f"answer to {a}", {"intent": "x"}, {"price": 1})
    if when:
        c.updated_at = when
        db.commit()
    return c


def test_first_question_becomes_the_title_and_later_ones_do_not_change_it(db):
    c = _conv(db, asks=("Why should I wait?", "What if it breaks 83,000?"))
    assert c.title == "Why should I wait?"


def test_long_titles_are_shortened_on_one_line(db):
    c = _conv(db, asks=("  analyze\nthis   chart " + "very long " * 30,))
    assert len(c.title) <= 80 and c.title.endswith("…") and "\n" not in c.title


def test_listing_is_newest_first_and_skips_empty_conversations(db):
    now = int(time.time())
    old = _conv(db, "ETHUSDT", asks=("older question",), when=now - 5000)
    new = _conv(db, "BTCUSDT", asks=("newer question",), when=now)
    db.add(models.Conversation(symbol="XRPUSDT", timeframe="1H"))      # a failed first turn: no messages
    db.commit()
    rows = orchestrator.list_conversations(db)
    assert [r["id"] for r in rows] == [new.id, old.id]
    assert rows[0]["message_count"] == 2 and rows[0]["symbol"] == "BTCUSDT"


def test_search_matches_title_or_symbol(db):
    _conv(db, "BTCUSDT", asks=("liquidity question",))
    _conv(db, "ETHUSDT", asks=("trend question",))
    assert [r["symbol"] for r in orchestrator.list_conversations(db, "liquid")] == ["BTCUSDT"]
    assert [r["symbol"] for r in orchestrator.list_conversations(db, "ethusdt")] == ["ETHUSDT"]


def test_http_list_open_rename_delete_roundtrip(db):
    c = _conv(db, "BTCUSDT", "5m", asks=("Find liquidity",))
    with TestClient(app) as http:
        lst = http.get("/api/ai/conversations").json()["conversations"]
        assert lst[0]["title"] == "Find liquidity" and lst[0]["timeframe"] == "5m"

        full = http.get(f"/api/ai/conversations/{c.id}").json()
        assert [m["role"] for m in full["messages"]] == ["user", "assistant"]
        assert full["messages"][1]["payload"] == {"intent": "x"}           # structured payload survives for re-rendering

        assert http.patch(f"/api/ai/conversations/{c.id}", json={"title": "My notes"}).json()["title"] == "My notes"
        assert http.patch(f"/api/ai/conversations/{c.id}", json={"title": ""}).status_code == 422
        assert http.patch("/api/ai/conversations/99999", json={"title": "x"}).status_code == 404

        assert http.delete(f"/api/ai/conversations/{c.id}").json() == {"deleted": c.id}
        assert http.get(f"/api/ai/conversations/{c.id}").status_code == 404
        assert http.get("/api/ai/conversations").json()["conversations"] == []
        assert http.delete(f"/api/ai/conversations/{c.id}").status_code == 404


def test_deleting_a_conversation_removes_its_messages(db):
    c = _conv(db, asks=("one", "two"))
    cid = c.id
    assert orchestrator.delete_conversation(db, cid) is True
    assert db.query(models.Message).filter_by(conversation_id=cid).count() == 0


def test_old_databases_are_upgraded_in_place(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE ai_conversations (id INTEGER PRIMARY KEY, symbol VARCHAR(32), timeframe VARCHAR(8), "
                       "created_at INTEGER, analysis_context JSON)"))
        c.execute(text("INSERT INTO ai_conversations (id, symbol, timeframe, created_at) VALUES (1, 'BTCUSDT', '1H', 1700000000)"))
    database._ensure_columns(eng)
    cols = {c["name"] for c in inspect(eng).get_columns("ai_conversations")}
    assert {"title", "updated_at"} <= cols
    with eng.connect() as c:
        assert c.execute(text("SELECT updated_at FROM ai_conversations WHERE id = 1")).scalar() == 1700000000
    database._ensure_columns(eng)                      # running it again changes nothing and does not fail


def test_compare_has_a_sensible_default_partner_in_every_market():
    from app.agents.orchestrator import _default_peer
    assert _default_peer("BTCUSDT") == "ETHUSDT" and _default_peer("ETHUSDT") == "BTCUSDT"
    assert _default_peer("^NSEI") == "^NSEBANK"                 # an index with its sibling, not a cryptocurrency
    assert _default_peer("GC=F") == "SI=F"
    assert _default_peer("RELIANCE.NS") != "BTCUSDT" and _default_peer("RELIANCE.NS").endswith(".NS")
    assert _default_peer("AAPL") not in (None, "AAPL")
