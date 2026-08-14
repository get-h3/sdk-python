"""GAP-035: GET /v1/sessions/{id} passes through get_session_info status.

The router used to hardcode ``status=active`` on every session response.
Since GAP-035 it reads the ``status`` key from the harness's
``get_session_info`` dict and validates it against ``SessionStatus``
("active"/"completed"/"expired"/"cancelled"); unknown or invalid values fall
back to ACTIVE, and harnesses that return no status key at all keep getting
ACTIVE (backward compatible — the pre-GAP-035 contract).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from h3_harness import BaseHarness, Decision, DecisionType, create_router
from h3_harness.protocol import End, EndReason, TextResponse


class StatusTrackingHarness(BaseHarness):
    """Tracks per-session status: active on process, completed after END.

    Mirrors the canonical echo.py (GAP-035) convention: on_result returns an
    END decision once the exchange is finished and marks the session
    completed.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    async def on_process(self, req):
        sid = req.session_id
        self._sessions[sid] = {
            "started_at": "2025-01-01T00:00:00Z",
            "turn_count": self._sessions.get(sid, {}).get("turn_count", 0) + 1,
            "status": "active",
        }
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="ok", finished=True),
        )

    async def on_result(self, req):
        sid = req.session_id
        if sid in self._sessions:
            self._sessions[sid]["turn_count"] = (
                self._sessions[sid].get("turn_count", 0) + 1
            )
            self._sessions[sid]["status"] = "completed"
        return Decision(
            decision=DecisionType.END,
            end=End(reason=EndReason.TASK_COMPLETE.value),
        )

    def get_session_info(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)


class InvalidStatusHarness(StatusTrackingHarness):
    """Same tracking, but with a garbage status value to test validation."""

    def get_session_info(self, session_id: str) -> dict | None:
        info = self._sessions.get(session_id)
        if info is not None:
            info = {**info, "status": "definitely-not-a-status"}
        return info


class NoStatusHarness(BaseHarness):
    """Backward-compat: get_session_info has no status key at all."""

    _sessions = {"legacy-sess": {"started_at": "2025-01-01T00:00:00Z", "turn_count": 2}}

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

    def get_session_info(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)


def _client(harness: BaseHarness) -> TestClient:
    app = FastAPI()
    app.include_router(create_router(harness))
    return TestClient(app)


def _process_body(session_id: str = "conv-001") -> dict:
    return {
        "session_id": session_id,
        "message": {"content": "hello", "timestamp": "2025-01-01T00:00:00Z"},
        "identity": {"platform": "test", "chat_id": "c-1"},
        "context": {"config": {}, "session_state": {}},
    }


def _result_body(session_id: str = "conv-001", decision_id: str = "d-1") -> dict:
    return {
        "session_id": session_id,
        "decision_id": decision_id,
        "result": {"type": "text_sent", "success": True},
    }


def test_in_flight_session_reports_active():
    """A session that has been processed but not ended → status active."""
    client = _client(StatusTrackingHarness())
    client.post("/v1/process", json=_process_body())
    r = client.get("/v1/sessions/conv-001")
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_completed_session_reports_completed():
    """A full process → result(END) loop → status completed (wire truth)."""
    client = _client(StatusTrackingHarness())
    resp = client.post("/v1/process", json=_process_body())
    assert resp.json()["decision"] == "text"

    # Still in flight before the result arrives.
    assert client.get("/v1/sessions/conv-001").json()["status"] == "active"

    resp = client.post("/v1/result", json=_result_body())
    assert resp.json()["decision"] == "end"
    assert resp.json()["end"]["reason"] == "task_complete"

    # After the END decision the session reports completed.
    r = client.get("/v1/sessions/conv-001")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


def test_unknown_status_value_falls_back_to_active():
    """An invalid status string is rejected → ACTIVE (safe option)."""
    client = _client(InvalidStatusHarness())
    client.post("/v1/process", json=_process_body())
    r = client.get("/v1/sessions/conv-001")
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_no_status_key_defaults_to_active():
    """Backward compat: harnesses without a status key keep getting ACTIVE."""
    client = _client(NoStatusHarness())
    r = client.get("/v1/sessions/legacy-sess")
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert r.json()["turn_count"] == 2
