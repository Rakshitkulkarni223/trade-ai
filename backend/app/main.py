"""TradeAI API. Market analysis only: there is no broker, no order placement and no account access."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analysis.engine import InsufficientData
from .config import get_settings
from .db.database import SessionLocal, init_db
from .routers import ai, analysis, market, paper, screener, watchlist
from .services import cache, llm, providers
from .services.providers import DataError

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        watchlist.seed_defaults(db)
    yield
    await providers.aclose()


app = FastAPI(title="TradeAI API", version="1.0.0", lifespan=lifespan,
              description="AI market copilot: charts, liquidity, structure, FVG and explainable setups. "
                          "Information only, not investment advice.")
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_url, "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])


@app.exception_handler(DataError)
async def data_error(_: Request, exc: DataError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc), "code": "data_unavailable"})


@app.exception_handler(InsufficientData)
async def thin(_: Request, exc: InsufficientData) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc), "code": "insufficient_data"})


for r in (market.router, analysis.router, ai.router, screener.router, watchlist.router, paper.router):
    app.include_router(r)


@app.get("/api/health")
def health() -> dict:
    p = llm.get_provider()
    return {"ok": True, "ai_provider": p.name if p else "offline",
            "cache": type(cache.get_cache()).__name__}


@app.get("/api/settings")
def settings() -> dict:
    s = get_settings()
    return {"account_size": s.account_size, "max_risk_per_trade_pct": s.max_risk_per_trade_pct,
            "max_position_pct": s.max_position_pct, "max_daily_loss_pct": s.max_daily_loss_pct}
