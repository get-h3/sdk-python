"""Session GC: ended sessions are purged on the END decision, not on a read.

Two halves of one story, and both matter:

* DF4-H3-SHIM-2 — the router's ``_live_sessions`` dict grew by one entry per
  finished conversation: an END result overwrote the entry with
  ``"completed"`` and only ``active_session_count()`` ever pruned it, so
  nothing bounded the dict unless something happened to read health.
* SDKPY-GAP-063b — the purge moved to the END write itself. The live map
  now holds LIVE sessions only; the ended status is kept for a bounded
  closing window (``_ended_sessions``, capped by ``_ended_session_cap``) so
  ``GET /v1/sessions/{id}`` and ``session_status()`` keep reporting a
  truthful ``completed`` (the GAP-058 parity pinned in
  ``tests/test_session_health_parity.py``) while a session whose result was
  NOT final — text, tool_call, llm_call: the conversation continues — stays
  live and is never purged early.

Mirrors the shim scaffold fix (get-h3/shim d62dc7f): purge on the END
decision, keep a bounded closing memory, never an unbounded live table.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from h3_harness import BaseHarness, Decision, DecisionType, SessionStatus, create_router
from h3_harness.protocol import End, EndReason, TextResponse


class NoStatusHarness(BaseHarness):
    """AGENTS.md Quickstart shape — metadata only, never a status key.

    Its own ``get_session_info`` dict keeps every session forever (the
    shape adopters ship), so nothing the harness does helps the router's
    live map: the purge has to happen in the router.
    """

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


class MultiTurnHarness(NoStatusHarness):
    """``on_result`` answers with more text until ``end_after`` results.

    ``end_after=None`` never ends: every result is non-final and the session
    must stay live.
    """

    def __init__(self, end_after: int | None = None) -> None:
        super().__init__()
        self._end_after = end_after
        self.results = 0

    async def on_result(self, req):
        self.results += 1
        if self._end_after is not None and self.results >= self._end_after:
            return Decision(
                decision=DecisionType.END,
                end=End(reason=EndReason.TASK_COMPLETE.value),
            )
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="more work", finished=True),
        )


class CrashingResultHarness(NoStatusHarness):
    """``on_result`` raises — the router masks it as an END/``error`` decision."""

    async def on_result(self, req):
        raise RuntimeError("boom in on_result")


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


def _live(harness: BaseHarness) -> dict:
    """The router's live map — sessions the router still considers live."""
    return getattr(harness, "_live_sessions", None) or {}


def _ended(harness: BaseHarness) -> dict:
    """The router's bounded ended window — recent terminal statuses."""
    return getattr(harness, "_ended_sessions", None) or {}


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
    """N full conversations leave the live map empty — no health read needed."""
    harness = NoStatusHarness()
    client = _client(harness)
    for i in range(5):
        _run_session(client, f"gc-{i}")

    assert _live(harness) == {}
    for _ in range(5):
        assert client.get("/v1/health").json()["active_sessions"] == 0
    assert harness._live_sessions == {}


def test_status_reads_still_resolve_the_ended_session_before_a_health_read():
    """GAP-058 parity is untouched: the ended window answers for the session."""
    harness = NoStatusHarness()
    client = _client(harness)
    _run_session(client, "gc-1")

    session = client.get("/v1/sessions/gc-1")
    assert session.status_code == 200
    assert session.json()["status"] == "completed"
    assert harness.session_status("gc-1") is SessionStatus.COMPLETED


def test_in_flight_sessions_survive_the_prune():
    """A live session is counted — and kept — while ended ones are gone."""
    harness = NoStatusHarness()
    client = _client(harness)
    _run_session(client, "gc-ended")
    client.post("/v1/process", json=_process_body("gc-live"))

    assert client.get("/v1/health").json()["active_sessions"] == 1
    assert harness._live_sessions == {"gc-live": "active"}
    assert harness.session_status("gc-live") is SessionStatus.ACTIVE


# ── SDKPY-GAP-063b: the END decision purges the live entry ──────────


def test_end_decision_purges_the_session_from_the_live_map():
    """One-shot conversation: the entry leaves the live map AT the END write.

    RED before the fix: the END result overwrote the entry with
    ``"completed"`` and left it in ``_live_sessions`` until something read
    health. Green after: the live map is empty the moment the decision
    lands, with no read in between, and the ended window keeps the status
    truthful for GET /v1/sessions/{id}.
    """
    harness = NoStatusHarness()
    client = _client(harness)
    _run_session(client, "one-shot")

    assert harness._live_sessions == {}
    assert "one-shot" not in _live(harness)
    assert harness.session_status("one-shot") is SessionStatus.COMPLETED
    assert client.get("/v1/health").json()["active_sessions"] == 0

    # Health counted the session as not live, but the read must NOT erase the
    # ended window: GET /v1/sessions/{id} still answers "completed"
    # afterwards. The two liveness surfaces may never disagree (GAP-058), and
    # a read that did strip the memory would split them in this order.
    assert _ended(harness) == {"one-shot": "completed"}
    session = client.get("/v1/sessions/one-shot")
    assert session.status_code == 200
    assert session.json()["status"] == "completed"


def test_one_shot_conversations_do_not_accumulate_in_the_live_map():
    """50 one-shot conversations leave the live map empty (RED: 50 entries)."""
    harness = NoStatusHarness()
    client = _client(harness)
    for i in range(50):
        _run_session(client, f"burst-{i}")

    assert _live(harness) == {}
    assert len(_ended(harness)) == 50
    assert client.get("/v1/health").json()["active_sessions"] == 0


def test_ended_window_is_bounded_by_the_cap():
    """The ended window keeps the most recent N — ended sessions cannot pile up."""

    class TinyWindowHarness(NoStatusHarness):
        _ended_session_cap = 3

    harness = TinyWindowHarness()
    client = _client(harness)
    for i in range(10):
        _run_session(client, f"cap-{i}")

    assert _live(harness) == {}
    assert _ended(harness) == {
        "cap-7": "completed",
        "cap-8": "completed",
        "cap-9": "completed",
    }
    assert client.get("/v1/health").json()["active_sessions"] == 0


def test_zero_cap_disables_the_ended_window():
    """``_ended_session_cap = 0`` keeps no memory at all — pure purge."""

    class NoWindowHarness(NoStatusHarness):
        _ended_session_cap = 0

    harness = NoWindowHarness()
    client = _client(harness)
    _run_session(client, "no-window")

    assert _live(harness) == {}
    assert _ended(harness) == {}
    assert harness.session_status("no-window") is None
    assert client.get("/v1/health").json()["active_sessions"] == 0


def test_multi_turn_session_is_not_purged_by_a_non_final_result():
    """text result → text result → … : the session stays live throughout."""
    harness = MultiTurnHarness()
    client = _client(harness)
    client.post("/v1/process", json=_process_body("multi"))

    for _ in range(3):
        assert (
            client.post("/v1/result", json=_result_body("multi")).json()["decision"]
            == "text"
        )
        assert _live(harness) == {"multi": "active"}
        assert _ended(harness) == {}
        assert harness.session_status("multi") is SessionStatus.ACTIVE
        assert client.get("/v1/health").json()["active_sessions"] == 1


def test_multi_turn_session_is_purged_only_by_its_end_decision():
    """The same session is purged by the END that closes it — and not before."""
    harness = MultiTurnHarness(end_after=3)
    client = _client(harness)
    client.post("/v1/process", json=_process_body("multi"))

    for _ in range(2):
        assert (
            client.post("/v1/result", json=_result_body("multi")).json()["decision"]
            == "text"
        )
    assert _live(harness) == {"multi": "active"}

    assert (
        client.post("/v1/result", json=_result_body("multi")).json()["decision"]
        == "end"
    )
    assert _live(harness) == {}
    assert harness.session_status("multi") is SessionStatus.COMPLETED
    assert client.get("/v1/health").json()["active_sessions"] == 0


def test_end_error_decision_purges_the_session_too():
    """A crashed on_result is masked as END/error — it ends the exchange."""
    harness = CrashingResultHarness()
    client = _client(harness)
    client.post("/v1/process", json=_process_body("crash"))

    body = client.post("/v1/result", json=_result_body("crash")).json()
    assert body["decision"] == "end"
    assert body["end"]["reason"] == "error"

    assert _live(harness) == {}
    assert harness.session_status("crash") is SessionStatus.COMPLETED
    assert client.get("/v1/health").json()["active_sessions"] == 0
