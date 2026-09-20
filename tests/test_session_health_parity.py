"""GAP-058: GET /v1/sessions/{id} and GET /v1/health answer ONE source.

Two surfaces used to answer "is this session live?" from two different
sources, so they disagreed for every harness that never writes a status key:

* ``GET /v1/sessions/{id}`` read the harness's own ``get_session_info`` dict
  and, with no ``status`` key, fell back to ``SessionStatus.ACTIVE`` — the
  session read ``active`` forever;
* ``GET /v1/health`` counted the ROUTER's tracking and reported the same
  session as not live (``active_sessions: 0``).

Since GAP-058 both call ``BaseHarness._resolve_status``: an explicit, valid
harness status wins (GAP-035, unchanged), else the router's own tracking
(``BaseHarness.session_status``), else the historical ACTIVE / not-live
defaults. These tests pin the pair TOGETHER — a change that moves one surface
without the other fails here, which is what the split was.

The no-status harness is the AGENTS.md Quickstart shape: ``get_session_info``
returns ``started_at`` + ``turn_count`` and no ``status`` key.
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


class StatedStatusHarness(NoStatusHarness):
    """No-status harness whose dict states ``status`` explicitly.

    ``stated`` is whatever the harness writes there — a valid SessionStatus
    (which must WIN over the router's tracking, the GAP-035 contract) or an
    unrecognised value (which must NOT: it is not a usable statement).
    """

    def __init__(self, stated: str) -> None:
        super().__init__()
        self._stated = stated

    def get_session_info(self, session_id: str) -> dict | None:
        info = self._sessions.get(session_id)
        if info is not None:
            info = {**info, "status": self._stated}
        return info


class KeepAliveHarness(NoStatusHarness):
    """on_result keeps working (never ENDs) — the router stays at active."""

    async def on_result(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="more work", finished=True),
        )


def _client(harness: BaseHarness) -> TestClient:
    app = FastAPI()
    app.include_router(create_router(harness))
    return TestClient(app)


def _process_body(session_id: str = "pm-1") -> dict:
    return {
        "session_id": session_id,
        "message": {"content": "hello", "timestamp": "2025-01-01T00:00:00Z"},
        "identity": {"platform": "test", "chat_id": "c-1"},
        "context": {"config": {}, "session_state": {}},
    }


def _result_body(session_id: str = "pm-1") -> dict:
    return {
        "session_id": session_id,
        "decision_id": "d-1",
        "result": {"type": "text_sent", "success": True},
    }


def _cancel_body(session_id: str = "pm-1") -> dict:
    return {"session_id": session_id, "reason": "user_interrupt"}


def _liveness(client: TestClient, session_id: str = "pm-1") -> tuple[str, int | None]:
    """Both surfaces in one read: (session status, health active_sessions)."""
    session = client.get(f"/v1/sessions/{session_id}")
    assert session.status_code == 200, session.text
    return session.json()["status"], client.get("/v1/health").json()["active_sessions"]


def _assert_agrees(status: str, count: int | None) -> None:
    """completed <-> 0, active <-> 1; anything else is a disagreement."""
    assert (status, count) in (("completed", 0), ("active", 1)), (
        f"the two liveness surfaces disagree: sessions status={status!r}, "
        f"health active_sessions={count!r}"
    )


# ── the no-status harness: the two surfaces must pair ───────────────


def test_no_status_harness_agrees_in_flight():
    """After POST /v1/process: active + 1 (not one each way)."""
    client = _client(NoStatusHarness())
    client.post("/v1/process", json=_process_body())

    _assert_agrees(*_liveness(client))


def test_no_status_harness_agrees_after_end():
    """After POST /v1/result returns END: completed + 0.

    The RED case for GAP-058: pre-fix this read ``active`` (GET) against
    ``0`` (health), and never flipped.
    """
    client = _client(NoStatusHarness())
    client.post("/v1/process", json=_process_body())
    result = client.post("/v1/result", json=_result_body())
    assert result.json()["decision"] == "end"

    status, count = _liveness(client)
    assert status == "completed", "the router-tracked status must reach the wire"
    _assert_agrees(status, count)


def test_no_status_harness_agrees_after_non_end_result():
    """A non-END result keeps the session live on BOTH surfaces."""
    client = _client(KeepAliveHarness())
    client.post("/v1/process", json=_process_body())
    assert client.post("/v1/result", json=_result_body()).json()["decision"] == "text"

    _assert_agrees(*_liveness(client))


def test_no_status_harness_agrees_after_cancel():
    """POST /v1/cancel is not an end — the pair stays active + 1."""
    client = _client(NoStatusHarness())
    client.post("/v1/process", json=_process_body())
    assert client.post("/v1/cancel", json=_cancel_body()).status_code == 200

    _assert_agrees(*_liveness(client))


def test_no_status_harness_agrees_after_delete():
    """DELETE /v1/sessions/{id} marks it completed on both surfaces."""
    client = _client(NoStatusHarness())
    client.post("/v1/process", json=_process_body())
    assert client.delete("/v1/sessions/pm-1").status_code == 200

    status, count = _liveness(client)
    assert status == "completed"
    _assert_agrees(status, count)


# ── the harness's own statement still wins (GAP-035, not regressed) ─


def test_harness_completed_status_wins_over_active_router_tracking():
    """Harness says completed while the router never ended the session."""
    client = _client(StatedStatusHarness("completed"))
    client.post("/v1/process", json=_process_body())

    status, count = _liveness(client)
    assert status == "completed"
    _assert_agrees(status, count)


def test_harness_active_status_wins_over_completed_router_tracking():
    """Harness says active after the router saw END — its word is the answer."""
    client = _client(StatedStatusHarness("active"))
    client.post("/v1/process", json=_process_body())
    assert client.post("/v1/result", json=_result_body()).json()["decision"] == "end"

    status, count = _liveness(client)
    assert status == "active"
    _assert_agrees(status, count)


def test_unrecognised_harness_status_falls_back_to_router_status():
    """A garbage status is no statement — the router's tracking is used.

    Pre-fix this was the second half of the split: GET would answer ACTIVE
    while health counted the same session as not live.
    """
    client = _client(StatedStatusHarness("definitely-not-a-status"))
    client.post("/v1/process", json=_process_body())
    assert client.post("/v1/result", json=_result_body()).json()["decision"] == "end"

    status, count = _liveness(client)
    assert status == "completed"
    _assert_agrees(status, count)


# ── the public accessor itself ──────────────────────────────────────


def test_session_status_is_none_for_a_session_the_router_never_tracked():
    """``None`` means "never tracked", not a status of its own."""
    harness = NoStatusHarness()
    harness._track_session("seen", "active")

    assert harness.session_status("never-seen") is None
    assert harness.session_status("seen") is SessionStatus.ACTIVE


def test_session_status_follows_the_router_lifecycle():
    """process → active, END result → completed, DELETE → completed."""
    harness = NoStatusHarness()
    client = _client(harness)

    assert harness.session_status("pm-1") is None
    client.post("/v1/process", json=_process_body())
    assert harness.session_status("pm-1") is SessionStatus.ACTIVE

    client.post("/v1/result", json=_result_body())
    assert harness.session_status("pm-1") is SessionStatus.COMPLETED

    client.post("/v1/process", json=_process_body())
    assert harness.session_status("pm-1") is SessionStatus.ACTIVE
    client.delete("/v1/sessions/pm-1")
    assert harness.session_status("pm-1") is SessionStatus.COMPLETED
