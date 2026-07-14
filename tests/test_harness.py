"""Harness router endpoint tests via TestClient + MockHermes tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from h3_harness import BaseHarness, Decision, DecisionType, create_router
from h3_harness.protocol import (
    CancelReason,
    End,
    EndReason,
    ResultPayload,
    ResultType,
    TextResponse,
)
from h3_harness.testbed import MockHermes

# ── Test harness ────────────────────────────────────────────────────


class EchoHarness(BaseHarness):
    """Minimal harness that echoes messages and ends on result."""

    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content=f"Echo: {req.message.content}", finished=True),
        )

    async def on_result(self, req):
        return Decision(
            decision=DecisionType.END,
            end=End(reason=EndReason.TASK_COMPLETE.value),
        )


@pytest.fixture()
def app():
    a = FastAPI()
    a.include_router(create_router(EchoHarness()))
    return a


@pytest.fixture()
def client(app):
    return TestClient(app)


# ── Valid helpers ───────────────────────────────────────────────────


def _process_body(content: str = "hello") -> dict:
    return {
        "session_id": "s-1",
        "message": {"content": content, "timestamp": "2025-01-01T00:00:00Z"},
        "identity": {
            "platform": "test",
            "chat_id": "c-1",
            "user_name": "tester",
            "user_id": "u-1",
        },
        "context": {
            "config": {"max_iterations": 10, "timeout_seconds": 300},
            "session_state": {"started_at": "2025-01-01T00:00:00Z"},
        },
    }


def _result_body() -> dict:
    return {
        "session_id": "s-1",
        "decision_id": "d-1",
        "result": {"type": "tool_result", "success": True},
    }


def _cancel_body() -> dict:
    return {"session_id": "s-1", "reason": "user_interrupt"}


# ── GET /v1/health ──────────────────────────────────────────────────


def test_health(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["transport"] == "rest"


# ── POST /v1/process ────────────────────────────────────────────────


def test_process(client):
    r = client.post("/v1/process", json=_process_body("Hello!"))
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "text"
    assert body["text"]["content"] == "Echo: Hello!"
    assert body["text"]["finished"] is True


# ── POST /v1/result ─────────────────────────────────────────────────


def test_result(client):
    r = client.post("/v1/result", json=_result_body())
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "end"
    assert body["end"]["reason"] == "task_complete"


# ── POST /v1/cancel ─────────────────────────────────────────────────


def test_cancel(client):
    r = client.post("/v1/cancel", json=_cancel_body())
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "s-1"
    assert body["cancelled"] is True


# ── GET /v1/sessions/{id} ───────────────────────────────────────────


def test_get_session(client):
    r = client.get("/v1/sessions/sess-123")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "sess-123"
    assert body["status"] == "active"


# ── DELETE /v1/sessions/{id} ────────────────────────────────────────


def test_delete_session(client):
    r = client.delete("/v1/sessions/sess-456")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "sess-456"
    assert body["terminated"] is True


# ── Error handling ──────────────────────────────────────────────────


def test_process_missing_fields_returns_422(client):
    r = client.post("/v1/process", json={})
    assert r.status_code == 422


def test_process_bad_structure_returns_422(client):
    r = client.post("/v1/process", json={"unexpected": "payload"})
    assert r.status_code == 422


# ── Prefix support ──────────────────────────────────────────────────


def test_prefix_support():
    app = FastAPI()
    app.include_router(create_router(EchoHarness(), prefix="/api"))
    c = TestClient(app)

    # Prefixed path works
    r = c.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Non-prefixed path is not found
    r = c.get("/v1/health")
    assert r.status_code == 404


# ── MockHermes tests ────────────────────────────────────────────────


async def test_mock_send_message():
    mock = MockHermes(EchoHarness())
    decision = await mock.send_message("Hello!")
    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.content == "Echo: Hello!"


async def test_mock_send_result():
    mock = MockHermes(EchoHarness())
    result = ResultPayload(type=ResultType.TOOL_RESULT, success=True)
    decision = await mock.send_result(result)
    assert decision.decision == DecisionType.END
    assert decision.end is not None
    assert decision.end.reason == "task_complete"


async def test_mock_send_result_auto_decision_id():
    mock = MockHermes(EchoHarness())
    result = ResultPayload(type=ResultType.TOOL_RESULT, success=True)
    # Should work without explicit decision_id
    decision = await mock.send_result(result)
    assert decision.decision == DecisionType.END


async def test_mock_cancel():
    mock = MockHermes(EchoHarness())
    confirmed = await mock.cancel(session_id="s-1", reason=CancelReason.TIMEOUT)
    assert confirmed is True


async def test_mock_cancel_default_reason():
    mock = MockHermes(EchoHarness())
    confirmed = await mock.cancel()
    assert confirmed is True
