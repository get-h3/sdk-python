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

## Passing the battery (h3-test compliance)

The gate for any H3 harness is the **test battery** (`test_battery.py` from
[get-h3/shim](https://github.com/get-h3/shim) — 44 tests across 6 categories).
Run it against any running harness endpoint:

```bash
# The shim is not yet published to PyPI — install from source (get-h3/shim)
pip install git+https://github.com/get-h3/shim
h3-test --endpoint http://localhost:9191   # exit 0 = compliant
```

The Quickstart harness above implements all four conventions and is fully
battery-compliant (**44/44**). If you modify it, keep the conventions intact —
a naive harness that drops them scores **41/44**. The four conventions the
battery checks (beyond "return a Decision") are:

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

The canonical battery-ready template is **[echo.py](src/h3_harness/examples/echo.py)**
— it implements all four conventions and scores 44/44. Use it as the starting
point for your own harness.

## Error handling

Exceptions raised inside your harness's `on_process` / `on_result` are
**caught by the router and masked as a successful HTTP 200** `end` decision:

```json
{"decision": "end", "end": {"reason": "error", "summary": "<exception text>"}}
```

This masking **is the current contract** — the spec
(`get-h3/h3` → `specs/04-SDK-Libraries.md`) is silent on handler exceptions,
and the behavior is locked in by `tests/test_handler_crash.py`. From the
shim's point of view the session simply ends: it sees a normal `end` and
stops, so **the session dies silently**. If you need to distinguish a crash
from a real completion, validate the decision — the
`end.reason == "error"` marker (and the server-side
`on_process failed` / `on_result failed` log lines from
`logger.exception`) is the only signal.

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
`get_session_info` (`"completed"` once the loop reaches `end`) and the
router passes it through.

## Development

```bash
make install   # create venv + install deps
make build     # build wheel (and sdist) into dist/
make test      # run tests
make lint      # ruff check
make fmt       # ruff format
```

## Reference

- Spec: [get-h3/h3 — specs/04-SDK-Libraries.md](https://github.com/get-h3/h3/blob/main/specs/04-SDK-Libraries.md)
- Protocol: [get-h3/protocol](https://github.com/get-h3/protocol)
- API reference: [docs/api/index.md](docs/api/index.md)
