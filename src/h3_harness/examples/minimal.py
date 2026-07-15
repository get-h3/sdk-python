"""Minimal H3 Harness — the smallest runnable example.

Bare-bones BaseHarness subclass with no real logic. Use this as a starting
template when building your own harness.

Run:
    python src/h3_harness/examples/minimal.py
    # → Server at http://0.0.0.0:8000
    #   GET  /v1/health  → harness health
    #   POST /v1/process → replies with a fixed string
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


class MinimalHarness(BaseHarness):
    """A no-op harness that always replies with a fixed greeting."""

    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="Hello from minimal!", finished=True),
        )

    async def on_result(self, req):
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))


if __name__ == "__main__":
    import uvicorn

    app = FastAPI()
    app.include_router(create_router(MinimalHarness()))
    add_middleware(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)
