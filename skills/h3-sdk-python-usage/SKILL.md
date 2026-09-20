---
name: h3-sdk-python-usage
description: >-
  How to USE the H3 Python SDK (get-h3/sdk-python) — build H3-compliant agent
  harnesses that Hermes Core can use as a brain. Install path, quickstart,
  the 3 battery conventions, pitfalls. Load this before touching this repo or
  building a harness with h3-harness-sdk.
version: 1.0.4
category: software-development
---

# H3 Python SDK — Usage Skill

The H3 ("Hermes Harness Hooks") protocol lets an external agent system become
the *thinking brain* of Hermes Core. This SDK is how Python developers build
the *body* side: an **H3-compliant harness** (a FastAPI app) that Hermes talks
to over HTTP. Compliance is enforced by the official test battery
(`h3-test`, 46 tests, from get-h3/shim) — the gate for any harness.

## What the SDK promises

> Subclass `BaseHarness`, implement `on_process` + `on_result`, mount
> `create_router(harness)` on FastAPI → your harness speaks the H3 protocol.

## Install

**Last verified: 2026-09-19** (dogfood run: fresh venv `pip install h3-harness-sdk`
→ 0.1.5 from PyPI, import OK; real consumer todo-harness with tool-calls built
end-to-end; fresh bunker clone of HEAD a7be001 + `make install` RC 0 in 25s on
bare Debian 13 / Python 3.13 — see docs/dogfood/2026-09-19-integration.md).

## Wire contract quick facts (learned the hard way, 2026-09-19)

- POST /v1/process requires: `identity` `{user_id, chat_id, platform}` AND
  `context` with `config` + `session_state` (both may be `{}`). Missing any → 422.
- Responses are FLAT: `decision` is a string discriminator, payload fields sit
  at top level (`resp["text"]["content"]`, NOT `resp["decision"]["text"]`).
- `ToolCall(name=..., params=..., reasoning=...)` — there is no
  `arguments`/`call_id`. Wrong kwargs → Pydantic error → router masks it into
  HTTP 200 `{"decision":"end","end":{"reason":"error","summary":...}}`;
  the cause is in `end.summary` and server logs.
- `ResultRequest.result` arrives in `on_result` as a RAW DICT (the exported
  `ResultPayload` model is not applied) — use `req.result.get("data", {})`.
- The harness NEVER executes tools: `on_process` only proposes the tool_call;
  the caller executes and POSTs /v1/result; apply tool effects in `on_result`.

## Install checklist

1. **✅ `pip install h3-harness-sdk`** — the package IS published on PyPI
   (0.1.3, released 2026-08-13 with the GAP-019/025/029 + MockHermes
   `send_message(models=...)` fixes). This is the primary install path.
2. **⚠️ Version-number gates are NOT content gates:** the `release-readiness`
   job (GAP-032) fails when the published PyPI *version* lags the repo
   version, and `docs-version-sweep` (GAP-040) catches docs version drift —
   but NEITHER catches a wheel that is content-stale at the SAME version
   number. Proven 2026-08-23: published 0.1.3 lacks the GAP-035 status
   pass-through (fix landed 3 min after the upload; never re-published) while
   both gates stayed green (GAP-043). When a fix touches
   `harness.py`/`testbed.py`/`protocol.py`, manually compare the last PyPI
   upload time (`https://pypi.org/pypi/h3-harness-sdk/json`) against the fix
   commit time — if the upload predates the fix, the wheel is stale. To diff
   content: `diff src/h3_harness/harness.py <venv>/lib/python3.*/site-packages/h3_harness/harness.py`.
3. **From-source fallback** (pre-release / want repo HEAD):
   ```bash
   pip install git+https://github.com/get-h3/sdk-python
   # or editable for development:
   git clone https://github.com/get-h3/sdk-python
   pip install -e /path/to/sdk-python
   ```
   (The wheel now contains `h3_harness/__init__.py` — DF-001 anchored the
   `_*.py` gitignore pattern to `/_*.py`; see `docs/dogfood/diagnostics.md`.)

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
  `req.result.type` (the shipped langchain example was fixed to use `.get()`
  — DF-003 — and is covered by regression tests).
- `LLMCall.messages` is `list[dict]` — pass plain dicts, not `LLMMessage` objects.
- Exceptions in your handlers are caught by the router and returned as
  `{"decision":"end","reason":"error","summary":...}` with HTTP 200 — check
  the `summary` when a session ends unexpectedly.

## The 3 battery conventions (undocumented in README — REQUIRED for 46/46)

1. **Echo history:** include `history=list(req.context.history)` in every
   Decision returned from **`on_process`** (test: `process_preserves_history`).
   ⚠️ **`on_result` has NO context** — `ResultRequest` carries only
   `decision_id`/`result`/`session_id`; do NOT reference `req.context` there
   (GAP-033; a doc-following user crashes on first /v1/result).
2. **Models guard:** only return `LLM_CALL` when `req.context.models` is
   non-empty; use `models[0].name` (test: `no_models_available`).
3. **Streaming flag:** if the message contains "do not finish", return
   `TextResponse(..., finished=False)` (test: `process_text_finished_false`).
   Apply it in EVERY TEXT branch, including the empty-models fallback —
   the battery caught a harness that missed it there (2026-08-13 run).

The shipped `src/h3_harness/examples/echo.py` implements all three — treat it
as the reference implementation. A from-scratch harness following these passed
the whole battery (see `docs/dogfood/2026-08-03-integration.md` for a full example).

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
h3-test --endpoint http://127.0.0.1:9191        # 46/46 + exit 0 = compliant
```

## Pitfalls

- **Don't** trust `make test` alone — tests import from source and never see
  the wheel. After packaging changes, build a wheel and inspect it
  (`pip wheel --no-deps . && unzip -l dist/*.whl`) — it MUST contain
  `h3_harness/__init__.py`.
- **Don't** assume repo-HEAD behavior is what users get: the published PyPI
  wheel can lag the repo even at the SAME version number (proven 2026-08-23:
  0.1.3 wheel lacks GAP-035's `_session_status` pass-through — GAP-043; the
  `release-readiness` version gate stayed green). Manual check: last PyPI
  upload time vs fix commit time; content diff against the installed wheel.
- **Do** expect `GET /v1/sessions/{id}` status to be hardcoded `"active"` on
  the published 0.1.3 wheel even after the session ENDs — the status
  pass-through only exists in repo HEAD (GAP-035, GAP-043). If your harness
  sets `status: "completed"` and the wire says `"active"`, that's the wheel,
  not your bug.
- **Do** expect a harness whose `get_session_info` carries no `status` key to
  still report `completed` after an `end` decision on repo HEAD since GAP-058:
  the router falls back to its own per-session tracking
  (`BaseHarness.session_status`), the same source `GET /v1/health`
  (`active_sessions`) counts, so the two surfaces agree. An explicit valid
  `status` in the dict still wins — a stale `"active"` left there is what the
  wire reports.
- **Do** override `on_session_terminate` to actually drop session state if you
  track sessions — the base implementation is a no-op, so `DELETE
  /v1/sessions/{id}` returns `{"terminated":true}` while `GET` still returns
  the session (GAP-044). The quickstart/echo examples don't override it either.
- **Do** handle `tool_calls` as a LIST (OpenAI style) — real LLM responses
  wrap tool calls in arrays; the shipped examples only show single dicts.
- **Do** expect handler exceptions to surface as HTTP 200
  `{"decision":"end","reason":"error","summary":...}` (GAP-034) — check
  `summary` and server logs when a session ends unexpectedly.
- **Do** use `src/h3_harness/examples/langchain_agent.py` as a LangChain
  integration reference — the dict-access bugs (DF-003) are fixed.
- **Don't** PUT scheduler cooldown for this project — fleet.toml pins it.
- **Do** keep `.coding-hermes/tasks.md` present in v2.1 `|||` format
  (GitReins `validate-board-format.py` requires it); the live board is
  JSONL-canonical — **new tasks go in `.coding-hermes/board/tasks.jsonl`**
  (the foreman reads that, not tasks.md); tasks.md mirrors active rows.
  `board.db` and `*.parquet` are local caches (JSONL-NORM-001).
- **Do** check `docs/dogfood/diagnostics.md` before debugging packaging or
  battery failures — the root causes are already recorded there.
