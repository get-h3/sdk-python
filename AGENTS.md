# AGENTS.md — H3 SDK for Python

Python SDK for building H3-compliant agent harnesses.

## Install

```bash
pip install h3-harness-sdk
```

### Install fallback (source / git)

If a release isn't published to PyPI yet (or you want the latest unreleased
changes), install directly from the repository:

```bash
# From git
pip install git+https://github.com/get-h3/sdk-python.git

# Editable source install (development)
git clone https://github.com/get-h3/sdk-python.git
cd sdk-python
pip install -e .
```

## Quickstart

```python
from datetime import datetime, timezone

from h3_harness import (
    BaseHarness,
    Decision,
    DecisionType,
    End,
    TextResponse,
    create_router,
)
from fastapi import FastAPI


class MyHarness(BaseHarness):
    def __init__(self):
        # Track sessions so cancel/session lookups 404 on unknown ids
        # (battery: test_5_9b cancel_unknown_session, test_5_10 session_not_found).
        self._sessions: dict[str, dict] = {}

    async def on_process(self, req):
        # Echo conversation history from context (battery: history preserved).
        history = list(req.context.history)
        # Streaming: "do not finish" in message -> unfinished text.
        streaming = "do not finish" in req.message.content
        finished = not streaming
        self._sessions[req.session_id] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "turn_count": (
                self._sessions.get(req.session_id, {}).get("turn_count", 0) + 1
            ),
        }
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(
                content=f"Echo: {req.message.content}",
                finished=finished,
            ),
            history=history,
        )

    async def on_result(self, req):
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))

    def get_session_info(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)


app = FastAPI()
app.include_router(create_router(MyHarness()))
# Run with: uvicorn my_harness:app --port 9191
```

## Package Structure

- `protocol.py` — Pydantic models (generated from get-h3/protocol JSON Schema)
- `harness.py` — BaseHarness ABC + FastAPI router
- `middleware.py` — Request logging middleware via BaseHTTPMiddleware
- `testbed.py` — MockHermes for pytest

## Development

- GitReins quality gate mandatory
- Must pass `h3-test` from get-h3/shim before release
- To score 44/44 on the battery: echo `context.history` in every Decision,
  never issue `llm_call` when `context.models` is empty, and return
  `text.finished=false` for "do not finish" prompts. See README → *Passing the
  battery (h3-test compliance)*. `src/h3_harness/examples/echo.py` is the
  battery-ready template.

## Reference

Spec: `get-h3/h3` → `specs/04-SDK-Libraries.md`
