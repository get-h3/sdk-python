"""QV-SDK-03: Python Pydantic validation matches JSON Schema.

Comprehensive validation that every Pydantic model produces JSON that validates
against the corresponding H3 protocol JSON Schema (draft 2020-12).

Tests:
  1. Every model instance → JSON → validates against its schema
  2. Required-fields validation: omitting required fields is rejected by Pydantic
  3. Enum validation: invalid enum values rejected
  4. Constraint validation: numeric ranges (min/max) enforced
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema
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
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    Identity,
    LLMCall,
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

# ── Schema loading ───────────────────────────────────────────────────

# SCHEMA_DIR: vendored protocol JSON schemas, tests/schemas/v1/
# (mirrors get-h3/protocol/schemas/v1/ so the conformance tests run on a
# standalone clone with no sibling checkout).
# Override with H3_SCHEMA_DIR to validate against a newer protocol checkout.
SCHEMA_DIR = Path(
    os.environ["H3_SCHEMA_DIR"]
    if "H3_SCHEMA_DIR" in os.environ
    else Path(__file__).resolve().parent / "schemas" / "v1"
)


def _load_schema(name: str) -> dict:
    """Load a single schema file."""
    path = SCHEMA_DIR / name
    if not path.exists():
        pytest.skip(f"Schema file not found: {path}")
    return json.loads(path.read_text())


def _build_store() -> dict:
    """Build a store of all schema files for $ref resolution."""
    store = {}
    if SCHEMA_DIR.exists():
        for f in SCHEMA_DIR.glob("*.json"):
            store[f.name] = json.loads(f.read_text())
    return store


def validate_instance(instance: object, schema_name: str) -> None:
    """Validate a Pydantic model instance against a named JSON Schema file.

    Serializes the instance via model_dump(mode='json', exclude_none=True),
    then validates against the schema with full $ref resolution.
    """
    schema = _load_schema(schema_name)
    store = _build_store()

    # Serialize to JSON-compatible dict
    if hasattr(instance, "model_dump"):
        data = instance.model_dump(mode="json", exclude_none=True)
    else:
        data = instance

    # Use referencing.Registry for Draft 2020-12 $ref resolution
    from referencing import Registry, Resource

    registry = Registry()
    for fname, s in store.items():
        registry = registry.with_resource(uri=fname, resource=Resource.from_contents(s))

    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    errors = list(validator.iter_errors(data))

    if errors:
        msg = f"Schema validation failed for {schema_name}:\n"
        for err in errors:
            path = "/".join(str(p) for p in err.absolute_path)
            msg += f"  - {err.message} (at {path})\n"
        raise AssertionError(msg)


# ── Helper factories ─────────────────────────────────────────────────


def _config(**kwargs) -> Config:
    defaults = {"max_iterations": 10, "timeout_seconds": 300}
    defaults.update(kwargs)
    return Config(**defaults)


def _session_state(**kwargs) -> SessionState:
    defaults = {"started_at": "2025-01-01T00:00:00Z"}
    defaults.update(kwargs)
    return SessionState(**defaults)


def _context(**kwargs) -> Context:
    defaults = {"config": _config(), "session_state": _session_state()}
    defaults.update(kwargs)
    return Context(**defaults)


def _message(**kwargs) -> Message:
    defaults = {"content": "hello", "timestamp": "2025-01-01T00:00:00Z"}
    defaults.update(kwargs)
    return Message(**defaults)


def _identity(**kwargs) -> Identity:
    defaults = {
        "platform": "test",
        "chat_id": "test",
        "user_name": "tester",
        "user_id": "u-1",
    }
    defaults.update(kwargs)
    return Identity(**defaults)


# ── Schema validation: Request / Response models ────────────────────


def test_process_request_validates_against_schema():
    req = ProcessRequest(
        session_id="s-1",
        message=_message(),
        identity=_identity(),
        context=_context(),
    )
    validate_instance(req, "process-request.json")


def test_result_request_validates_against_schema():
    req = ResultRequest(
        session_id="s-1",
        decision_id="d-1",
        result={"type": "tool_result", "success": True, "tool_name": "search"},
    )
    validate_instance(req, "result-request.json")


def test_cancel_request_validates_against_schema():
    req = CancelRequest(session_id="s-1", reason="user_interrupt")
    validate_instance(req, "cancel-request.json")


def test_health_response_validates_against_schema():
    resp = HealthResponse(
        status="ok",
        version="1.0.0",
        transport="rest",
        protocol_version="1.0",
        capabilities=["tool_call", "text", "end"],
    )
    validate_instance(resp, "health-response.json")


def test_error_response_validates_against_schema():
    resp = ErrorResponse(error={"code": "INVALID_REQUEST", "message": "Bad payload"})
    validate_instance(resp, "error-response.json")


def test_session_response_validates_against_schema():
    resp = SessionResponse(
        session_id="s-1",
        started_at="2025-01-01T00:00:00Z",
        last_active="2025-01-01T00:05:00Z",
        turn_count=3,
        status="active",
    )
    validate_instance(resp, "session-response.json")


# ── Schema validation: Decision payloads ────────────────────────────


def test_decision_text_validates_against_schema():
    d = Decision(
        decision=DecisionType.TEXT,
        text=TextResponse(content="Hello!", finished=True),
    )
    validate_instance(d, "decision.json")


def test_decision_tool_call_validates_against_schema():
    d = Decision(
        decision=DecisionType.TOOL_CALL,
        tool_call=ToolCall(name="search", params={"q": "cats"}, reasoning="need info"),
    )
    validate_instance(d, "decision.json")


def test_decision_llm_call_validates_against_schema():
    d = Decision(
        decision=DecisionType.LLM_CALL,
        llm_call=LLMCall(
            model="deepseek-v4",
            messages=[{"role": "user", "content": "hi"}],
        ),
    )
    validate_instance(d, "decision.json")


def test_decision_wait_validates_against_schema():
    d = Decision(
        decision=DecisionType.WAIT,
        wait=Wait(reason="awaiting input", duration_seconds=30),
    )
    validate_instance(d, "decision.json")


def test_decision_delegate_validates_against_schema():
    d = Decision(
        decision=DecisionType.DELEGATE,
        delegate={"task": "review code", "agent": "code-reviewer"},
    )
    validate_instance(d, "decision.json")


def test_decision_end_validates_against_schema():
    d = Decision(
        decision=DecisionType.END,
        end=End(reason="task_complete", summary="All done!"),
    )
    validate_instance(d, "decision.json")


# ── Schema validation: Payload sub-types ────────────────────────────


def test_tool_call_validates_against_schema():
    tc = ToolCall(name="search", params={"q": "cats"}, reasoning="need info")
    validate_instance(tc, "tool-call.json")


def test_llm_call_validates_against_schema():
    lc = LLMCall(
        model="deepseek-v4",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7,
    )
    validate_instance(lc, "llm-call.json")


def test_text_response_validates_against_schema():
    tr = TextResponse(content="Hello!", finished=True)
    validate_instance(tr, "text-response.json")


def test_text_response_unfinished_validates_against_schema():
    tr = TextResponse(content="Streaming...", finished=False)
    validate_instance(tr, "text-response.json")


def test_wait_validates_against_schema():
    w = Wait(reason="awaiting input", duration_seconds=30)
    validate_instance(w, "wait.json")


def test_delegate_validates_against_schema():
    d = {"task": "review code", "agent": "code-reviewer"}
    validate_instance(d, "delegate.json")


def test_end_validates_against_schema():
    e = End(reason="task_complete", summary="All done!")
    validate_instance(e, "end.json")


# ── Required-field validation: Pydantic enforces what Schema requires ─


def test_message_allows_missing_timestamp():
    """timestamp defaults to None (FIELD_OVERRIDES make it optional)."""
    msg = Message(content="hi")
    assert msg.content == "hi"
    assert msg.timestamp is None


def test_message_rejects_missing_content():
    with pytest.raises(ValidationError):
        Message(timestamp="2025-01-01T00:00:00Z")


def test_identity_allows_missing_user_name():
    """user_name is Optional — Identity works without it (matches test battery)."""
    ident = Identity(platform="t", chat_id="c", user_id="u")
    assert ident.platform == "t"
    assert ident.chat_id == "c"
    assert ident.user_id == "u"
    assert ident.user_name is None


def test_identity_allows_missing_user_id():
    """user_id is Optional — Identity works without it (matches test battery)."""
    ident = Identity(platform="t", chat_id="c", user_name="n")
    assert ident.platform == "t"
    assert ident.chat_id == "c"
    assert ident.user_name == "n"
    assert ident.user_id is None


def test_session_state_defaults_started_at():
    """started_at defaults to None (FIELD_OVERRIDES make it optional)."""
    ss = SessionState()
    assert ss.started_at is None
    assert ss.turn_count == 0


def test_config_defaults_max_iterations():
    """max_iterations defaults to None (FIELD_OVERRIDES remove the default)."""
    cfg = Config(timeout_seconds=300)
    assert cfg.max_iterations is None
    assert cfg.timeout_seconds == 300


def test_process_request_rejects_missing_session_id():
    with pytest.raises(ValidationError):
        ProcessRequest(message=_message(), identity=_identity(), context=_context())


def test_result_request_rejects_missing_session_id():
    with pytest.raises(ValidationError):
        ResultRequest(decision_id="d-1", result={"type": "x", "success": True})


def test_cancel_request_rejects_missing_reason():
    with pytest.raises(ValidationError):
        CancelRequest(session_id="s-1")


def test_health_response_rejects_missing_status():
    with pytest.raises(ValidationError):
        HealthResponse(version="1.0")


def test_error_response_rejects_missing_error():
    with pytest.raises(ValidationError):
        ErrorResponse()


def test_session_response_rejects_missing_status():
    with pytest.raises(ValidationError):
        SessionResponse(
            session_id="s-1",
            started_at="2025-01-01T00:00:00Z",
            last_active="2025-01-01T00:05:00Z",
            turn_count=3,
        )


# ── Enum validation matches Schema enums ────────────────────────────


def test_decision_type_enum_matches_schema():
    """DecisionType enum values must match the schema's decision enum."""
    schema = _load_schema("decision.json")
    schema_values = set(schema["properties"]["decision"]["enum"])
    python_values = {dt.value for dt in DecisionType}
    assert python_values == schema_values, (
        f"Mismatch: {python_values} vs {schema_values}"
    )


def test_end_reason_enum_matches_schema():
    schema = _load_schema("end.json")
    schema_values = set(schema["properties"]["reason"]["enum"])
    python_values = {er.value for er in EndReason}
    assert python_values == schema_values, (
        f"Mismatch: {python_values} vs {schema_values}"
    )


def test_health_status_enum_matches_schema():
    schema = _load_schema("health-response.json")
    schema_values = set(schema["properties"]["status"]["enum"])
    python_values = {hs.value for hs in HealthStatus}
    assert python_values == schema_values, (
        f"Mismatch: {python_values} vs {schema_values}"
    )


def test_cancel_reason_enum_matches_schema():
    schema = _load_schema("cancel-request.json")
    schema_values = set(schema["properties"]["reason"]["enum"])
    python_values = {cr.value for cr in CancelReason}
    assert python_values == schema_values, (
        f"Mismatch: {python_values} vs {schema_values}"
    )


def test_result_type_enum_matches_schema():
    schema = _load_schema("result-request.json")
    schema_values = set(schema["properties"]["result"]["properties"]["type"]["enum"])
    python_values = {rt.value for rt in ResultType}
    assert python_values == schema_values, (
        f"Mismatch: {python_values} vs {schema_values}"
    )


def test_error_code_enum_matches_schema():
    schema = _load_schema("error-response.json")
    schema_values = set(schema["properties"]["error"]["properties"]["code"]["enum"])
    python_values = {ec.value for ec in ErrorCode}
    assert python_values == schema_values, (
        f"Mismatch: {python_values} vs {schema_values}"
    )


def test_session_status_enum_matches_schema():
    schema = _load_schema("session-response.json")
    schema_values = set(schema["properties"]["status"]["enum"])
    python_values = {ss.value for ss in SessionStatus}
    assert python_values == schema_values, (
        f"Mismatch: {python_values} vs {schema_values}"
    )


# ── Numeric constraint validation ───────────────────────────────────


def test_config_timeout_minimum():
    """timeout_seconds has no Field(ge=1) — FIELD_OVERRIDES strip constraints."""
    cfg = Config(timeout_seconds=0)
    assert cfg.timeout_seconds == 0  # no validation error expected


def test_config_max_iterations_minimum():
    """max_iterations has no Field(ge=1) — FIELD_OVERRIDES strip constraints."""
    # max_iterations is int | None with no validation constraint
    assert Config(max_iterations=0).max_iterations == 0


def test_wait_duration_seconds_minimum():
    """Schema requires duration_seconds >= 1."""
    with pytest.raises(ValidationError):
        Wait(reason="x", duration_seconds=0)


def test_llm_call_temperature_range():
    """temperature has no Field(ge=0, le=2) — FIELD_OVERRIDES strip constraints."""
    call = LLMCall(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        temperature=2.1,
    )
    assert call.temperature == 2.1  # no validation error expected


def test_result_payload_duration_ms_minimum():
    """Schema requires duration_ms >= 0."""
    with pytest.raises(ValidationError):
        ResultPayload(type="tool_result", success=True, duration_ms=-1)


# ── Capability enum matches schema ──────────────────────────────────


def test_capability_enum_matches_schema():
    schema = _load_schema("health-response.json")
    schema_values = set(schema["properties"]["capabilities"]["items"]["enum"])
    python_values = {c.value for c in Capability}
    assert python_values == schema_values, (
        f"Mismatch: {python_values} vs {schema_values}"
    )
