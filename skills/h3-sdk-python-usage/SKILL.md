---
name: h3-sdk-python-usage
description: >-
  How to USE the H3 Python SDK (get-h3/sdk-python) — build H3-compliant agent
  harnesses that Hermes Core can use as a brain. Install path, quickstart,
  the 3 battery conventions, pitfalls. Load this before touching this repo or
  building a harness with h3-harness-sdk.
version: 1.0.0
category: software-development
---

# H3 Python SDK — Usage Skill

The H3 ("Hermes Harness Hooks") protocol lets an external agent system become
the *thinking brain* of Hermes Core. This SDK is how Python developers build
the *body* side: an **H3-compliant harness** (a FastAPI app) that Hermes talks
to over HTTP. Compliance is enforced by the official test battery
(`h3-test`, 43 tests, from get-h3/shim) — the gate for any harness.

## What the SDK promises

> Subclass `BaseHarness`, implement `on_process` + `on_result`, mount
> `create_router(harness)` on FastAPI → your harness speaks the H3 protocol.

## ⚠️ Install (read this first — the documented path is broken)

As of 2026-08-03 (dogfood run):

1. `pip install h3-harness-sdk` — ❌ **fails** (not on PyPI). Don't try it.
2. `pip install <repo-path>` / git install — ❌ **installs a broken wheel**:
   hatchling drops `__init__.py` (`.gitignore` `_*.py` pattern — see
   `docs/dogfood/diagnostics.md`). `from h3_harness import BaseHarness` →
   ImportError.
3. **✅ The only working path:**
   ```bash
   git clone https://github.com/get-h3/sdk-python
   pip install -e /path/to/sdk-python   # editable install
   ```

## Quickstart (works)

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
            text=TextResponse(content=f"Hello: {req.message.content}", finished=True),
        )

    async def on_result(self, req):
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))


app = FastAPI()
app.include_router(create_router(MyHarness()))
```

## Protocol loop (how Hermes drives your harness)

```
POST /v1/process  (message + context)      → Decision (tool_call|llm_call|text|wait|delegate|end)
POST /v1/result   (outcome of last exec)   → next Decision
…repeat… → Decision(end) finishes the session
GET/DELETE /v1/sessions/{id}, POST /v1/cancel, GET /v1/health
```

- `req.result` is a plain **dict** — use `req.result.get("type")`, NOT
  `req.result.type` (the shipped langchain example does the latter and crashes).
- `LLMCall.messages` is `list[dict]` — pass plain dicts, not `LLMMessage` objects.
- Exceptions in your handlers are caught by the router and returned as
  `{"decision":"end","reason":"error","summary":...}` with HTTP 200 — check
  the `summary` when a session ends unexpectedly.

## The 3 battery conventions (undocumented in README — REQUIRED for 43/43)

1. **Echo history:** include `history=list(req.context.history)` in every
   Decision you return (test: `process_preserves_history`).
2. **Models guard:** only return `LLM_CALL` when `req.context.models` is
   non-empty; use `models[0].name` (test: `no_models_available`).
3. **Streaming flag:** if the message contains "do not finish", return
   `TextResponse(..., finished=False)` (test: `process_text_finished_false`).

The shipped `src/h3_harness/examples/echo.py` implements all three — treat it
as the reference implementation. A from-scratch harness following these scored
43/43 (see `docs/dogfood/2026-08-03-integration.md` for a full example).

## Test without a server: MockHermes

```python
from h3_harness.testbed import MockHermes
from h3_harness.examples.echo import EchoHarness

mock = MockHermes(EchoHarness())
decision = await mock.send_message("Hello!")
assert decision.text.content == "Echo: Hello!"
```

## Run the acceptance gate

```bash
# any harness server:
uvicorn my_harness:app --port 9191
# THE GATE (from get-h3/shim; a binary may exist in another venv):
h3-test --endpoint http://127.0.0.1:9191        # 43/43 + exit 0 = compliant
```

## Pitfalls

- **Don't** trust `make test` alone — tests import from source and never see
  the wheel. After packaging changes, build a wheel and inspect it
  (`pip wheel --no-deps . && unzip -l dist/*.whl`) — it MUST contain
  `h3_harness/__init__.py`.
- **Don't** use the langchain example as a template yet — it crashes
  (board task DF-003).
- **Don't** PUT scheduler cooldown for this project — fleet.toml pins it.
- **Do** keep `.coding-hermes/tasks.md` present in v2.1 `|||` format
  (GitReins `validate-board-format.py` requires it); the live board is
  `.coding-hermes/board/tasks.parquet` (DuckDB).
- **Do** check `docs/dogfood/diagnostics.md` before debugging packaging or
  battery failures — the root causes are already recorded there.
