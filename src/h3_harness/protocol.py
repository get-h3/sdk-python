"""H3 Protocol Types — Pydantic models matching the v1 JSON Schema.

Generated from get-h3/protocol/schemas/v1/*.json.
All field names use snake_case per Python convention; Pydantic
handles JSON (camelCase) ↔ Python (snake_case) automatically.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

# ── Enums ───────────────────────────────────────────────────────────


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


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_DECISION = "INVALID_DECISION"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    UNKNOWN_MODEL = "UNKNOWN_MODEL"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    HARNESS_TIMEOUT = "HARNESS_TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class AttachmentType(str, Enum):
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Capability(str, Enum):
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    TEXT = "text"
    WAIT = "wait"
    DELEGATE = "delegate"
    END = "end"


# ── Common / Shared Types ───────────────────────────────────────────


class Attachment(BaseModel):
    type: AttachmentType
    url: str
    mime_type: str


class Message(BaseModel):
    role: str = "user"
    content: str
    attachments: list[Attachment] | None = None
    timestamp: str = ""  # test battery omits this; Go zero-value handles it


class Identity(BaseModel):
    platform: str = ""
    chat_id: str = ""
    thread_id: str | None = None
    user_name: str = ""
    user_id: str = ""


class HistoryEntry(BaseModel):
    role: str  # user | assistant | system
    content: str


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class Model(BaseModel):
    name: str
    provider: str
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None
    context_window: int
    supports_vision: bool | None = None
    supports_tool_calling: bool | None = None


class SessionState(BaseModel):
    turn_count: int = 0
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    cost_so_far: float = 0.0
    started_at: str = ""  # test battery sends empty session_state


class Config(BaseModel):
    max_iterations: int = 100  # test battery sends empty config
    timeout_seconds: int = 300  # test battery sends empty config
    project_dir: str | None = None
    max_tool_calls_per_turn: int | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class Context(BaseModel):
    history: list[HistoryEntry] = Field(default_factory=list)
    tools: list[Tool] = Field(default_factory=list)
    models: list[Model] = Field(default_factory=list)
    memory: str | None = None
    skills: list[str] | None = None
    config: Config
    session_state: SessionState


# ── Decision Sub-Types ──────────────────────────────────────────────


class ToolCall(BaseModel):
    name: str
    params: dict[str, Any]
    reasoning: str | None = None


class LLMMessage(BaseModel):
    role: str  # user | assistant | system
    content: str


class LLMCall(BaseModel):
    model: str
    messages: list[LLMMessage]
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)


class TextResponse(BaseModel):
    content: str
    finished: bool


class Wait(BaseModel):
    reason: str
    duration_seconds: int | None = Field(default=None, ge=1)
    poll_endpoint: str | None = None


class Delegate(BaseModel):
    agent: str | None = None  # GAP-3: sub-agent name/role (from schema)
    task: str
    context: str | None = None
    model: str | None = None
    provider: str | None = None


class End(BaseModel):
    reason: str  # GAP-1: includes rate_limited + cancelled (6 values per schema)
    summary: str | None = None


# ── Request Models ──────────────────────────────────────────────────


class ProcessRequest(BaseModel):
    session_id: str
    message: Message
    identity: Identity
    context: Context


class ResultRequest(BaseModel):
    session_id: str
    decision_id: str
    result: ResultPayload


class ResultPayload(BaseModel):
    type: ResultType
    tool_name: str | None = None
    data: dict[str, Any] | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    success: bool


class CancelRequest(BaseModel):
    session_id: str
    reason: CancelReason


# ── Response Models ─────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: HealthStatus
    version: str
    transport: str | None = "rest"
    protocol_version: str | None = None
    uptime_seconds: int | None = Field(default=None, ge=0)  # GAP-2
    active_sessions: int | None = Field(default=None, ge=0)  # GAP-2
    capabilities: list[Capability] | None = None
    degraded_reason: str | None = None  # GAP-2
    error: str | None = None  # GAP-2


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class SessionResponse(BaseModel):  # GAP-4: defined per schema, missing from spec
    session_id: str
    started_at: str
    last_active: str
    turn_count: int = 0
    status: SessionStatus
    current_decision: str | None = None
    current_decision_type: DecisionType | None = None


# ── Decision (discriminated union) ──────────────────────────────────


class Decision(BaseModel):
    """Top-level decision object sent from harness to Hermes.

    The ``decision`` field determines which sub-type is valid.
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


# ── Public API ──────────────────────────────────────────────────────

__all__ = [
    # Enums
    "DecisionType",
    "EndReason",
    "CancelReason",
    "ResultType",
    "SessionStatus",
    "ErrorCode",
    "HealthStatus",
    "AttachmentType",
    "MessageRole",
    "Capability",
    # Common
    "Attachment",
    "Message",
    "Identity",
    "HistoryEntry",
    "Tool",
    "Model",
    "SessionState",
    "Config",
    "Context",
    # Decision sub-types
    "ToolCall",
    "LLMMessage",
    "LLMCall",
    "TextResponse",
    "Wait",
    "Delegate",
    "End",
    # Requests
    "ProcessRequest",
    "ResultRequest",
    "ResultPayload",
    "CancelRequest",
    # Responses
    "HealthResponse",
    "ErrorDetail",
    "ErrorResponse",
    "SessionResponse",
    # Decision
    "Decision",
]
