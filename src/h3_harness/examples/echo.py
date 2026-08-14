"""Echo Harness — a complete H3 harness that echoes back user messages.

Demonstrates:
  - BaseHarness with on_process + on_result
  - TextResponse, Decision, End
  - create_router + add_middleware
  - Session tracking via get_session_info (H3 compliance)
  - Session status reporting: "active" → "completed" once on_result ends it
  - Streaming detection via content heuristics
  - uvicorn runner

Run:
    python src/h3_harness/examples/echo.py
    # → Server at http://0.0.0.0:9191
    #   GET  /v1/health  → harness health
    #   POST /v1/process → send a message, get it echoed back
    #
    # The port defaults to the battery port 9191; pass a number to override
    # (e.g. python echo.py 8000).
"""

import sys
from datetime import datetime, timezone

from fastapi import FastAPI

from h3_harness import (
    BaseHarness,
    Decision,
    DecisionType,
    End,
    EndReason,
    TextResponse,
    add_middleware,
    create_router,
)


class EchoHarness(BaseHarness):
    """Echoes back whatever the user sends. Tracks sessions for H3 compliance."""

    def __init__(self):
        super().__init__()
        self._sessions: dict[str, dict] = {}
        self._streaming: dict[str, bool] = {}

    async def on_process(self, req):
        content = f"Echo: {req.message.content}"
        sid = req.session_id

        # Streaming: "do not finish" in message → unfinished text
        streaming = "do not finish" in req.message.content
        self._streaming[sid] = streaming
        finished = not streaming

        self._sessions[sid] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "turn_count": self._sessions.get(sid, {}).get("turn_count", 0) + 1,
            # GAP-035: sessions start active; on_result flips them to
            # "completed" when it returns an END decision.
            "status": "active",
        }

        # Echo conversation history from context
        history = list(req.context.history)

        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content=content, finished=finished),
            history=history,
        )

    async def on_result(self, req):
        sid = req.session_id
        streaming = self._streaming.get(sid, False)
        finished = not streaming

        if sid in self._sessions:
            entry = self._sessions[sid]
            entry["turn_count"] = entry.get("turn_count", 0) + 1

        if finished:
            # The exchange is complete — end the session and record it as
            # completed (GAP-035: GET /v1/sessions/{id} then reports
            # status="completed"). Streaming sessions ("do not finish")
            # keep returning unfinished text and stay active.
            if sid in self._sessions:
                self._sessions[sid]["status"] = "completed"
            return Decision(
                decision=DecisionType.END,
                end=End(reason=EndReason.TASK_COMPLETE),
            )

        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(
                content=f"Result received: {req.decision_id}",
                finished=finished,
            ),
        )

    def get_session_info(self, session_id: str) -> dict | None:
        """Return session info dict or None if not found. Used by create_router."""
        return self._sessions.get(session_id)


def _server_port(argv=None) -> int:
    """Return the HTTP port for the echo server.

    Defaults to the battery port 9191 (h3-test --endpoint
    http://localhost:9191); an explicit argument overrides it, e.g.
    ``python echo.py 8000``. When ``argv`` is None, ``sys.argv[1:]`` is used.
    """
    args = sys.argv[1:] if argv is None else argv
    return int(args[0]) if args else 9191


# ── Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    app = FastAPI()
    app.include_router(create_router(EchoHarness()))
    add_middleware(app)
    uvicorn.run(app, host="0.0.0.0", port=_server_port())
