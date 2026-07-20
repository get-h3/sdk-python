"""Echo Harness — a complete H3 harness that echoes back user messages.

Demonstrates:
  - BaseHarness with on_process + on_result
  - TextResponse, Decision, End
  - create_router + add_middleware
  - Session tracking via get_session_info (H3 compliance)
  - Streaming detection via content heuristics
  - uvicorn runner

Run:
    python src/h3_harness/examples/echo.py
    # → Server at http://0.0.0.0:8000
    #   GET  /v1/health  → harness health
    #   POST /v1/process → send a message, get it echoed back
"""

import time

from fastapi import FastAPI

from h3_harness import (
    BaseHarness,
    Decision,
    DecisionType,
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
            "started_at": time.time(),
            "turn_count": self._sessions.get(sid, {}).get("turn_count", 0) + 1,
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

        result_content = f"Result received: {req.decision_id}"
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content=result_content, finished=finished),
        )

    def get_session_info(self, session_id: str) -> dict | None:
        """Return session info dict or None if not found. Used by create_router."""
        return self._sessions.get(session_id)


# ── Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    app = FastAPI()
    app.include_router(create_router(EchoHarness()))
    add_middleware(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)
