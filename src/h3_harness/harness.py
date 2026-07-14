"""H3 Harness — BaseHarness ABC + FastAPI router for one-line integration.

Usage:
    from h3_harness import BaseHarness, Decision, DecisionType, create_router
    from fastapi import FastAPI

    class MyHarness(BaseHarness):
        async def on_process(self, req):
            return Decision(decision=DecisionType.TEXT, text=TextResponse(...))

        async def on_result(self, req):
            return Decision(decision=DecisionType.END, end=End(reason="task_complete"))

    app = FastAPI()
    app.include_router(create_router(MyHarness()))
    # Optional: add request logging with add_middleware(app)

"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .protocol import (
    CancelRequest,
    Capability,
    Decision,
    DecisionType,
    End,
    EndReason,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    ProcessRequest,
    ResultRequest,
    SessionResponse,
    SessionStatus,
)

logger = logging.getLogger(__name__)


class BaseHarness(ABC):
    """Abstract base class for H3-compliant agent harnesses.

    Subclasses MUST implement ``on_process`` and ``on_result``.
    Optional overrides: ``on_cancel``, ``on_session_terminate``, ``health``.
    """

    _started_at: float = 0.0

    def __init__(self) -> None:
        self._started_at = time.time()

    @abstractmethod
    async def on_process(self, req: ProcessRequest) -> Decision:
        """Called when a new user message arrives.

        Return the first Decision in the agent loop.
        """
        ...

    @abstractmethod
    async def on_result(self, req: ResultRequest) -> Decision:
        """Called after Hermes executes a Decision.

        Return the next Decision. Return Decision(decision=DecisionType.END, ...)
        to finish the session.
        """
        ...

    async def on_cancel(self, req: CancelRequest) -> bool:
        """Called when the user interrupts. Return True to confirm cancellation."""
        return True

    async def on_session_terminate(self, session_id: str) -> None:
        """Called on DELETE /v1/sessions/{session_id}."""
        pass

    def health(self) -> HealthResponse:
        """Return harness health status. Override for custom health logic."""
        return HealthResponse(
            status=HealthStatus.OK,
            version="1.0.0",
            transport="rest",
            protocol_version="1.0",
            uptime_seconds=int(time.time() - self._started_at),
            capabilities=list(Capability),
        )


def _error_response(status_code: int, code: ErrorCode, message: str) -> JSONResponse:
    """Build a standard H3 error JSON response."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump(
            mode="json"
        ),
    )


def create_router(harness: BaseHarness, *, prefix: str = "") -> APIRouter:
    """Create a FastAPI router wired to the given harness.

    Registers all H3 endpoints:
        GET  /v1/health
        POST /v1/process
        POST /v1/result
        POST /v1/cancel
        GET  /v1/sessions/{session_id}
        DELETE /v1/sessions/{session_id}

    Usage:
        app = FastAPI()
        app.include_router(create_router(MyHarness()))
        # or with a prefix:
        app.include_router(create_router(MyHarness(), prefix="/api"))
    """
    router = APIRouter(prefix=prefix)

    # ── GET /v1/health ───────────────────────────────────────────
    @router.get("/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return harness.health()

    # ── POST /v1/process ─────────────────────────────────────────
    @router.post("/v1/process", response_model=Decision)
    async def process(req: ProcessRequest) -> Decision:
        try:
            return await harness.on_process(req)
        except Exception as exc:
            logger.exception("on_process failed")
            return Decision(
                decision=DecisionType.END,
                end=End(reason=EndReason.ERROR, summary=str(exc)),
            )

    # ── POST /v1/result ──────────────────────────────────────────
    @router.post("/v1/result", response_model=Decision)
    async def result(req: ResultRequest) -> Decision:
        try:
            return await harness.on_result(req)
        except Exception as exc:
            logger.exception("on_result failed")
            return Decision(
                decision=DecisionType.END,
                end=End(reason=EndReason.ERROR, summary=str(exc)),
            )

    # ── POST /v1/cancel ──────────────────────────────────────────
    @router.post("/v1/cancel")
    async def cancel(req: CancelRequest):
        try:
            confirmed = await harness.on_cancel(req)
            return {"session_id": req.session_id, "cancelled": confirmed}
        except Exception as exc:
            logger.exception("on_cancel failed")
            raise HTTPException(status_code=500, detail=str(exc))

    # ── GET /v1/sessions/{session_id} ────────────────────────────
    @router.get("/v1/sessions/{session_id}", response_model=SessionResponse)
    async def get_session(session_id: str, request: Request):
        # Note: Base harness doesn't track sessions by default.
        # Subclasses may override via session store.
        return SessionResponse(
            session_id=session_id,
            started_at="",
            last_active="",
            turn_count=0,
            status=SessionStatus.ACTIVE,
        )

    # ── DELETE /v1/sessions/{session_id} ─────────────────────────
    @router.delete("/v1/sessions/{session_id}")
    async def terminate_session(session_id: str):
        try:
            await harness.on_session_terminate(session_id)
            return {"session_id": session_id, "terminated": True}
        except Exception as exc:
            logger.exception("on_session_terminate failed")
            raise HTTPException(status_code=500, detail=str(exc))

    return router
