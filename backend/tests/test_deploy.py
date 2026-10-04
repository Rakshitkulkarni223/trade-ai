"""Production pieces: serving the built frontend, the optional password, and Railway-style database URLs."""
import asyncio
import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import normalise_database_url
from app.web import PasswordGate, mount_frontend


@pytest.fixture()
def site(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>APP SHELL</html>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log('hi')")
    (tmp_path / "favicon.txt").write_text("icon")
    (tmp_path.parent / "secret.txt").write_text("TOP SECRET")
    api = FastAPI()

    @api.get("/api/health")
    def health():
        return {"ok": True}

    @api.get("/api/private")
    def private():
        return {"data": 1}
    assert mount_frontend(api, str(tmp_path)) is True
    return api


def test_home_and_client_side_routes_get_the_app_shell(site):
    c = TestClient(site)
    for path in ("/", "/chart/BTCUSDT", "/watchlist", "/some/deep/route"):
        r = c.get(path)
        assert r.status_code == 200 and "APP SHELL" in r.text, path
    assert "no-cache" in c.get("/").headers["cache-control"]        # a new deploy must not be hidden behind a cached shell


def test_assets_and_real_files_are_served_as_themselves(site):
    c = TestClient(site)
    assert c.get("/assets/app-abc123.js").text == "console.log('hi')"
    assert c.get("/favicon.txt").text == "icon"


def test_api_paths_are_never_swallowed_by_the_app_shell(site):
    c = TestClient(site)
    assert c.get("/api/private").json() == {"data": 1}
    r = c.get("/api/does-not-exist")
    assert r.status_code == 404 and "APP SHELL" not in r.text      # a typo'd API call must fail loudly, not return HTML


def test_path_traversal_cannot_read_files_outside_the_site(site):
    c = TestClient(site)
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "/assets/../../secret.txt"):
        r = c.get(path)
        assert "TOP SECRET" not in r.text, path


def test_a_missing_build_directory_is_reported_not_crashed(tmp_path):
    assert mount_frontend(FastAPI(), str(tmp_path / "nope")) is False


# ------------------------------------------------------------------ password gate
def basic(user, pw):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


def test_password_gate(site):
    c = TestClient(PasswordGate(site, "s3cret"))
    r = c.get("/")
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")
    assert c.get("/api/private").status_code == 401
    assert c.get("/", headers=basic("anyone", "wrong")).status_code == 401
    assert c.get("/", headers=basic("anyone", "s3cret")).status_code == 200     # any username, right password
    assert c.get("/api/private", headers=basic("x", "s3cret")).json() == {"data": 1}
    assert c.get("/", headers={"Authorization": "Basic !!!not-base64"}).status_code == 401
    assert c.get("/", headers={"Authorization": "Bearer s3cret"}).status_code == 401


def test_health_check_stays_open_for_the_platform(site):
    assert TestClient(PasswordGate(site, "s3cret")).get("/api/health").json() == {"ok": True}


def test_websocket_scope_passes_through_the_gate():
    """Prices only: the gate protects HTTP, and a websocket handshake must not be rejected by it."""
    reached = []

    async def inner(scope, receive, send):
        reached.append(scope["type"])
    gate = PasswordGate(inner, "s3cret")
    asyncio.run(gate({"type": "websocket", "path": "/ws/market/BTCUSDT", "headers": []}, None, None))
    assert reached == ["websocket"]


# ------------------------------------------------------------------ database url
@pytest.mark.parametrize("given,expected", [
    ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),       # already explicit: untouched
    ("sqlite:///./tradeai.db", "sqlite:///./tradeai.db"),
    ("sqlite:////data/tradeai.db", "sqlite:////data/tradeai.db"),
])
def test_database_url_gets_the_right_driver(given, expected):
    assert normalise_database_url(given) == expected
