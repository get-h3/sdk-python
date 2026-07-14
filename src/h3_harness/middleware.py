"""H3 Middleware — Logging, timing, and error handling for FastAPI apps.

Usage:
    from h3_harness.middleware import add_middleware
    from fastapi import FastAPI

    app = FastAPI()
    add_middleware(app)

Called automatically by ``create_router()`` if an app reference is provided.
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .protocol import ErrorCode, ErrorDetail, ErrorResponse

logger = logging.getLogger("h3_harness")


class _RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "%s %s → %d (%dms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            return response
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "%s %s → 500 (%dms) — %s",
                request.method,
                request.url.path,
                elapsed_ms,
                exc,
            )
            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))
                ).model_dump(mode="json"),
            )


def add_middleware(app: FastAPI) -> None:
    """Attach request-logging middleware to a FastAPI application.

    IMPORTANT: Call BEFORE adding routes — middleware order matters.
    """
    app.add_middleware(_RequestLoggingMiddleware)
