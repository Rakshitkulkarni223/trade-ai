"""Production-only pieces: serve the built frontend from the API, and an optional password gate."""
from __future__ import annotations

import base64
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

OPEN_PATHS = {"/api/health"}          # the platform's health check must work without credentials


class PasswordGate:
    """HTTP Basic auth in front of everything except the health check and the market-data WebSocket.

    The WebSocket only carries public prices (no AI, no account data), so leaving it open costs nothing and avoids relying on
    browsers attaching credentials to a socket handshake. Any username is accepted; only the password is checked.
    """

    def __init__(self, app, password: str):
        self.app = app
        self._password = password.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in OPEN_PATHS:
            return await self.app(scope, receive, send)
        header = dict(scope["headers"]).get(b"authorization", b"").decode()
        if header.lower().startswith("basic "):
            try:
                supplied = base64.b64decode(header[6:]).decode().partition(":")[2]
                if secrets.compare_digest(supplied.encode(), self._password):
                    return await self.app(scope, receive, send)
            except Exception:           # malformed header: treat as not authenticated
                pass
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"www-authenticate", b'Basic realm="TradeAI", charset="UTF-8"'),
                                (b"content-type", b"text/plain; charset=utf-8")]})
        await send({"type": "http.response.body", "body": b"Password required."})


def mount_frontend(app: FastAPI, directory: str) -> bool:
    """Serve a built Vite app: hashed assets with long caching, and index.html for every client-side route.
    Registered after the API routers so /api and /ws always win. Returns False if there is nothing to serve."""
    root = Path(directory).resolve()
    index = root / "index.html"
    if not index.is_file():
        return False
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith(("api/", "ws/")) or path in ("api", "ws"):
            raise HTTPException(404)                     # an unknown API path is a 404, not the app shell
        target = (root / path).resolve()
        if path and target.is_file() and root in target.parents:
            return FileResponse(target)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return True
