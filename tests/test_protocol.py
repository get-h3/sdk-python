"""Protocol serialization + validation tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from h3_harness.protocol import (
    CancelReason,
    CancelRequest,
    Capability,
    Config,
    Context,
    Decision,
    DecisionType,
    End,
    EndReason,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    Identity,
    LLMCall,
    LLMMessage,
    Message,
    ProcessRequest,
    ResultPayload,
    ResultRequest,
    ResultType,
    SessionResponse,
    SessionState,
    SessionStatus,
    TextResponse,
    ToolCall,
    Wait,
)

# ── Helpers ─────────────────────────────────────────────────────────


def _config() -> Config:
    return Config(max_iterations=10, timeout_seconds=300)


def _session_state() -> SessionState:
    return SessionState(started_at="2025-01-01T00:00:00Z")


def _context() -> Context:
    return Context(config=_config(), session_state=_session_state())


def _message(content: str = "hello") -> Message:
    return Message(content=content, timestamp="2025-01-01T00:00:00Z")


def _identity() -> Identity:
    return Identity(
        platform="test",
        chat_id="test",
        user_name="tester",
        user_id="u-1",
    )


def _result_payload() -> ResultPayload:
    return ResultPayload(type=ResultType.TOOL_RESULT, success=True)


def assert_round_trip(model_cls, instance):
    """model → json → model → verify dumps match."""
    original_dump = instance.model_dump(mode="json")
    json_str = json.dumps(original_dump)
    restored = model_cls.model_validate_json(json_str)
    assert restored.model_dump(mode="json") == original_dump


# ── Round-trip: Decision variations ─────────────────────────────────


def test_decision_text_round_trip():
    d = Decision(
        decision=DecisionType.TEXT,
        text=TextResponse(content="Hello!", finished=True),
    )
    assert_round_trip(Decision, d)


def test_decision_tool_call_round_trip():
    d = Decision(
        decision=DecisionType.TOOL_CALL,
        tool_call=ToolCall(name="search", params={"q": "cats"}, reasoning="need info"),
    )
    assert_round_trip(Decision, d)


def test_decision_end_round_trip():
    d = Decision(
        decision=DecisionType.END,
        end=End(reason="task_complete", summary="Done!"),
    )
    assert_round_trip(Decision, d)


# ── Round-trip: Request / Response models ───────────────────────────


def test_process_request_round_trip():
    req = ProcessRequest(
        session_id="s-1",
        message=_message("test message"),
        identity=_identity(),
        context=_context(),
    )
    assert_round_trip(ProcessRequest, req)


def test_result_request_round_trip():
    req = ResultRequest(
        session_id="s-1",
        decision_id="d-1",
        result=_result_payload().model_dump(),
    )
    assert_round_trip(ResultRequest, req)


def test_cancel_request_round_trip():
    req = CancelRequest(session_id="s-1", reason=CancelReason.USER_INTERRUPT)
    assert_round_trip(CancelRequest, req)


def test_health_response_round_trip():
    resp = HealthResponse(
        status=HealthStatus.OK,
        version="1.0.0",
        capabilities=[Capability.TEXT, Capability.END],
    )
    assert_round_trip(HealthResponse, resp)


def test_error_response_round_trip():
    resp = ErrorResponse(
        error=ErrorDetail(
            code=ErrorCode.INVALID_REQUEST,
            message="Bad payload",
            details={"field": "message"},
        ).model_dump(),
    )
    assert_round_trip(ErrorResponse, resp)


def test_session_response_round_trip():
    resp = SessionResponse(
        session_id="s-1",
        started_at="2025-01-01T00:00:00Z",
        last_active="2025-01-01T00:05:00Z",
        turn_count=3,
        status=SessionStatus.ACTIVE,
    )
    assert_round_trip(SessionResponse, resp)


# ── Validation: enum rejection ──────────────────────────────────────


def test_decision_type_rejects_invalid():
    with pytest.raises(ValidationError):
        Decision(decision="not_a_real_type")


def test_end_reason_rejects_invalid():
    with pytest.raises(ValueError):
        EndReason("totally_bogus")


# ── Validation: field constraints ───────────────────────────────────


def test_llm_call_temperature_too_high():
    with pytest.raises(ValidationError):
        LLMCall(
            model="gpt-4",
            messages=[LLMMessage(role="user", content="hi")],
            temperature=3.0,
        )


def test_llm_call_temperature_negative():
    with pytest.raises(ValidationError):
        LLMCall(
            model="gpt-4",
            messages=[LLMMessage(role="user", content="hi")],
            temperature=-0.5,
        )


def test_wait_duration_seconds_zero():
    with pytest.raises(ValidationError):
        Wait(reason="polling", duration_seconds=0)


def test_wait_duration_seconds_negative():
    with pytest.raises(ValidationError):
        Wait(reason="polling", duration_seconds=-5)


def test_result_payload_duration_ms_negative():
    with pytest.raises(ValidationError):
        ResultPayload(type=ResultType.TOOL_RESULT, success=True, duration_ms=-1)


def test_result_payload_success_required():
    with pytest.raises(ValidationError):
        ResultPayload(type=ResultType.TOOL_RESULT)


# ── ErrorResponse serialization ─────────────────────────────────────


def test_error_response_json_serializable():
    resp = ErrorResponse(
        error=ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="kaboom",
        ).model_dump(),
    )
    d = resp.model_dump(mode="json")
    # Must be JSON-serializable
    json.dumps(d)
    assert d["error"]["code"] == "INTERNAL_ERROR"
    assert d["error"]["message"] == "kaboom"


# ── UUID auto-generation ────────────────────────────────────────────


def test_decision_uuid_auto_generation():
    d = Decision(
        decision=DecisionType.TEXT,
        text=TextResponse(content="x", finished=True),
    )
    assert d.decision_id is not None
    assert isinstance(d.decision_id, str)
    assert len(d.decision_id) > 0


def test_decision_explicit_id_preserved():
    d = Decision(
        decision=DecisionType.TEXT,
        decision_id="my-custom-id",
        text=TextResponse(content="x", finished=True),
    )
    assert d.decision_id == "my-custom-id"
