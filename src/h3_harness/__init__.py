"""H3 Harness SDK for Python — build agent harnesses compatible with Hermes Core."""

__version__ = "0.1.0"

from .harness import BaseHarness, create_router
from .middleware import add_middleware
from .protocol import (
    CancelReason,
    CancelRequest,
    Decision,
    DecisionType,
    Delegate,
    End,
    EndReason,
    ErrorCode,
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    LLMCall,
    ProcessRequest,
    ResultPayload,
    ResultRequest,
    ResultType,
    SessionResponse,
    SessionStatus,
    TextResponse,
    ToolCall,
    Wait,
)

__all__ = [
    "BaseHarness",
    "create_router",
    "add_middleware",
    "CancelReason",
    "CancelRequest",
    "Decision",
    "DecisionType",
    "Delegate",
    "End",
    "EndReason",
    "ErrorCode",
    "ErrorResponse",
    "HealthResponse",
    "HealthStatus",
    "LLMCall",
    "ProcessRequest",
    "ResultPayload",
    "ResultRequest",
    "ResultType",
    "SessionResponse",
    "SessionStatus",
    "TextResponse",
    "ToolCall",
    "Wait",
]
