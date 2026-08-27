"""Minimal H3 Harness — the smallest runnable, battery-compliant example.

A bare-bones BaseHarness subclass with no real logic. Use this as a starting
template when building your own harness — it stays battery-compliant (44/44)
by tracking sessions (unknown ids 404), echoing context.history, and applying
the "do not finish" streaming heuristic.

Run:
    python src/h3_harness/examples/minimal.py
    # → Server at http://0.0.0.0:8000
    #   GET  /v1/health  → harness health
    #   POST /v1/process → replies with a fixed string
"""

from datetime import datetime, timezone

from fastapi import FastAPI

from h3_harness import (
    BaseHarness,
    Decision,
    DecisionType,
    End,
    TextResponse,
    add_middleware,
    create_router,
)


class MinimalHarness(BaseHarness):
    """A no-op harness that always replies with a fixed greeting."""

    def __init__(self):
        super().__init__()
        self._sessions: dict[str, dict] = {}

    async def on_process(self, req):
        # Streaming: "do not finish" in message → unfinished text
        finished = "do not finish" not in req.message.content

        self._sessions[req.session_id] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "turn_count": (
                self._sessions.get(req.session_id, {}).get("turn_count", 0) + 1
            ),
        }

        # Echo conversation history from context
        history = list(req.context.history)

        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="Hello from minimal!", finished=finished),
            history=history,
        )

    async def on_result(self, req):
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))

    def get_session_info(self, session_id: str) -> dict | None:
        """Return session info dict or None if not found. Used by create_router."""
        return self._sessions.get(session_id)


# ── App ────────────────────────────────────────────────────────────
# Module-level `app` so the example can be served directly with
# `uvicorn h3_harness.examples.minimal:app` (README Examples section).
app = FastAPI()
app.include_router(create_router(MinimalHarness()))
add_middleware(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
