"""GAP-034: handler exceptions are masked as HTTP 200 end/error decisions.

Contract (README → *Error handling*): exceptions raised inside a harness's
``on_process`` / ``on_result`` are caught by the router and surfaced as an
HTTP 200 Decision with ``decision="end"``, ``end.reason="error"`` and
``end.summary`` carrying the exception text. From the shim's point of view
the session simply ends — it sees a normal ``end`` and stops, so a crashed
session dies silently. Harness authors should validate the decision.

The spec (``get-h3/h3`` → ``specs/04-SDK-Libraries.md``) is silent on
handler-exception behavior, so the 200 masking IS the current contract —
these tests lock it in. Handler-crash coverage in the shim battery
(``get-h3/shim`` → ``test_battery.py``) belongs to that repo and is out of
scope here.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from h3_harness import BaseHarness, Decision, DecisionType, create_router
from h3_harness.protocol import End, EndReason, TextResponse


class CrashingProcessHarness(BaseHarness):
    """on_process always raises — the crash-masking subject of GAP-034."""

    async def on_process(self, req):
        raise RuntimeError("boom in on_process")

    async def on_result(self, req):
        return Decision(
            decision=DecisionType.END,
            end=End(reason=EndReason.TASK_COMPLETE.value),
        )


class CrashingResultHarness(BaseHarness):
    """on_result always raises — the crash-masking subject of GAP-034."""

    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="ok", finished=True),
        )

    async def on_result(self, req):
        raise RuntimeError("boom in on_result")


class CrashingCancelHarness(BaseHarness):
    """on_cancel raises — boundary: this path still returns a real 500."""

    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="ok", finished=True),
        )

    async def on_result(self, req):
        return Decision(
            decision=DecisionType.END,
            end=End(reason=EndReason.TASK_COMPLETE.value),
        )

    async def on_cancel(self, req):
        raise RuntimeError("cancel exploded")


def _client(harness: BaseHarness) -> TestClient:
    app = FastAPI()
    app.include_router(create_router(harness))
    return TestClient(app)


def _process_body() -> dict:
    return {
        "session_id": "s-1",
        "message": {"content": "hello", "timestamp": "2025-01-01T00:00:00Z"},
        "identity": {"platform": "test", "chat_id": "c-1"},
        "context": {"config": {}, "session_state": {}},
    }


def _result_body() -> dict:
    return {
        "session_id": "s-1",
        "decision_id": "d-1",
        "result": {"type": "tool_result", "success": True},
    }


def test_on_process_exception_masked_as_end_error():
    """A crash in on_process is NOT a 500 — it is a 200 end/error decision.

    decision="end", end.reason="error", end.summary carries the exception
    text. This is the documented contract, not a bug to "fix" into a 500.
    """
    client = _client(CrashingProcessHarness())
    r = client.post("/v1/process", json=_process_body())
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "end"
    assert body["end"]["reason"] == "error"
    assert "boom in on_process" in body["end"]["summary"]


def test_on_result_exception_masked_as_end_error():
    """A crash in on_result is masked the same way as on_process."""
    client = _client(CrashingResultHarness())
    r = client.post("/v1/result", json=_result_body())
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "end"
    assert body["end"]["reason"] == "error"
    assert "boom in on_result" in body["end"]["summary"]


def test_on_cancel_exception_still_returns_real_500():
    """Boundary: the masking covers on_process/on_result ONLY.

    on_cancel / on_session_terminate exceptions keep returning real HTTP
    500s (harness.py cancel handler) — the GAP-034 masking must not be
    extended to them.
    """
    client = _client(CrashingCancelHarness())
    r = client.post(
        "/v1/cancel", json={"session_id": "s-1", "reason": "user_interrupt"}
    )
    assert r.status_code == 500
    assert "cancel exploded" in r.json()["detail"]
