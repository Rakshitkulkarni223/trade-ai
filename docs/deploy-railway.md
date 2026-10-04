# Deploying TradeAI on Railway

One service, one URL: the `Dockerfile` builds the frontend and the API serves it. Add a Postgres database and a password.

## Steps

1. **Push the repo to GitHub** (Railway deploys from it). Every push to `main` redeploys.
2. **Railway → New Project → Deploy from GitHub repo** → choose this repo. Railway reads `railway.toml` and the root `Dockerfile`; there is nothing to configure for the build.
3. **Add a database:** in the project, **+ New → Database → Add PostgreSQL**. (Without it the SQLite file lives on the container's disk and is wiped on every deploy, taking your watchlist and chat history with it.)
4. **Set variables** on the app service (Variables tab):

   | Variable | Value |
   | --- | --- |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (reference the Postgres service; its name may differ) |
   | `APP_PASSWORD` | a long random password. **Set this**: the AI endpoints spend your model key. |
   | `AI_PROVIDER` | `gemini` |
   | `GEMINI_API_KEY` | your key (omit all AI keys to run on the rules-based explainer only) |
   | `GEMINI_MODEL` | `gemini-3.5-flash-lite` (optional; this is the default) |
   | `REDIS_URL` | optional: `${{Redis.REDIS_URL}}` if you add the Redis plugin |

   Do **not** set `PORT`; Railway injects it.
5. **Settings → Networking → Generate Domain**, then open it. The browser asks for credentials: type anything as the username and `APP_PASSWORD` as the password.
6. **Check:** the deploy logs should end with `Application startup complete`, and `GET /api/health` (open, for Railway's health check) returns `{"ok": true, ...}`.

## Good to know

- **Password:** HTTP Basic auth in front of everything except `/api/health` and the market-data WebSocket (public prices only). It is a shared password, not user accounts.
- **Region:** Binance blocks some countries. If crypto shows "Binance data is unavailable", change the service **Region** (Settings → Deploy). The app already falls back to Binance's public data hosts.
- **Yahoo Finance** is unofficial and may rate-limit cloud IP addresses (HTTP 429); stocks can be flaky for that reason, crypto is unaffected.
- **Keep it to one instance.** Live setups and the cache are held in memory per process; two replicas would disagree. A deploy or restart forgets live setups (they are re-detected from the candles).
- **No Postgres?** Use a Volume instead: add a Volume mounted at `/data` and set `DATABASE_URL=sqlite:////data/tradeai.db`.
- **Cost:** Railway bills usage. The AI cost is the model key's, so keep `APP_PASSWORD` set.

## What has and has not been verified

Verified locally: the app served as a single service behind a password (API, client-side routes, live stream, AI answer), the SPA/path-traversal/password logic (unit tests), and that every table compiles to valid PostgreSQL DDL.
**Not** verified here: the Docker image build (Docker is not installed on the development machine) and a run against a real Postgres server. The first Railway deploy is the first time those run; if the build fails, the build log will say where.
