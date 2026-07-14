"""Echo Harness — a complete H3 harness that echoes back user messages.

Demonstrates:
  - BaseHarness with on_process + on_result
  - TextResponse, Decision, End
  - create_router + add_middleware
  - uvicorn runner

Run:
    python src/h3_harness/examples/echo.py
    # → Server at http://0.0.0.0:8000
    #   GET  /v1/health  → harness health
    #   POST /v1/process → send a message, get it echoed back
"""

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


class EchoHarness(BaseHarness):
    """Echoes back whatever the user sends."""

    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content=f"Echo: {req.message.content}", finished=True),
        )

    async def on_result(self, req):
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))


# ── Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    app = FastAPI()
    app.include_router(create_router(EchoHarness()))
    add_middleware(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)
