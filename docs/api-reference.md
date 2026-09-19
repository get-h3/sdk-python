# H3 Harness SDK for Python — API Reference

Reference for `h3-harness-sdk` **0.1.5** (import package `h3_harness`): the HTTP
surface your harness exposes, the request/response models it exchanges, and the
`BaseHarness` methods you implement.

> **Version note:** the package version is sourced from one place —
> `src/h3_harness/_version.py` — and surfaced as `h3_harness.__version__` and in
> the `GET /v1/health` `version` field. This document must never hardcode a
> version other than that one; the CI `docs-version-sweep` job (GAP-040) fails
> the build on drift.

Everything below was read off the source in `src/h3_harness/`. Where a docstring
and the code disagree, the code wins.

**New here?** Start with the [Integration Guide](integration-guide.md) — it
takes you from `pip install` to a battery-passing harness, then come back here
for the full field tables.

---

## Package layout

| Module | Contents |
|---|---|
| `h3_harness` | Top-level re-exports (`__all__`): `BaseHarness`, `create_router`, `add_middleware`, `__version__`, and 21 protocol models/enums. |
| `h3_harness.protocol` | All 33 Pydantic models and enums of the H3 v1 protocol (generated from the `get-h3/protocol` JSON Schema). The 12 not re-exported at the top level (`Attachment`, `Capability`, `Config`, `Context`, `HistoryEntry`, `LLMMessage`, `Message`, `Model`, `ErrorDetail`, `Identity`, `SessionState`, `Tool`) are imported from `h3_harness.protocol`. |
| `h3_harness.harness` | `BaseHarness` (ABC) and `create_router` (FastAPI router factory). |
| `h3_harness.middleware` | `add_middleware(app)` — request logging + a catch-all error handler. |
| `h3_harness.testbed` | `MockHermes` — drive a harness in-process from pytest/scripts, with no server. |
| `h3_harness.examples` | Three runnable examples: `echo.py` (battery template), `minimal.py`, `langchain_agent.py`. |

```python
from fastapi import FastAPI
from h3_harness import BaseHarness, Decision, DecisionType, TextResponse, create_router


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

---

## The agent loop

```
Hermes Core                                             Your harness
     │  POST /v1/process  (ProcessRequest)                    │
     │ ──────────────────────────────────────────────────────► │  on_process(req)
     │ ◄────────────────────────────────────── Decision ────── │
     │                                                         │
     │  (Hermes executes the decision: tool / LLM / text /      │
     │   wait / delegate)                                      │
     │                                                         │
     │  POST /v1/result   (ResultRequest: decision_id + result) │
     │ ──────────────────────────────────────────────────────► │  on_result(req)
     │ ◄────────────────────────────────────── Decision ────── │
     │                                                         │
     │  … repeats until a Decision with decision="end" …        │
```

Every `Decision` carries a fresh `decision_id` (UUID4). Hermes echoes that id
back on `POST /v1/result`, which is how your `on_result` learns **which**
decision the result belongs to. See
[Chaining `decision_id`](integration-guide.md#4-smoke-test-it-with-curl).

---

## Endpoints

`create_router(harness, *, prefix="")` registers exactly six routes. `prefix` is
prepended to every path (`prefix="/api"` → `/api/v1/health`).

| Method | Path | Request body | Success response | Error responses |
|---|---|---|---|---|
| `GET` | `/v1/health` | — | `200` `HealthResponse` | — |
| `POST` | `/v1/process` | `ProcessRequest` | `200` `Decision` (`response_model_exclude_none=True`) | `422` validation error |
| `POST` | `/v1/result` | `ResultRequest` | `200` `Decision` (`response_model_exclude_none=True`) | `422` validation error |
| `POST` | `/v1/cancel` | `CancelRequest` | `200` `{"session_id": str, "cancelled": bool}` | `404` unknown session, `500` hook raised, `422` validation error |
| `GET` | `/v1/sessions/{session_id}` | — | `200` `SessionResponse` | `404` unknown session (only when the harness tracks sessions) |
| `DELETE` | `/v1/sessions/{session_id}` | — | `200` `{"session_id": str, "terminated": true}` | `404` unknown session (tracked harnesses), `500` hook raised |

Notes that bite in practice:

- **`422` bodies come from FastAPI/pydantic**, not from `ErrorResponse`. A
  missing `identity` or `context.config`/`context.session_state` is rejected
  before your code runs.
- **An exception raised inside `on_process`/`on_result` is *not* a 500.** The
  router logs `on_process failed` / `on_result failed` and returns
  `Decision(decision=END, end=End(reason="error", summary=str(exc)))`. The
  session dies silently from the shim's point of view; `end.reason == "error"`
  is the only signal.
- **`404` on cancel/GET/DELETE only happens if your harness implements
  `get_session_info`.** Without it the router skips existence checks entirely.
  With it, a `None` return means "unknown session" and the router answers `404
  {"detail": "Session not found"}`.
- `500` bodies for `cancel`/`DELETE` are FastAPI's `{"detail": "<exception
  text>"}` — raised when `on_cancel` / `on_session_terminate` raises.

---

## Request models

### `ProcessRequest` — `POST /v1/process`

| Field | Type | Required | Notes |
|---|---|---|---|
| `context` | `Context` | yes | Conversation + session context (below). |
| `identity` | `Identity` | yes | Who is talking. |
| `message` | `Message` | yes | The new user message. |
| `session_id` | `str` | yes | Stable id for the session; key your per-session state on it. |

### `Context`

| Field | Type | Default | Notes |
|---|---|---|---|
| `config` | `Config` | — (required) | Loop budget/limits. |
| `session_state` | `SessionState` | — (required) | Counters/cost so far. |
| `history` | `list[HistoryEntry]` | `[]` | Prior turns. **Echo this back in your `on_process` Decision** — the battery asserts it round-trips. |
| `models` | `list[Model]` | `[]` | Models Hermes can run. **Empty means "no model available"** — never return `llm_call` in that case. |
| `tools` | `list[Tool]` | `[]` | Tools Hermes can execute. |
| `memory` | `str \| None` | `None` | Optional memory blob. |
| `skills` | `list[str] \| None` | `None` | Optional skill names. |

### `Config`

| Field | Type | Default |
|---|---|---|
| `max_iterations` | `int \| None` | `None` |
| `timeout_seconds` | `int` | `300` |
| `max_tool_calls_per_turn` | `int \| None` | `None` |
| `project_dir` | `str \| None` | `None` |
| `temperature` | `float \| None` | `None` |

### `SessionState`

| Field | Type | Default |
|---|---|---|
| `cost_so_far` | `float` | `0.0` |
| `started_at` | `str \| None` | `None` |
| `total_llm_calls` | `int` | `0` |
| `total_tool_calls` | `int` | `0` |
| `turn_count` | `int` | `0` |

### `Identity`

| Field | Type | Required |
|---|---|---|
| `chat_id` | `str` | yes |
| `platform` | `str` | yes |
| `user_id` | `str \| None` | no |
| `user_name` | `str \| None` | no |
| `thread_id` | `str \| None` | no |

### `Message` and `HistoryEntry`

| Model | Field | Type | Default |
|---|---|---|---|
| `Message` | `content` | `str` | required |
| `Message` | `role` | `str` | `"user"` |
| `Message` | `timestamp` | `str \| None` | `None` |
| `Message` | `attachments` | `list[Attachment] \| None` | `None` |
| `HistoryEntry` | `content` | `str` | required |
| `HistoryEntry` | `role` | `str` | required |

`Attachment` = `{mime_type: str, type: str, url: str}` (all required).

### `Tool` and `Model`

`Tool` = `{name: str, description: str, parameters: dict[str, Any]}` — all required.

| `Model` field | Type | Required |
|---|---|---|
| `name` | `str` | yes |
| `provider` | `str` | yes |
| `context_window` | `int` | yes |
| `cost_per_1k_input` | `float \| None` | no |
| `cost_per_1k_output` | `float \| None` | no |
| `supports_tool_calling` | `bool \| None` | no |
| `supports_vision` | `bool \| None` | no |

### `ResultRequest` — `POST /v1/result`

| Field | Type | Required | Notes |
|---|---|---|---|
| `decision_id` | `str` | yes | The `decision_id` of the `Decision` this result belongs to. |
| `result` | `dict[str, Any]` | yes | **Plain dict** — read with `.get()`, never attribute access (`req.result.type` raises `AttributeError`). |
| `session_id` | `str` | yes | Same id as the originating `process` call. |

`ResultRequest` has **no `context` field** — decisions returned from
`on_result` must omit `history` (touching `req.context.history` there raises
`AttributeError`).

`ResultPayload` is the canonical shape of `result`:

| Field | Type | Required |
|---|---|---|
| `type` | `str` | yes — one of the `ResultType` values below |
| `success` | `bool` | yes |
| `tool_name` | `str \| None` | no |
| `data` | `dict[str, Any] \| None` | no |
| `duration_ms` | `int \| None` (≥ 0) | no |

**`result["tool_calls"]` is a list.** When a result carries tool calls, it is
`list[dict]`, one entry per call — never a single dict:

```python
tool_calls = req.result.get("tool_calls") or []
if not isinstance(tool_calls, list):
    tool_calls = [tool_calls]  # defensive: accept a lone dict too
```

### `CancelRequest` — `POST /v1/cancel`

| Field | Type | Required |
|---|---|---|
| `session_id` | `str` | yes |
| `reason` | `str` | yes — one of `user_interrupt`, `timeout`, `system` (`CancelReason`) |

---

## Response models

### `Decision`

Returned by `POST /v1/process` and `POST /v1/result`. Serialized with
`response_model_exclude_none=True`, so unset payload fields are omitted from the
JSON.

| Field | Type | Default | Notes |
|---|---|---|---|
| `decision` | `DecisionType` | required | Selects which payload field is meaningful. |
| `decision_id` | `str` | `str(uuid4())` | Auto-generated per Decision; echo it back via `ResultRequest.decision_id`. |
| `history` | `list[HistoryEntry]` | `[]` | Echo `req.context.history` from `on_process` only. |
| `tool_call` | `ToolCall \| None` | `None` | Payload when `decision == "tool_call"`. |
| `llm_call` | `LLMCall \| None` | `None` | Payload when `decision == "llm_call"`. |
| `text` | `TextResponse \| None` | `None` | Payload when `decision == "text"`. |
| `wait` | `Wait \| None` | `None` | Payload when `decision == "wait"`. |
| `delegate` | `Delegate \| None` | `None` | Payload when `decision == "delegate"`. |
| `end` | `End \| None` | `None` | Payload when `decision == "end"`. |

### Decision variants

| `DecisionType` value | Payload model | Payload fields | Meaning |
|---|---|---|---|
| `text` | `TextResponse` | `content: str`, `finished: bool` | Send text to the user. `finished=false` = more coming (streaming). |
| `tool_call` | `ToolCall` | `name: str`, `params: dict[str, Any]`, `reasoning: str \| None` | Ask Hermes to execute a tool. |
| `llm_call` | `LLMCall` | `messages: list[dict[str, Any]]`, `model: str`, `max_tokens: int \| None`, `system_prompt: str \| None`, `temperature: float \| None` | Ask Hermes to run an LLM prompt. Only valid when `context.models` is non-empty. |
| `wait` | `Wait` | `reason: str`, `duration_seconds: int \| None` (≥ 1), `poll_endpoint: str \| None` | Pause for an external signal. |
| `delegate` | `Delegate` | `task: str`, `agent: str \| None`, `context: str \| None`, `model: str \| None`, `provider: str \| None` | Spawn a sub-agent. |
| `end` | `End` | `reason: str`, `summary: str \| None` | Terminate the session. `reason` uses the `EndReason` values: `task_complete`, `user_requested`, `error`, `timeout`, `rate_limited`, `cancelled`. |

`Decision(decision=DecisionType.TEXT, text=...)` is the only variant the shipped
echo/minimal templates need; `langchain_agent.py` shows the `llm_call` loop.

```python
Decision(decision=DecisionType.TEXT, text=TextResponse(content="hello", finished=True))
Decision(
    decision=DecisionType.TOOL_CALL,
    tool_call=ToolCall(name="read_file", params={"path": "a.txt"}),
)
Decision(
    decision=DecisionType.LLM_CALL,
    llm_call=LLMCall(
        model=req.context.models[0].name, messages=[{"role": "user", "content": "hi"}]
    ),
)
Decision(decision=DecisionType.WAIT, wait=Wait(reason="awaiting approval"))
Decision(decision=DecisionType.DELEGATE, delegate=Delegate(task="summarize the repo"))
Decision(decision=DecisionType.END, end=End(reason=EndReason.TASK_COMPLETE))
```

### `HealthResponse` — `GET /v1/health`

| Field | Type | Required | Base-harness value |
|---|---|---|---|
| `status` | `str` | yes | `"ok"` (`HealthStatus`: `ok` / `degraded` / `down`) |
| `version` | `str` | yes | the SDK version (`0.1.5`, from `_version.py`) |
| `active_sessions` | `int \| None` | no | live session count from router tracking; `None` only when the harness tracks no sessions |
| `capabilities` | `list[str] \| None` | no | `list(Capability)` — all six decision types |
| `degraded_reason` | `str \| None` | no | `None` |
| `error` | `str \| None` | no | `None` |
| `protocol_version` | `str \| None` | no | `"1.0"` |
| `transport` | `str \| None` | no | `"rest"` |
| `uptime_seconds` | `int \| None` | no | seconds since `__init__` (lazily initialised) |

Override `health()` to report `degraded`/`down` or add your own fields. The
base implementation already populates `active_sessions` from the router's
session tracking: `POST /v1/process` marks a session live, an `END` decision
from `POST /v1/result` (or `DELETE /v1/sessions/{id}`) marks it completed, and
`active_sessions` is `None` only for a harness that tracks no sessions at all
(no traffic and no `get_session_info`).

### `SessionResponse` — `GET /v1/sessions/{session_id}`

| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | Echoes the path parameter. |
| `started_at` | `str` | ISO-8601. Populated from `get_session_info()["started_at"]`; epoch numbers are coerced, `""` when absent. |
| `last_active` | `str` | Same handling as `started_at`. |
| `turn_count` | `int` | From `get_session_info()["turn_count"]`, default `0`. |
| `status` | `str` | `active` / `completed` / `expired` / `cancelled` (`SessionStatus`); unknown values fall back to `active`. |
| `current_decision` | `str \| None` | Present in the model; not populated by the router (`null`). |
| `current_decision_type` | `str \| None` | Present in the model; not populated by the router (`null`). |

Without `get_session_info`, the router always returns
`status="active"`, `started_at=""`, `last_active=""`, `turn_count=0`.

### Error models

`POST /v1/cancel` and `DELETE /v1/sessions/{id}` never use these — their `500`
bodies are FastAPI's `{"detail": "..."}`. `ErrorResponse` is what the logging
middleware returns for an exception that escapes the router:

```json
{"error": {"code": "INTERNAL_ERROR", "message": "...", "field": null}}
```

`ErrorDetail` = `{message: str (required), code: str | None, field: str | None}`;
`ErrorResponse` = `{error: dict[str, Any]}`. `ErrorCode` values:
`INVALID_REQUEST`, `INVALID_DECISION`, `UNKNOWN_TOOL`, `UNKNOWN_MODEL`,
`SESSION_NOT_FOUND`, `SESSION_EXPIRED`, `HARNESS_TIMEOUT`, `INTERNAL_ERROR`.

---

## Which methods do I implement?

Read off `src/h3_harness/harness.py` — this is the actual abstract-vs-optional
split:

| Method | Status | Signature | Default behaviour |
|---|---|---|---|
| `on_process` | **abstract — required** | `async def on_process(self, req: ProcessRequest) -> Decision` | none — `BaseHarness` cannot be instantiated without it |
| `on_result` | **abstract — required** | `async def on_result(self, req: ResultRequest) -> Decision` | none |
| `on_cancel` | optional override | `async def on_cancel(self, req: CancelRequest) -> bool` | returns `True` (cancel confirmed) |
| `on_session_terminate` | optional override | `async def on_session_terminate(self, session_id: str) -> None` | no-op |
| `health` | optional override | `def health(self) -> HealthResponse` | `ok` payload above |
| `get_session_info` | **duck-typed — not on the ABC** | `def get_session_info(self, session_id: str) -> dict \| None` | absent → router reports every session as `active` and never 404s |
| `__init__` | optional | `def __init__(self) -> None` | call `super().__init__()` to record `_started_at` (uptime); `health()` lazily initialises it anyway |

`get_session_info` may return the keys `started_at`, `last_active`,
`turn_count`, `status`. Returning `None` makes `GET`/`DELETE /v1/sessions/{id}`
and `POST /v1/cancel` answer `404` for that id.

**Minimum to pass the battery** (46 tests, `get-h3/shim` → `h3-test`):
implement `get_session_info` (404s), echo `context.history` from `on_process`,
set `text.finished=False` for "do not finish" prompts, and never return
`llm_call` when `context.models` is empty. `src/h3_harness/examples/echo.py` is
the battery-ready template; the
[Integration Guide](integration-guide.md) has the full recipe.

---

## Enums (appendix)

| Enum | Values |
|---|---|
| `DecisionType` | `tool_call`, `llm_call`, `text`, `wait`, `delegate`, `end` |
| `Capability` | same six values as `DecisionType` |
| `EndReason` | `task_complete`, `user_requested`, `error`, `timeout`, `rate_limited`, `cancelled` |
| `CancelReason` | `user_interrupt`, `timeout`, `system` |
| `ResultType` | `tool_result`, `llm_response`, `text_sent`, `delegate_result`, `wait_timeout`, `error` |
| `HealthStatus` | `ok`, `degraded`, `down` |
| `SessionStatus` | `active`, `completed`, `expired`, `cancelled` |
| `ErrorCode` | `INVALID_REQUEST`, `INVALID_DECISION`, `UNKNOWN_TOOL`, `UNKNOWN_MODEL`, `SESSION_NOT_FOUND`, `SESSION_EXPIRED`, `HARNESS_TIMEOUT`, `INTERNAL_ERROR` |

> `End.reason` and `EndReason` are not tied together by pydantic — `End.reason`
> is a plain `str`, so `End(reason="task_complete")` is valid and the constants
> in `EndReason` are the canonical spellings.

---

## See also

| Doc | Covers |
|---|---|
| [Integration Guide](integration-guide.md) | Prereqs → install → first harness → uvicorn → curl smoke test (incl. `decision_id` chaining) → running the battery → 15-minute checklist. |
| [api/index.md](api/index.md) | Map of the hand-written reference pages below. |
| [api/protocol.md](api/protocol.md) | Every enum/model with generated-schema detail. |
| [api/harness.md](api/harness.md) | `BaseHarness` + `create_router` deep dive, per-endpoint behavior. |
| [api/testbed.md](api/testbed.md) | `MockHermes` — in-process testing without a server. |
| [api/middleware.md](api/middleware.md) | `add_middleware` — request logging and the catch-all error handler. |
| [api/examples.md](api/examples.md) | The three shipped examples and what each demonstrates. |
| [README](../README.md) | Install, quickstart, battery conventions. |
