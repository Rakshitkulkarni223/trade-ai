# TradeAI — AI Market Copilot

An AI-first chart workspace. Open a market, see liquidity, market structure, fair value gaps and indicators on an
interactive chart, and ask a copilot that explains the setup from the **actual numbers** — including when the right
answer is **WAIT**.

> Analysis only. There is no broker, no order placement, no account access. Information, not financial advice.

## Run it

Needs Python 3.10+ (3.11 used in development) and Node 18+.

```bash
./scripts/dev.sh          # backend on :8000 (docs at /docs), app on :5173
```

or by hand:

```bash
cd backend && python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

No keys are required. Market data: **Binance** (crypto) and **Yahoo Finance** (Indian/US stocks, indices, metals).
Optionally copy `.env.example` to `.env` and add an `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY`
for LLM-written explanations. Without one, a deterministic rules-based explainer is used.

## What's in it

| Area | What it does |
| --- | --- |
| Chart | Live candle (streamed for crypto), volume, EMA/VWAP/Bollinger, RSI pane, 1m–1W, liquidity lines, FVG boxes, BOS/CHoCH, Entry/SL/TP. Built on TradingView's open-source `lightweight-charts`. |
| Liquidity | Previous day/week high & low, swing highs/lows, equal highs/lows, sweep detection (wick through, close back). |
| Structure | Swings, HH/HL/LH/LL, BOS, CHoCH, trend. No look-ahead: swings are only used once confirmed. |
| FVG | Bullish/bearish gaps with unmitigated / partial / filled status. |
| Signal | LONG / SHORT / **WAIT** from required conditions, decided on **closed candles only** and always with the **Supertrend (ATR 10 × 3)** agreeing. Evidence is *supporting / against / caution / missing*, never a win-probability. |
| Setups | Supertrend Buy/Sell flip (not a whipsaw), liquidity-sweep reversal, trend pullback. A triggered setup keeps **fixed** entry/stop/targets until stopped, completed, expired (30 candles) or the Supertrend turns against it. While WAIT, **no entry levels are shown anywhere**. |
| Plan | Entry, invalidation, TP1–3 as R-multiples, sizing from your account size and risk %. All assumptions are returned. |
| Copilot | A pinned verdict (headline, progress, market read) where **every missing condition says what would satisfy it and at which level**, plus quick actions + chat. Understands "what if it breaks 78,000?", "compare with ETH", "why WAIT?", "what changed?". **Why?** highlights the object on the chart. |
| AI Lab / Screener | Scans a market; every hit lists the checks behind it. Plain-English queries become structured rules you can see. |
| Chat history | **＋ New chat** and a **History** view in the copilot: every conversation is saved, grouped by day, searchable, and can be reopened (its symbol and timeframe come back with it), renamed or deleted. Titles come from your first question. |
| Watchlist | Price, change, trend, liquidity and AI status, with a `closed` marker for markets that are shut. The Watch button reflects (and edits) the real list; added tickers are checked (a bare Indian ticker like `ESDS` resolves to `ESDS.NS`), and the starter list is offered only once. |
| Paper analysis | Save an active plan, then see what later candles did to it (stop wins ties; no fees/slippage). |

Sector and market-cap screening are not offered: the free providers don't supply fundamentals.

## Architecture

```
React (Vite, TS, Tailwind, TanStack Query, Zustand)  →  /api proxy  →  FastAPI
FastAPI:  routers → services (market data, cache, LLM, scanner) → analysis (pure numpy) → agents (orchestrator)
Storage:  SQLite by default (DATABASE_URL for Postgres) · memory cache by default (REDIS_URL for Redis)
```

Agents (`backend/app/agents/`): `market_agent` (data) → `technical`, `liquidity`, `structure`, `risk` → `explanation_agent`,
coordinated by `orchestrator`. A plain orchestrator, no framework. See [docs/ai-guardrails.md](docs/ai-guardrails.md).

API highlights: `GET /api/market/{symbol}/history`, `GET /api/analysis/{symbol}?timeframe=1H`, `POST /api/ai/analyze|chat|scan|explain`,
`POST /api/screener/query`, `/api/watchlist`, `/api/paper/setups`. Interactive docs at `/docs`.

## Tests

```bash
cd backend && .venv/bin/pytest -q      # offline: synthetic candles with known sweeps, CHoCH, FVGs, risk math
cd frontend && npm run build           # typecheck + production build
```

## Known limits

- Live feed: crypto streams from Binance through the backend (`/ws/market/{symbol}`), updating the forming candle about every 2 s.
  Stocks, indices and metals have no free stream, so their price is polled every 5 s (the header shows `LIVE · 5s`), and Yahoo may delay
  some exchanges. Indicators, liquidity and the AI insight recompute on a 8 s – 2 min refresh, not per tick.
- **Closed markets are left alone.** Open/closed comes from the regular-session window in Yahoo's own metadata plus a last-trade check (so
  futures that report a nominal session but have not traded are also treated as closed). While closed, the live feed and the page's
  polling stop, answers are cached until the open, and the header says `Market closed`; one slow check lets an open page notice the open.
  An unknown ticker is reported once and not retried.
- Yahoo limits intraday history (1m ≈ 5 days, 5–30m ≈ 1 month, 1H ≈ 6 months) and is unofficial; it can change without notice.
- Detector parameters (swing size, FVG minimum size, sweep window, 2.5 ATR "extended" rule, 4 ATR stop limit) are sensible defaults,
  not tuned or backtested. Treat output as a structured read of the chart.
- Single local user, no login. Postgres and Redis paths exist but were not exercised here.
- Groww/broker integration and real trading were deliberately removed from scope.
