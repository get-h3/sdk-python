# AGENTS.md — H3 SDK for Python

Python SDK for building H3-compliant agent harnesses.

## Install

```bash
pip install h3-harness-sdk
```

## Quickstart

```python
from h3_harness import BaseHarness, Decision, DecisionType, create_router
from fastapi import FastAPI

class MyHarness(BaseHarness):
    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="Hello from Python!", finished=True)
        )

    async def on_result(self, req):
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))

app = FastAPI()
app.include_router(create_router(MyHarness()))
```

## Package Structure

- `protocol.py` — Pydantic models (generated from get-h3/protocol JSON Schema)
- `harness.py` — BaseHarness ABC + FastAPI router
- `testbed.py` — MockHermes for pytest

## Development

- GitReins quality gate mandatory
- Must pass `h3-test` from get-h3/shim before release

## Reference

Spec: `get-h3/h3` → `specs/04-SDK-Libraries.md`
