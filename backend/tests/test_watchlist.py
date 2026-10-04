"""Watchlist: seeded once, validated on add, duplicates and removals reported honestly."""
import pytest
from fastapi.testclient import TestClient

from app.db import database, models
from app.main import app
from app.routers import watchlist as wl
from app.services import market_service, providers


@pytest.fixture()
def http(monkeypatch):
    database.init_db()
    with database.SessionLocal() as s:
        s.query(models.WatchlistItem).delete()
        s.query(models.AppFlag).delete()
        s.commit()

    known_on_yahoo = {"ESDS.NS", "SOMETHING.BO"}

    async def quote(sym):
        if sym.upper() in known_on_yahoo:
            return {"symbol": sym.upper(), "price": 1.0}
        raise providers.DataError(f"Yahoo Finance does not know the symbol {sym}.")
    monkeypatch.setattr(market_service, "get_quote", quote)
    with TestClient(app) as c:
        yield c


def symbols(http):
    return http.get("/api/watchlist/symbols").json()["symbols"]


def test_first_use_offers_the_starter_list(http):
    assert symbols(http) == wl.DEFAULTS


def test_removing_everything_does_not_bring_the_defaults_back(http):
    for s in list(symbols(http)):
        assert http.delete(f"/api/watchlist/{s}").status_code == 200
    assert symbols(http) == []
    assert symbols(http) == []                         # asked again: still empty
    assert http.get("/api/watchlist?timeframe=1H").json()["items"] == []


def test_an_existing_list_is_never_replaced_by_the_starter_list(http):
    """An install from before the 'seeded' flag existed: it has a list and no flag. Neither may be overwritten."""
    with database.SessionLocal() as s:
        s.query(models.WatchlistItem).delete()
        s.query(models.AppFlag).delete()
        s.add(models.WatchlistItem(symbol="MSFT", position=0))
        s.commit()
    assert symbols(http) == ["MSFT"]
    http.delete("/api/watchlist/MSFT")
    assert symbols(http) == []                          # and once emptied it stays empty


def test_adding_a_catalogue_symbol_and_a_duplicate(http):
    http.delete("/api/watchlist/AAPL")
    first = http.post("/api/watchlist", json={"symbol": "aapl"}).json()
    assert first["symbol"] == "AAPL" and first["added"] is True
    again = http.post("/api/watchlist", json={"symbol": "AAPL"}).json()
    assert again["added"] is False                      # told it was already there, not silently accepted
    assert symbols(http).count("AAPL") == 1


def test_a_bare_indian_ticker_resolves_to_its_nse_listing(http):
    out = http.post("/api/watchlist", json={"symbol": "esds"}).json()
    assert out["symbol"] == "ESDS.NS" and out["added"] is True and out["resolved_from"] == "ESDS"
    assert "ESDS.NS" in symbols(http)


def test_a_made_up_ticker_is_rejected_with_a_useful_message(http):
    r = http.post("/api/watchlist", json={"symbol": "NOSUCHCO"})
    assert r.status_code == 422
    msg = r.json()["detail"]
    assert "NOSUCHCO" in msg and ".NS" in msg
    assert "NOSUCHCO" not in symbols(http)


def test_a_made_up_crypto_pair_is_rejected_without_trying_stock_suffixes(http):
    r = http.post("/api/watchlist", json={"symbol": "FAKEUSDT"})
    assert r.status_code == 422 and "FAKEUSDT.NS" not in r.json()["detail"]


def test_removing_something_not_in_the_list_is_a_404(http):
    assert http.delete("/api/watchlist/NOPE").status_code == 404
