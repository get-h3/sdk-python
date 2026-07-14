# H3 Harness SDK for Python

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

## Development

```bash
make install   # create venv + install deps
make build     # verify imports
make test      # run tests
make lint      # ruff check
make fmt       # ruff format
```

## Reference

- Spec: [get-h3/h3 — specs/04-SDK-Libraries.md](https://github.com/get-h3/h3/blob/main/specs/04-SDK-Libraries.md)
- Protocol: [get-h3/protocol](https://github.com/get-h3/protocol)
