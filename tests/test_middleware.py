"""Tests for h3_harness.middleware — request logging and error handling."""

from __future__ import annotations

import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from h3_harness.middleware import _RequestLoggingMiddleware, add_middleware

# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture()
def app():
    a = FastAPI()
    add_middleware(a)
    return a


@pytest.fixture()
def client(app):
    return TestClient(app)


# ── Success path ────────────────────────────────────────────────


def test_success_path_returns_response(caplog):
    """A successful request returns 200 and logs method/path/status."""
    app = FastAPI()
    add_middleware(app)

    @app.get("/hello")
    async def hello():
        return {"msg": "world"}

    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        r = client.get("/hello")

    assert r.status_code == 200
    assert r.json() == {"msg": "world"}

    # Log should contain method, path, status, and duration
    assert len(caplog.records) >= 1
    msg = caplog.records[0].getMessage()
    assert "GET" in msg
    assert "/hello" in msg
    assert "200" in msg
    assert re.search(r"\d+ms", msg), f"Expected duration in ms, got: {msg}"


# ── Error path ──────────────────────────────────────────────────


def test_error_path_returns_500_json_response(caplog):
    """An exception in a route handler returns 500 JSONResponse with error body."""
    app = FastAPI()
    add_middleware(app)

    @app.get("/fail")
    async def fail():
        raise ValueError("test error message")

    client = TestClient(app)

    with caplog.at_level(logging.ERROR):
        r = client.get("/fail")

    assert r.status_code == 500

    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["message"] == "test error message"

    # Log should contain the exception info
    assert len(caplog.records) >= 1
    msg = caplog.records[0].getMessage()
    assert "GET" in msg
    assert "/fail" in msg
    assert "500" in msg
    assert "test error message" in msg or "ValueError" in msg


# ── add_middleware function ─────────────────────────────────────


def test_add_middleware_attaches_middleware():
    """add_middleware() correctly attaches _RequestLoggingMiddleware."""
    app = FastAPI()
    assert len(app.user_middleware) == 0

    add_middleware(app)
    assert len(app.user_middleware) == 1
    assert app.user_middleware[0].cls == _RequestLoggingMiddleware

    # Verify it actually runs when a request is made
    @app.get("/ping")
    async def ping():
        return {"pong": True}

    client = TestClient(app)
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.json() == {"pong": True}


# ── Logging format ──────────────────────────────────────────────


def test_logging_format_contains_all_parts(caplog):
    """Log messages include method, path, status, and duration marker."""
    app = FastAPI()
    add_middleware(app)

    @app.get("/format-test")
    async def route():
        return {"ok": True}

    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        r = client.get("/format-test")

    assert r.status_code == 200

    assert len(caplog.records) >= 1
    msg = caplog.records[0].getMessage()

    # The format string from middleware: "%s %s → %d (%dms)"
    assert " → " in msg, f"Expected arrow separator in log: {msg}"
    assert re.search(r"\(\d+ms\)", msg), f"Expected (Nms) in log: {msg}"


# ── Logger name ─────────────────────────────────────────────────


def test_logger_name_is_h3_harness(caplog):
    """Requests are logged under the 'h3_harness' logger."""
    app = FastAPI()
    add_middleware(app)

    @app.get("/logger-check")
    async def route():
        return {"ok": True}

    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        r = client.get("/logger-check")

    assert r.status_code == 200

    assert len(caplog.records) >= 1
    assert caplog.records[0].name == "h3_harness"


# ── Error path: different exception types ───────────────────────


def test_error_path_various_exceptions(caplog):
    """Middleware catches different exception types and returns 500."""
    app = FastAPI()
    add_middleware(app)

    @app.get("/key-error")
    async def key_error():
        return {}["missing_key"]  # raises KeyError

    client = TestClient(app)

    with caplog.at_level(logging.ERROR):
        r = client.get("/key-error")

    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    # The message should mention 'missing_key'
    assert "missing_key" in body["error"]["message"]
