# H3 Harness SDK for Python

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

**From a clean system** (no `pip` preinstalled — e.g. a minimal Ubuntu
container): bootstrap a venv first, then install into it:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
# or the one-command equivalent: make install
```

`make install` creates `.venv` (via `python3 -m venv`), upgrades pip inside
it, and installs the package with dev extras — no system pip required.

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
            # Battery: sessions start active; on_result flips them to
            # "completed" (test_5_11 session_status_completed).
            "status": "active",
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
        # Battery: a session that has ended must report status="completed"
        # (test_5_11 session_status_completed) — flip it before returning END.
        session = self._sessions.get(req.session_id)
        if session is not None:
            session["status"] = "completed"
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))

    def get_session_info(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    async def on_session_terminate(self, session_id: str) -> None:
        # DELETE /v1/sessions/{id} -> forget the session so a later GET 404s.
        self._sessions.pop(session_id, None)


app = FastAPI()
app.include_router(create_router(MyHarness()))
# Run with: uvicorn my_harness:app --port 9191
```

**Trying it out:** with the server running, send a minimal request. The
payload must include `identity`, `context.config`, and `context.session_state`
(plus `message` and `session_id`) or the router rejects it with a 422:

```bash
curl -X POST http://localhost:9191/v1/process \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "sess-001",
    "identity": {"chat_id": "chat-1", "platform": "cli"},
    "message": {"content": "Hello, harness!"},
    "context": {"config": {}, "session_state": {}, "history": []}
  }'
```

→ `{"decision":"text","decision_id":"...","history":[],"text":{"content":"Echo: Hello, harness!","finished":true}}`

Health is at **`/v1/health`** (not `/health`): `curl http://localhost:9191/v1/health`.

### Session lifecycle

`DELETE /v1/sessions/{id}` invokes `on_session_terminate(session_id)` on the
harness (unknown ids 404 at the router before the harness is involved). The
base implementation is a **no-op**, so without an override a terminated
session stays fully retrievable: the DELETE returns `{"terminated": true}`,
but a later `GET /v1/sessions/{id}` still returns 200 with the full session.
The fix is a 3-line cleanup — drop the session from your tracking dict,
exactly as in the quickstart above:

```python
async def on_session_terminate(self, session_id: str) -> None:
    # DELETE /v1/sessions/{id} -> forget the session so a later GET 404s.
    self._sessions.pop(session_id, None)
```

Keep this override in any harness that tracks sessions — it keeps harness
state consistent with what the wire promises (a terminated session 404s on
later GET, like any unknown session).

## Testbed

<!-- Runnable as a plain script: save this block to a file and run `python file.py` -->
```python
import asyncio

from h3_harness.testbed import MockHermes
from h3_harness.examples.echo import EchoHarness


async def main() -> None:
    mock = MockHermes(EchoHarness())
    decision = await mock.send_message("Hello!")
    assert decision.text.content == "Echo: Hello!"


if __name__ == "__main__":
    asyncio.run(main())
```

## Examples

- **[echo.py](src/h3_harness/examples/echo.py)** — Echo harness that mirrors user messages
- **[minimal.py](src/h3_harness/examples/minimal.py)** — Minimal harness with health endpoint, uvicorn runner
- **[langchain_agent.py](src/h3_harness/examples/langchain_agent.py)** — LangChain integration: LLM call with text response

Each example exposes a module-level `app` and a `python -m` runner. Either
works:

```bash
# uvicorn against the module-level app (any port)
uvicorn h3_harness.examples.echo:app --port 9191
uvicorn h3_harness.examples.minimal:app --port 8000
uvicorn h3_harness.examples.langchain_agent:app --port 8000

# or the built-in runner (echo.py accepts an optional port argument;
# its default is the battery port 9191, the other two default to 8000)
python -m h3_harness.examples.echo 9191
python -m h3_harness.examples.minimal
python -m h3_harness.examples.langchain_agent
```

`langchain_agent.py` needs no extra installs — despite the name it imports no
langchain: the "LLM" is a hardcoded stand-in and the example demonstrates the
protocol pattern for delegating reasoning to an external LLM pipeline.

## Passing the battery (h3-test compliance)

The gate for any H3 harness is the **test battery** (`test_battery.py` from
[get-h3/shim](https://github.com/get-h3/shim) — 46 tests across 6 categories).
Run it against any running harness endpoint:

```bash
# The shim is not yet published to PyPI — install from source (get-h3/shim)
pip install git+https://github.com/get-h3/shim
h3-test --endpoint http://localhost:9191   # exit 0 = compliant
```

The Quickstart harness above implements all five conventions and is fully
battery-compliant (**46/46**). If you modify it, keep the conventions intact —
a naive harness that drops them scores **40/46** (measured against a harness
with no history echo, no session tracking, and no streaming flag). The five
conventions the battery checks (beyond "return a Decision") are:

1. **Echo `context.history` in every Decision returned from `on_process`.**
   The battery sends a session with prior history and asserts it flows back
   through the response (`test_2_8_process_preserves_history`). Pass it
   through explicitly:
   ```python
   history = list(req.context.history)
   return Decision(..., history=history)
   ```
   This applies to decisions returned from `on_process` — the `ProcessRequest`
   carries the `context` field. `on_result` receives a `ResultRequest`, which
   has **no** `context` field (only `decision_id`/`result`/`session_id`); a
   decision returned from `on_result` simply omits `history`. Echoing
   `req.context.history` there raises `AttributeError`.
2. **Never issue `llm_call` when `context.models` is empty.** The battery
   sends `context.models: []` and FAILS any harness that returns an `llm_call`
   decision (`test_5_8_no_models_available` — "hallucinated model"). Only
   return `LLM_CALL` when the request actually lists models.
3. **Return `text.finished=false` for "do not finish" prompts.** The battery
   sends *"Just start a thought, do not finish it yet."* and asserts the
   response has `text.finished == False` (`test_2_4_process_text_finished_false`).
   Detect streaming/unfinished intent and set `finished` accordingly.
4. **404 unknown sessions.** The battery cancels a nonexistent session
   (`test_5_9b cancel_unknown_session`) and GETs one
   (`test_5_10 session_not_found`) and asserts a 404. Track sessions in the
   harness (`get_session_info` returning `None` for unknown ids) — the router
   turns that into the 404.
5. **Report `status="completed"` once the session ends.** The battery drives
   process → result round-trips until your harness returns an `end` decision,
   then GETs the session (`test_5_11 session_status_completed`) and asserts
   `status="completed"`. This is only asserted when your harness emits a
   `status` field at all — and since GAP-058 the router supplies the status
   itself when your `get_session_info` omits it (it tracks the session's own
   lifecycle: `active` after a process call, `completed` once `on_result`
   returns `end`), so a metadata-only `get_session_info` passes too. If you do
   emit `status`, keep it truthful: set `"status": "active"` when the session
   starts and flip it to `"completed"` when `on_result` returns `end` — an
   explicit valid status always wins over the router's tracking, so a stale
   `"active"` left there is what the wire reports, and `GET /v1/health`
   (`active_sessions`) counts the very same value. The router purges its own
   live entry on that `END` decision, so an ended conversation is never left
   counted as an extra live session.

The canonical battery-ready template is **[echo.py](src/h3_harness/examples/echo.py)**
— it implements all five conventions and scores 46/46. Use it as the starting
point for your own harness.

## Error handling

Exceptions raised inside your harness's `on_process` / `on_result` are
**caught by the router and masked as a successful HTTP 200** `end` decision:

```json
{"decision": "end", "end": {"reason": "error", "summary": "<exception text>"}}
```

**A validation mistake in your own decision-building code reaches the caller
this way too.** `Decision` and its payloads are pydantic models, so building
one with the wrong kwargs — `ToolCall(tool="read_file", arguments={})`, where
the real field names are `name` and `params` — raises a `ValidationError`
inside your handler, and the API caller gets a *legitimate-looking protocol
response* rather than an error:

- HTTP **200** with `decision="end"` and `end.reason="error"`;
- the actual cause — here the pydantic validation error naming the offending
  field — in **`end.summary`**;
- one `WARNING` on the `h3_harness.harness` logger naming the masked
  `decision_id` and pointing at `end.summary`, so the failure is findable
  from the caller's own response instead of only in the server's stderr.

**For local development, `create_router(..., debug_errors=True)`** turns the
mask off:

```python
app.include_router(create_router(MyHarness(), debug_errors=True))
```

With `debug_errors=True` an exception from `on_process` / `on_result`
propagates instead of being masked, so the client gets a real **HTTP 500**
with the traceback in the server log — the fastest way to see that a
`ValidationError` is your own kwarg mistake and not a protocol end. The
default is `debug_errors=False` (masking): that is the behavior the `h3-test`
battery and existing adopters expect, so do not ship with it enabled.

This masking **is the current contract** — the spec
(`get-h3/h3` → `specs/04-SDK-Libraries.md`) is silent on handler exceptions,
and the behavior is locked in by `tests/test_handler_crash.py`. From the
shim's point of view the session simply ends: it sees a normal `end` and
stops, so **the session dies silently**. To tell a crashed session from a
real completion, read `end.reason` (the `"error"` marker), the cause in
`end.summary`, and the `WARNING` line above — the server-side
`on_process failed` / `on_result failed` log lines from `logger.exception`
still carry the full traceback.

Real HTTP 500s are reserved for **non-handler** failures and are not
disturbed by the masking: exceptions from `on_cancel` /
`on_session_terminate` surface as HTTP 500 (`{"detail": ...}`), and any
exception that escapes the router entirely is caught by the logging
middleware's catch-all, which returns an `ErrorResponse` with
`ErrorCode.INTERNAL_ERROR`. Handler-crash coverage in the shim battery
(`get-h3/shim` → `test_battery.py`) belongs to that repo — it is out of
scope for this SDK.

## Result payloads

**`result["tool_calls"]` is a LIST.** When a result carries tool calls
(OpenAI-style LLM APIs), `req.result["tool_calls"]` is a `list[dict]`, one
entry per call — never a single dict:

```python
tool_calls = req.result.get("tool_calls") or []
if not isinstance(tool_calls, list):
    tool_calls = [tool_calls]  # defensive: accept a lone dict too
for call in tool_calls:
    print(call["name"])  # each entry is a plain dict
```

Dict-style access on the list (`req.result["tool_calls"].get("name")`)
raises `AttributeError: 'list' object has no attribute 'get'` — which,
under the error contract above, surfaces as a silent HTTP 200 `end/error`
and kills the session with no signal.

`req.result` itself is a **plain dict** — read fields with `.get()`, never
attribute style (`req.result.type` raises `AttributeError`). The canonical
shape is `ResultPayload`; see `docs/api/protocol.md`.

`GET /v1/sessions/{id}` reports session status: `"active"` (default) or
`"completed"`. Harnesses that track lifecycle return a `status` key from
`get_session_info` (`"completed"` once the loop reaches `end`) and the router
passes it through; harnesses that don't get the router's own tracking instead
(`"completed"` once `on_result` returns `end`), so `status` and the
`active_sessions` count in `GET /v1/health` always agree.

## Tool-calling harnesses

The Quickstart covers the **text** path. A tool-calling harness returns a
`Decision(decision=DecisionType.TOOL_CALL, ...)` instead, and the wire
contract around it has sharp edges that cost real debugging time when guessed
at. Every shape below is **measured** against this SDK (captured from a live
uvicorn server), not transcribed from the spec.

### The request payload needs every required field

`POST /v1/process` requires `session_id`, `identity`, and `message` at the
top level, plus `context.config` and `context.session_state` inside
`context`. Miss any of them and FastAPI rejects the request with a `422`
before your harness runs. Inside `identity`, `chat_id` and `platform` are
required (`user_id`, `user_name`, `thread_id` are optional). Empty objects
pass for `config`/`session_state` — the keys just have to be present. A
request without `identity` fails like this (measured):

```json
{"detail":[{"type":"missing","loc":["body","identity"],"msg":"Field required","input":{"session_id":"sess-tool-002","message":{"content":"deploy the app"},"context":{"config":{},"session_state":{},"history":[]}}}]}
```

A complete, valid payload:

```bash
curl -X POST http://localhost:9191/v1/process \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "sess-tool-001",
    "identity": {"chat_id": "chat-1", "platform": "cli", "user_id": "user-1"},
    "message": {"content": "deploy the app"},
    "context": {
      "config": {"timeout_seconds": 300},
      "session_state": {"turn_count": 0},
      "history": []
    }
  }'
```

### The response is FLAT — `decision` is a string discriminator

There is no nested `"decision": {...}` object. The response carries a
top-level `decision` **string** naming the decision type, and the payload
sits in a top-level key named after that type. Measured response (HTTP 200)
for a tool-call decision:

```json
{"decision":"tool_call","decision_id":"6fda46c9-7b2c-4aba-b791-9a1f1e68cdd0","history":[],"tool_call":{"name":"deploy_app","params":{"env":"staging","replicas":2},"reasoning":"user asked to deploy"}}
```

Read the call from `resp["tool_call"]`, not
`resp["decision"]["tool_call"]` — the latter doesn't exist.

### Handler side: `ToolCall` takes `name` / `params` / `reasoning`

The `ToolCall` fields are exactly `name` (str), `params` (dict) and
`reasoning` (optional str). There is no `arguments` and no `call_id` —
OpenAI-style guesses fail validation:

```python
from h3_harness import Decision, DecisionType, ToolCall


def deploy_decision(req) -> Decision:
    return Decision(
        decision=DecisionType.TOOL_CALL,
        tool_call=ToolCall(
            name="deploy_app",
            params={"env": "staging", "replicas": 2},  # not "arguments"
            reasoning="user asked to deploy",
        ),
        history=list(req.context.history),
    )
```

### `on_result`: tool results arrive as a RAW dict

`ResultRequest.result` is typed `dict[str, Any]` and the router does **not**
validate it against `ResultPayload` — the exported `ResultPayload` model
(`type`/`success`/`tool_name`/`data`/`duration_ms`) documents the canonical
shape, but nothing on this path constructs it. The natural typed-access path
therefore raises:

```python
from h3_harness import Decision, DecisionType, End


async def on_result(self, req):
    # req.result is a RAW dict, not a ResultPayload: attribute access
    # (req.result.data) raises AttributeError: 'dict' object has no
    # attribute 'data'. Use dict access.
    tool_calls = req.result.get("tool_calls") or []  # list[dict]
    for call in tool_calls:
        print(call["name"])  # plain dict access — never call.data
    return Decision(decision=DecisionType.END, end=End(reason="task_complete"))
```

(See *Result payloads* above for more on the raw-dict result shape.)

### Failure modes: handler mistakes come back as HTTP 200, not 4xx

Two different layers, two very different failure surfaces:

- **Request-shape mistakes** (missing `identity`, `config`,
  `session_state`, …) → clean `422`: FastAPI validates the request body
  before your handler runs.
- **Handler-side mistakes** (a `ToolCall` built with `arguments=` instead
  of `params=`, `.data` attribute access on a raw dict) raise *inside*
  `on_process` / `on_result` — and the router converts any handler
  exception into a normal-looking **HTTP 200** `end` decision (measured):

```json
{"decision":"end","decision_id":"b859661d-8e66-4871-8d17-1752165b4c0b","history":[],"end":{"reason":"error","summary":"1 validation error for ToolCall\nparams\n  Field required [type=missing, input_value={'name': 'deploy_app', 'a...ts': {'env': 'staging'}}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/missing"}}
```

The only signals are `end.reason == "error"`, the (truncated) traceback in
`end.summary`, and the full traceback in the **server logs**
(`logger.exception("on_process failed")`) — the client sees a success
status either way. This masking is the current contract (see *Error
handling* above); making validation failures loud is tracked separately as
GAP-065. Until then, don't rely on a 4xx to tell you your decision shape is
wrong — check `end.summary` when a session ends unexpectedly.

## Development

```bash
make install   # create venv + install deps
make build     # build wheel (and sdist) into dist/
make test      # run tests
make lint      # ruff check
make fmt       # ruff format
make generate  # regenerate src/h3_harness/protocol.py from JSON Schema
```

**Running tests:** use the project venv — `make install` then `.venv/bin/pytest`
(229 tests). Bare `pytest` on an ambient interpreter may fail to import
`h3_harness`; `pytest.ini`'s `pythonpath = src` covers collection from the
source tree without an install, but the project venv is the supported path.

### Regenerating the protocol models

`make generate` regenerates `src/h3_harness/protocol.py` from the JSON Schemas
in `get-h3/protocol/schemas/v1`. It prefers a sibling `protocol` checkout when
one sits next to this repo, otherwise it uses the vendored copies in
`tests/schemas/v1` — so it works on a fresh clone with no sibling checkout.
Override the source with `--schema-dir /path/to/schemas/v1` or `H3_SCHEMA_DIR`.

## Documentation

- **[docs/integration-guide.md](docs/integration-guide.md)** — prereqs, install,
  first harness, uvicorn run, curl smoke test (including the `decision_id`
  chaining example for `POST /v1/result`), and running the h3-test battery.
- **[docs/api-reference.md](docs/api-reference.md)** — endpoint reference,
  request/response model field tables, `Decision` variants, and the
  `BaseHarness` abstract-vs-optional method contract.
- **[docs/api/index.md](docs/api/index.md)** — the hand-written per-module
  reference pages (`protocol`, `harness`, `middleware`, `testbed`, `examples`).

## Reference

- Spec: [get-h3/h3 — specs/04-SDK-Libraries.md](https://github.com/get-h3/h3/blob/main/specs/04-SDK-Libraries.md)
- Protocol: [get-h3/protocol](https://github.com/get-h3/protocol)
- API reference: [docs/api/index.md](docs/api/index.md)
