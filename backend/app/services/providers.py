"""Raw market-data fetchers. Each returns candles as a list of {t,o,h,l,c,v} dicts (t = unix seconds,
oldest first). Nothing here invents data: on failure it raises DataError and the caller says so."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .universe import Instrument

log = logging.getLogger("tradeai.providers")

TIMEFRAMES: dict[str, int] = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
                              "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800}

BINANCE_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision", "https://api.binance.us"]
BINANCE_INTERVAL = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                    "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1w"}

# timeframe -> (yahoo interval, yahoo range, resample-to-seconds or None)
YAHOO_PLAN = {
    "1m": ("1m", "5d", None), "5m": ("5m", "1mo", None), "15m": ("15m", "1mo", None),
    "30m": ("30m", "1mo", None), "1H": ("60m", "6mo", None), "4H": ("60m", "1y", 14400),
    "1D": ("1d", "2y", None), "1W": ("1wk", "10y", None),
}
HEADERS = {"User-Agent": "Mozilla/5.0 (TradeAI market copilot)"}

_client: Optional[httpx.AsyncClient] = None


class DataError(RuntimeError):
    """The provider could not supply data. Surfaced to the user verbatim."""


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15, headers=HEADERS, follow_redirects=True)
    return _client


async def aclose() -> None:
    if _client and not _client.is_closed:
        await _client.aclose()


def _row(t, o, h, l, c, v) -> Optional[dict]:
    try:
        if None in (t, o, h, l, c):
            return None
        o, h, l, c = float(o), float(h), float(l), float(c)
        if min(o, h, l, c) <= 0 or h < l:
            return None
        return {"t": int(t), "o": o, "h": h, "l": l, "c": c, "v": float(v or 0.0)}
    except (TypeError, ValueError):
        return None


def resample(rows: list[dict], seconds: int) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        bucket = r["t"] // seconds * seconds
        if out and out[-1]["t"] == bucket:
            b = out[-1]
            b["h"], b["l"], b["c"], b["v"] = max(b["h"], r["h"]), min(b["l"], r["l"]), r["c"], b["v"] + r["v"]
        else:
            out.append({**r, "t": bucket})
    return out


# --------------------------------------------------------------------------- Binance
async def _binance_get(path: str, params: dict) -> object:
    last: Optional[Exception] = None
    for host in BINANCE_HOSTS:
        try:
            r = await client().get(host + path, params=params)
            if r.status_code == 200:
                return r.json()
            last = DataError(f"Binance returned HTTP {r.status_code} for {params.get('symbol')}")
            if r.status_code == 400:        # unknown symbol: other hosts will say the same
                break
        except httpx.HTTPError as exc:
            last = exc
    raise DataError(f"Binance data is unavailable ({last}).")


async def binance_candles(inst: Instrument, tf: str, limit: int) -> list[dict]:
    data = await _binance_get("/api/v3/klines", {"symbol": inst.symbol, "interval": BINANCE_INTERVAL[tf],
                                                  "limit": min(limit, 1000)})
    rows = [_row(k[0] // 1000, k[1], k[2], k[3], k[4], k[5]) for k in data]  # type: ignore[index]
    return [r for r in rows if r]


async def binance_quote(inst: Instrument) -> dict:
    d = await _binance_get("/api/v3/ticker/24hr", {"symbol": inst.symbol})
    return {"price": float(d["lastPrice"]), "change": float(d["priceChange"]),         # type: ignore[index]
            "change_pct": float(d["priceChangePercent"]), "prev_close": float(d["prevClosePrice"]),
            "high": float(d["highPrice"]), "low": float(d["lowPrice"]), "volume": float(d["volume"])}


async def binance_depth(inst: Instrument, limit: int = 20) -> dict:
    d = await _binance_get("/api/v3/depth", {"symbol": inst.symbol, "limit": limit})
    return {"bids": [[float(p), float(q)] for p, q in d["bids"]],          # type: ignore[index]
            "asks": [[float(p), float(q)] for p, q in d["asks"]]}


# --------------------------------------------------------------------------- Yahoo
async def _yahoo_chart(symbol: str, interval: str, rng: str) -> dict:
    last: Optional[Exception] = None
    for host in ("query1", "query2"):
        try:
            r = await client().get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}",
                                   params={"interval": interval, "range": rng, "includePrePost": "false"})
            if r.status_code == 404:
                raise DataError(f"Yahoo Finance does not know the symbol {symbol}.")
            if r.status_code == 200:
                body = r.json().get("chart", {})
                if body.get("error"):
                    raise DataError(f"Yahoo Finance: {body['error'].get('description', 'error')}")
                result = body.get("result")
                if result:
                    return result[0]
            last = DataError(f"Yahoo Finance returned HTTP {r.status_code}")
        except DataError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            last = exc
    raise DataError(f"Yahoo Finance data is unavailable ({last}).")


def _yahoo_rows(res: dict) -> list[dict]:
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    rows = [_row(t, q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i])
            for i, t in enumerate(ts)] if q else []
    return [r for r in rows if r]


async def yahoo_candles(inst: Instrument, tf: str, limit: int) -> list[dict]:
    interval, rng, resample_to = YAHOO_PLAN[tf]
    res = await _yahoo_chart(inst.symbol, interval, rng)
    rows = _yahoo_rows(res)
    if resample_to:
        rows = resample(rows, resample_to)
    if not rows:
        raise DataError(f"No candles returned for {inst.symbol} on {tf}.")
    return rows[-limit:]


async def yahoo_quote(inst: Instrument) -> dict:
    res = await _yahoo_chart(inst.symbol, "1d", "5d")
    meta, rows = res.get("meta", {}), _yahoo_rows(res)
    price = meta.get("regularMarketPrice") or (rows[-1]["c"] if rows else None)
    prev = meta.get("chartPreviousClose") or meta.get("previousClose") or (rows[-2]["c"] if len(rows) > 1 else None)
    if price is None:
        raise DataError(f"No quote available for {inst.symbol}.")
    change = price - prev if prev else 0.0
    return {"price": float(price), "change": change, "change_pct": change / prev * 100 if prev else 0.0,
            "prev_close": prev, "high": meta.get("regularMarketDayHigh"), "low": meta.get("regularMarketDayLow"),
            "volume": meta.get("regularMarketVolume")}
