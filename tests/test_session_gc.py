"""DF4-H3-SHIM-2: BaseHarness purges ended sessions so tracking stays bounded.

The router's ``_live_sessions`` dict used to grow with every finished
conversation: an END result flips the entry to ``"completed"`` and
``active_session_count()`` already stopped counting it (GAP-058), but the
entry itself was never removed — a long-lived harness leaked one dict entry
per session forever. Since DF4-H3-SHIM-2 the count read prunes entries that
resolve not-live, so the dict is bounded by LIVE sessions while the other
status reads keep resolving the ended session until then (GAP-058 parity is
untouched — see ``tests/test_session_health_parity.py``).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from h3_harness import BaseHarness, Decision, DecisionType, SessionStatus, create_router
from h3_harness.protocol import End, EndReason, TextResponse


class NoStatusHarness(BaseHarness):
    """AGENTS.md Quickstart shape — metadata only, never a status key."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    async def on_process(self, req):
        sid = req.session_id
        self._sessions[sid] = {
            "started_at": "2025-01-01T00:00:00Z",
            "turn_count": self._sessions.get(sid, {}).get("turn_count", 0) + 1,
        }
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


def _process_body(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "message": {"content": "hello", "timestamp": "2025-01-01T00:00:00Z"},
        "identity": {"platform": "test", "chat_id": "c-1"},
        "context": {"config": {}, "session_state": {}},
    }


def _result_body(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "decision_id": "d-1",
        "result": {"type": "text_sent", "success": True},
    }


def _run_session(client: TestClient, session_id: str) -> None:
    """One full process → result(END) conversation."""
    assert (
        client.post("/v1/process", json=_process_body(session_id)).json()["decision"]
        == "text"
    )
    assert (
        client.post("/v1/result", json=_result_body(session_id)).json()["decision"]
        == "end"
    )


def test_health_reports_zero_after_end_and_prunes_tracking():
    """After END: health counts 0 AND the tracking entry is gone."""
    harness = NoStatusHarness()
    client = _client(harness)
    _run_session(client, "gc-1")

    assert harness.session_status("gc-1") is SessionStatus.COMPLETED
    assert client.get("/v1/health").json()["active_sessions"] == 0
    assert harness._live_sessions == {}


def test_ended_sessions_do_not_accumulate_across_conversations():
    """N full conversations leave zero tracked entries after a health read."""
    harness = NoStatusHarness()
    client = _client(harness)
    for i in range(5):
        _run_session(client, f"gc-{i}")

    assert len(harness._live_sessions) == 5
    for _ in range(5):
        assert client.get("/v1/health").json()["active_sessions"] == 0
    assert harness._live_sessions == {}


def test_status_reads_still_resolve_the_ended_session_before_a_health_read():
    """GAP-058 parity is untouched: the prune happens on the count read."""
    harness = NoStatusHarness()
    client = _client(harness)
    _run_session(client, "gc-1")

    session = client.get("/v1/sessions/gc-1")
    assert session.status_code == 200
    assert session.json()["status"] == "completed"
    assert harness.session_status("gc-1") is SessionStatus.COMPLETED


def test_in_flight_sessions_survive_the_prune():
    """A live session is counted — and kept — while ended ones are pruned."""
    harness = NoStatusHarness()
    client = _client(harness)
    _run_session(client, "gc-ended")
    client.post("/v1/process", json=_process_body("gc-live"))

    assert client.get("/v1/health").json()["active_sessions"] == 1
    assert harness._live_sessions == {"gc-live": "active"}
    assert harness.session_status("gc-live") is SessionStatus.ACTIVE
