"""A closed market has nothing to fetch, so nothing should be fetched."""
import asyncio
import time

import pytest

from app.services import market_service as ms, providers, universe, websocket_service as ws

H = 3600
START, END = 1_000_000, 1_000_000 + 6 * H            # a 6-hour regular session


def rec(last_trade):
    return {"start": START, "end": END, "last_trade": last_trade, "fetched_at": 0}


def test_inside_hours_and_trading_is_open():
    now = START + 3 * H
    assert ms.evaluate_session(rec(now - 60), now)["open"] is True


def test_before_the_open_is_closed_and_reports_when_it_opens():
    out = ms.evaluate_session(rec(START - 20 * H), START - 2 * H)
    assert out == {"open": False, "opens_at": START}


def test_after_the_close_is_closed_with_no_known_open():
    out = ms.evaluate_session(rec(END - 10), END + H)
    assert out["open"] is False and out["opens_at"] is None


def test_futures_style_nominal_session_with_no_recent_trade_is_closed():
    """Gold futures report a 'Sunday to Monday' session although nothing has traded since Friday."""
    now = START + 2 * H
    assert ms.evaluate_session(rec(START - 40 * H), now)["open"] is False


def test_just_after_the_open_a_stale_last_trade_is_not_called_closed():
    now = START + 5 * 60                              # five minutes into the session
    assert ms.evaluate_session(rec(START - 17 * H), now)["open"] is True


def test_missing_last_trade_relies_on_the_window_alone():
    now = START + 3 * H
    assert ms.evaluate_session(rec(None), now)["open"] is True


@pytest.mark.asyncio
async def test_crypto_never_closes_and_unknown_sessions_assume_open(monkeypatch):
    assert (await ms.market_status(universe.resolve("BTCUSDT")))["open"] is True
    providers.MARKET_META.pop("ZZZZ.NS", None)

    async def boom(*a, **k):
        raise providers.DataError("down")
    monkeypatch.setattr(providers, "_yahoo_chart", boom)
    out = await ms.market_status(universe.resolve("ZZZZ.NS"))
    assert out == {"open": True, "known": False}      # never switch updates off on a guess


def test_closed_cache_time_never_runs_past_the_open():
    assert ms.closed_ttl({"opens_at": 1_000 + 120}, now=1_000) == 120
    assert ms.closed_ttl({"opens_at": 1_000 + 99_999}, now=1_000) == ms.CLOSED_TTL_MAX
    assert ms.closed_ttl({}, now=1_000) == 300


@pytest.mark.asyncio
async def test_closed_market_polling_makes_no_price_requests_and_announces_once(monkeypatch):
    inst = universe.resolve("RELIANCE.NS")
    soon = time.time() + 10 * H
    providers.MARKET_META[inst.symbol] = {"start": soon, "end": soon + 6 * H, "last_trade": 1, "fetched_at": time.time()}
    calls, sent, sleeps = [], [], []

    async def quote(_):
        calls.append(1)
        return {"price": 1.0, "change_pct": 0.0}

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) >= 3:
            raise asyncio.CancelledError
    monkeypatch.setattr(providers, "yahoo_quote", quote)
    monkeypatch.setattr(ws.asyncio, "sleep", fake_sleep)

    async def send(m):
        sent.append(m)
    with pytest.raises(asyncio.CancelledError):
        await ws.poll_yahoo(inst, send)
    assert calls == []                                          # not one price request while closed
    assert [m["state"] for m in sent] == ["closed"]             # told the client once, not every cycle
    assert all(30 <= s <= ms.CLOSED_TTL_MAX for s in sleeps)    # sleeping long, not every 5 seconds


@pytest.mark.asyncio
async def test_open_market_polls_and_resumes_after_closed(monkeypatch):
    inst = universe.resolve("TCS.NS")
    state = {"open": False}

    async def status(_):
        return {"open": state["open"], "known": True, "opens_at": None}
    calls, sent = [], []

    async def quote(_):
        calls.append(1)
        return {"price": 10.0, "change_pct": 1.0}
    n = {"i": 0}

    async def fake_sleep(s):
        n["i"] += 1
        state["open"] = True                                    # the market opens after the first sleep
        if n["i"] >= 3:
            raise asyncio.CancelledError
    monkeypatch.setattr(ws, "market_status", status)
    monkeypatch.setattr(providers, "yahoo_quote", quote)
    monkeypatch.setattr(ws.asyncio, "sleep", fake_sleep)

    async def send(m):
        sent.append(m)
    with pytest.raises(asyncio.CancelledError):
        await ws.poll_yahoo(inst, send)
    kinds = [m.get("state") or m["type"] for m in sent]
    assert kinds[0] == "closed" and "hello" in kinds and "tick" in kinds
    assert len(calls) >= 1


@pytest.mark.asyncio
async def test_closed_market_candles_are_served_from_cache_without_new_requests(monkeypatch):
    from app.services import cache as cache_mod
    cache_mod._cache = cache_mod.MemoryCache()
    inst = universe.resolve("INFY.NS")
    soon = time.time() + 10 * H
    providers.MARKET_META[inst.symbol] = {"start": soon, "end": soon + 6 * H, "last_trade": 1, "fetched_at": time.time()}
    fetches = []

    async def candles(i, tf, limit):
        fetches.append(1)
        return [{"t": 1_700_000_000 + k * 60, "o": 1, "h": 2, "l": 1, "c": 1.5, "v": 1} for k in range(5)]
    monkeypatch.setattr(providers, "yahoo_candles", candles)
    a = await ms.get_candles(inst.symbol, "1m")
    b = await ms.get_candles(inst.symbol, "1m")
    assert len(fetches) == 1                                    # the second call needed no Yahoo request
    assert a["data_status"]["market_open"] is False and "closed" in a["data_status"]["note"].lower()
    assert b["data_status"]["stale"] is False


@pytest.mark.asyncio
async def test_unknown_symbol_is_reported_once_and_polling_stops(monkeypatch):
    inst = universe.resolve("NOSUCH.NS")
    providers.MARKET_META.pop(inst.symbol, None)
    calls, sent = [], []

    async def status(_):
        return {"open": True, "known": False}

    async def quote(_):
        calls.append(1)
        raise providers.DataError("Yahoo Finance does not know the symbol NOSUCH.NS.")

    async def send(m):
        sent.append(m)
    monkeypatch.setattr(ws, "market_status", status)
    monkeypatch.setattr(providers, "yahoo_quote", quote)
    await asyncio.wait_for(ws.poll_yahoo(inst, send), timeout=2)        # returns by itself instead of looping forever
    assert len(calls) == 1
    assert sent[-1]["state"] == "error" and sent[-1]["fatal"] is True


@pytest.mark.asyncio
async def test_transient_errors_back_off_instead_of_hammering(monkeypatch):
    inst = universe.resolve("TCS.NS")
    sleeps = []

    async def status(_):
        return {"open": True, "known": True}

    async def quote(_):
        raise providers.DataError("Yahoo Finance returned HTTP 429")

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) >= 4:
            raise asyncio.CancelledError

    async def send(m):
        pass
    monkeypatch.setattr(ws, "market_status", status)
    monkeypatch.setattr(providers, "yahoo_quote", quote)
    monkeypatch.setattr(ws.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await ws.poll_yahoo(inst, send)
    assert sleeps == sorted(sleeps) and sleeps[-1] > sleeps[0] and max(sleeps) <= 300
