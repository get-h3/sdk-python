"""H3 Protocol Types — Pydantic models matching the v1 JSON Schema.

Generated from get-h3/protocol/schemas/v1/*.json.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

# ── Enums ──


class DecisionType(str, Enum):
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    TEXT = "text"
    WAIT = "wait"
    DELEGATE = "delegate"
    END = "end"


class EndReason(str, Enum):
    TASK_COMPLETE = "task_complete"
    USER_REQUESTED = "user_requested"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    CANCELLED = "cancelled"


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class Capability(str, Enum):
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    TEXT = "text"
    WAIT = "wait"
    DELEGATE = "delegate"
    END = "end"


class CancelReason(str, Enum):
    USER_INTERRUPT = "user_interrupt"
    TIMEOUT = "timeout"
    SYSTEM = "system"


class ResultType(str, Enum):
    TOOL_RESULT = "tool_result"
    LLM_RESPONSE = "llm_response"
    TEXT_SENT = "text_sent"
    DELEGATE_RESULT = "delegate_result"
    WAIT_TIMEOUT = "wait_timeout"
    ERROR = "error"


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_DECISION = "INVALID_DECISION"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    UNKNOWN_MODEL = "UNKNOWN_MODEL"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    HARNESS_TIMEOUT = "HARNESS_TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ── Common Types ──


class Attachment(BaseModel):
    mime_type: str
    type: str
    url: str


class Message(BaseModel):
    content: str
    role: str = "user"
    timestamp: str | None = None
    attachments: list[Attachment] | None = None


class Identity(BaseModel):
    chat_id: str
    platform: str
    user_id: str | None = None
    user_name: str | None = None
    thread_id: str | None = None


class HistoryEntry(BaseModel):
    content: str
    role: str


class Tool(BaseModel):
    description: str
    name: str
    parameters: dict[str, Any]


class Model(BaseModel):
    context_window: int
    name: str
    provider: str
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None
    supports_tool_calling: bool | None = None
    supports_vision: bool | None = None


class SessionState(BaseModel):
    cost_so_far: float = 0.0
    started_at: str | None = None
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    turn_count: int = 0


class Config(BaseModel):
    max_iterations: int | None = None
    timeout_seconds: int = 300
    max_tool_calls_per_turn: int | None = None
    project_dir: str | None = None
    temperature: float | None = None


class Context(BaseModel):
    config: Config
    history: list[HistoryEntry] = []
    models: list[Model] = []
    session_state: SessionState
    tools: list[Tool] = []
    memory: str | None = None
    skills: list[str] | None = None


# ── Decision Payloads ──


class ToolCall(BaseModel):
    """Decision to execute a Hermes tool."""

    name: str
    params: dict[str, Any]
    reasoning: str | None = None


class LLMCall(BaseModel):
    """Decision to run an LLM prompt."""

    messages: list[dict[str, Any]]
    model: str
    max_tokens: int | None = None
    system_prompt: str | None = None
    temperature: float | None = None


class TextResponse(BaseModel):
    """Decision to send text to the user."""

    content: str
    finished: bool


class Wait(BaseModel):
    """Decision to pause for an external signal."""

    reason: str
    duration_seconds: int | None = Field(default=None, ge=1)
    poll_endpoint: str | None = None


class Delegate(BaseModel):
    """Decision to spawn a sub-agent."""

    task: str
    agent: str | None = None
    context: str | None = None
    model: str | None = None
    provider: str | None = None


class End(BaseModel):
    """Decision to terminate the session."""

    reason: str
    summary: str | None = None


class LLMMessage(BaseModel):
    """Single message in an LLM conversation."""

    role: str
    content: str


class ErrorDetail(BaseModel):
    """Detailed error information."""

    field: str | None = None
    message: str
    code: str | None = None


class ResultPayload(BaseModel):
    """Payload for a result returned to the harness."""

    type: str
    success: bool
    tool_name: str | None = None
    data: dict[str, Any] | None = None
    duration_ms: int | None = Field(default=None, ge=0)


# ── Request/Response Models ──


class ProcessRequest(BaseModel):
    """Request body for POST /v1/process — new message triggers process.
    The harness evaluates the message and context, then returns a Decision.
    """

    context: Context
    identity: Identity
    message: Message
    session_id: str


class ResultRequest(BaseModel):
    """Request body for POST /v1/result — execution result of a prior decision."""

    decision_id: str
    result: dict[str, Any]
    session_id: str


class CancelRequest(BaseModel):
    """Request body for POST /v1/cancel — cancel an in-flight operation."""

    reason: str
    session_id: str


class HealthResponse(BaseModel):
    """Response from GET /v1/health — harness health status."""

    status: str
    version: str
    active_sessions: int | None = None
    capabilities: list[str] | None = None
    degraded_reason: str | None = None
    error: str | None = None
    protocol_version: str | None = None
    transport: str | None = None
    uptime_seconds: int | None = None


class ErrorResponse(BaseModel):
    """Standard error response for all H3 endpoints."""

    error: dict[str, Any]


class SessionResponse(BaseModel):
    """Response from GET /v1/sessions/{session_id} — session metadata."""

    last_active: str
    session_id: str
    started_at: str
    status: str
    turn_count: int
    current_decision: str | None = None
    current_decision_type: str | None = None


class Decision(BaseModel):
    """Top-level decision object sent from harness to Hermes.

    The decision field determines which sub-type is valid.
    Pydantic validates that the matching sub-field is present.
    """

    decision: DecisionType
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    history: list[HistoryEntry] = Field(default_factory=list)
    tool_call: ToolCall | None = None
    llm_call: LLMCall | None = None
    text: TextResponse | None = None
    wait: Wait | None = None
    delegate: Delegate | None = None
    end: End | None = None
