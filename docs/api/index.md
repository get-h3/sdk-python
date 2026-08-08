# H3 Harness SDK — API Reference

Hand-written API reference for `h3-harness-sdk` **0.1.2** (package `h3_harness`).

This reference documents the public surface of the SDK exactly as implemented in
`src/h3_harness/` at the time of writing. If anything here disagrees with a
docstring in the source, this reference reflects the code's actual behavior.

The SDK builds **H3-compliant agent harnesses**: a FastAPI service that speaks
the H3 protocol to Hermes Core. Hermes sends the harness user messages and
tool/model results; the harness replies with `Decision` objects that tell
Hermes what to do next (call a tool, call an LLM, send text, wait, delegate, or
end the session).

## Package layout

| Module | Contents |
|---|---|
| `h3_harness` | Top-level re-exports (`__all__`): `BaseHarness`, `create_router`, `add_middleware`, and 21 protocol models/enums. `__version__` = `"0.1.2"`. |
| `h3_harness.protocol` | All 33 Pydantic models and enums of the H3 v1 protocol (generated from `get-h3/protocol` JSON Schema). 12 of them are **not** re-exported at the top level — import them from `h3_harness.protocol`. |
| `h3_harness.harness` | `BaseHarness` (abstract base class) and `create_router` (FastAPI router factory). |
| `h3_harness.middleware` | `add_middleware` — request logging for FastAPI apps. |
| `h3_harness.testbed` | `MockHermes` — simulate Hermes Core in pytest without a running server. |
| `h3_harness.examples` | Three runnable examples: `echo.py`, `minimal.py`, `langchain_agent.py`. |

## How the pieces fit

```
Hermes Core (or MockHermes)
        │  POST /v1/process   (ProcessRequest: message + identity + context)
        ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI app                                             │
│   app.include_router(create_router(MyHarness()))         │
│   add_middleware(app)        # optional request logging  │
│                                                          │
│   create_router wires:                                   │
│     /v1/health      → harness.health()                   │
│     /v1/process     → harness.on_process(req)            │
│     /v1/result      → harness.on_result(req)             │
│     /v1/cancel      → harness.on_cancel(req)             │
│     GET  /v1/sessions/{id} → harness.get_session_info()  │
│     DELETE /v1/sessions/{id} → harness.on_session_terminate() │
└─────────────────────────────────────────────────────────┘
        │  Decision (decision + one payload: text/tool_call/llm_call/wait/delegate/end)
        ▼
Hermes executes the decision, then POSTs /v1/result → harness returns the
next Decision. The loop repeats until a Decision with decision=END.
```

The minimal integration (full details in [harness.md](harness.md)):

```python
from fastapi import FastAPI
from h3_harness import (
    BaseHarness,
    Decision,
    DecisionType,
    End,
    TextResponse,
    create_router,
)


class MyHarness(BaseHarness):
    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content=f"Echo: {req.message.content}", finished=True),
        )

    async def on_result(self, req):
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))


app = FastAPI()
app.include_router(create_router(MyHarness()))
```

## Reference pages

| Page | Covers |
|---|---|
| [protocol.md](protocol.md) | Every enum and Pydantic model in `h3_harness.protocol` — fields, types, defaults. |
| [harness.md](harness.md) | `BaseHarness` ABC (abstract + concrete methods) and `create_router` (options, endpoint table, error semantics). |
| [middleware.md](middleware.md) | `add_middleware` — what it logs, how to wire it. |
| [testbed.md](testbed.md) | `MockHermes` — constructor, methods, pytest round-trip example. |
| [examples.md](examples.md) | The three shipped examples and what each demonstrates. |

See the [README](../../README.md) for install instructions and the quickstart,
and the [passing-the-battery section](../../README.md#passing-the-battery-h3-test-compliance)
for what the h3-test compliance suite (43 tests) checks.
