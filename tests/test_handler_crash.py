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

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from h3_harness import BaseHarness, Decision, DecisionType, create_router
from h3_harness.protocol import End, EndReason, TextResponse, ToolCall


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


# --- SDKPY-GAP-065: the masked failure must be DISCOVERABLE -------------------
#
# The masking above is the contract, but on the wire a consumer's broken
# Decision is indistinguishable from a legitimate protocol end: dogfood
# (2026-09-19) returned
#   {"decision":"end","end":{"reason":"error","summary":"1 validation error
#    for ToolCall\nparams\n  Field required ..."}}
# with the traceback living only in the server's stderr. These tests pin the
# two discoverability surfaces added for that: a single WARN naming the masked
# decision, and the opt-in debug_errors=True escape hatch that raises instead.


class BadToolCallDecisionHarness(BaseHarness):
    """A consumer building its Decision with the wrong ToolCall kwargs.

    ``ToolCall`` declares ``name`` / ``params``; ``tool`` / ``arguments`` are
    the plausible-looking-but-wrong names from the GAP-065 dogfood report, so
    the Decision constructor raises a pydantic ``ValidationError`` inside
    ``on_process`` — not a harness bug, a harness-author mistake.
    """

    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TOOL_CALL,
            tool_call=ToolCall(tool="read_file", arguments={}),  # type: ignore[call-arg]
        )

    async def on_result(self, req):
        return Decision(
            decision=DecisionType.END,
            end=End(reason=EndReason.TASK_COMPLETE.value),
        )


def test_bad_decision_is_masked_but_the_cause_is_named_in_a_warn(caplog):
    """A raising consumer Decision yields end/error + ONE discoverable WARN.

    Wire behavior (unchanged, GAP-034 contract): HTTP 200, decision="end",
    end.reason="error", and the exception text — here the pydantic
    ValidationError naming the offending field — in end.summary. Because that
    is indistinguishable from a real `end` to the caller, the masking path
    must ALSO leave a single WARNING line naming the masked decision_id and
    pointing at end.summary, so the failure is findable without reading the
    server's stderr.
    """
    client = _client(BadToolCallDecisionHarness())
    with caplog.at_level(logging.WARNING, logger="h3_harness.harness"):
        r = client.post("/v1/process", json=_process_body())

    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "end"
    assert body["end"]["reason"] == "error"
    summary = body["end"]["summary"]
    # The cause as pydantic renders it: "2 validation errors for ToolCall \
    #  name ... params/n  Field required ...".
    assert "validation error" in summary.lower()
    assert "ToolCall" in summary
    assert "params" in summary

    warns = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert len(warns) == 1, caplog.text
    message = warns[0].getMessage()
    assert body["decision_id"] in message
    assert "end.summary" in message


def test_debug_errors_re_raises_instead_of_masking():
    """``create_router(..., debug_errors=True)`` propagates the failure.

    Dev-mode escape hatch (SDKPY-GAP-065): the exception leaves the handler,
    so the client sees a real HTTP 500 instead of a masked 200 end/error.
    The default (no flag) keeps masking, for both on_process and on_result —
    that is what the battery and existing adopters depend on.
    """
    masked = _client(CrashingProcessHarness())
    assert masked.post("/v1/process", json=_process_body()).status_code == 200

    debug_app = FastAPI()
    debug_app.include_router(create_router(CrashingProcessHarness(), debug_errors=True))
    debug_client = TestClient(debug_app, raise_server_exceptions=False)
    assert debug_client.post("/v1/process", json=_process_body()).status_code == 500

    masked_result = _client(CrashingResultHarness())
    masked_body = masked_result.post("/v1/result", json=_result_body())
    assert masked_body.status_code == 200
    assert masked_body.json()["end"]["reason"] == "error"

    debug_result_app = FastAPI()
    debug_result_app.include_router(
        create_router(CrashingResultHarness(), debug_errors=True)
    )
    debug_result_client = TestClient(debug_result_app, raise_server_exceptions=False)
    assert (
        debug_result_client.post("/v1/result", json=_result_body()).status_code == 500
    )
