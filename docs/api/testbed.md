# `h3_harness.testbed` — `MockHermes`

**Module:** `h3_harness.testbed` — import directly:
`from h3_harness.testbed import MockHermes`.

`MockHermes` simulates Hermes Core for testing H3-compliant harnesses without
a running server. It wraps a `BaseHarness` instance and provides convenience
methods that build protocol-correct requests and return the harness's
`Decision`.

**Scope of that promise:** `MockHermes` builds a protocol-correct
`ProcessRequest` / `ResultRequest` / `CancelRequest` and calls the harness hook
directly (`on_process` / `on_result` / `on_cancel`). Your harness code runs on
the same path the router drives it through, so hook-level logic (echoing
history, the models guard, the streaming flag, session bookkeeping) is tested
faithfully. What is **not** in the loop is the HTTP layer itself: request
validation, the router's error masking, and the router's own session tracking.
Use a wire test (`create_router` + a server or `TestClient`) whenever those are
what you mean to pin — see *Where MockHermes and the wire diverge* below.

---

## `MockHermes(harness: BaseHarness)`

Constructor takes the harness instance to drive.

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `harness` | `BaseHarness` | The harness under test (set from the constructor argument). |

### Methods

#### `async send_message(content: str, *, session_id: str = "test-session", models: list[Model] | None = None) -> Decision`

Send a user message to the harness and return its Decision (calls
`harness.on_process`).

The request is built with:

- `Message(content=content, timestamp=<current UTC ISO 8601>)`
- `Identity(platform="test", chat_id="test", user_name="test", user_id="test-user")`
- `Context(config=Config(max_iterations=10, timeout_seconds=300),
  session_state=SessionState(started_at=<current UTC ISO 8601>))` — history
  and tools are empty.
- `models` defaults to an **empty list**, matching the battery's no-models
  context (README convention #2). Pass `models=[Model(...)]` to exercise the
  `llm_call` branch instead.

#### `async send_result(result: ResultPayload, *, session_id: str = "test-session", decision_id: str | None = None) -> Decision`

Send a result back to the harness and return its next Decision (calls
`harness.on_result`).

- `result` may be a `ResultPayload` instance **or** a plain `dict` (a dict is
  passed through as-is; a `ResultPayload` is converted with
  `result.model_dump()`).
- If `decision_id` is omitted, a UUID is auto-generated.

#### `async cancel(session_id: str = "test-session", reason: CancelReason = CancelReason.USER_INTERRUPT) -> bool`

Send a cancel request and return whether the harness confirmed (calls
`harness.on_cancel`).

- The harness is asked **unconditionally**: `MockHermes` calls `on_cancel`
  directly, so it never answers 404 the way `POST /v1/cancel` does for a
  session your harness does not know (see the divergence table).

---

## Where MockHermes and the wire diverge

`MockHermes` returns **the harness's own answer** to the hook. The router wraps
that hook, so three behaviours differ, each measured on this SDK:

| Situation | Through `MockHermes` (direct hook call) | Through the HTTP wire (`create_router`) |
|---|---|---|
| `cancel()` for a session the harness never saw | the harness is asked anyway → the base `on_cancel` returns `True` | `404 {"detail":"Session not found"}` whenever the harness implements `get_session_info` and returns `None` for the id (`test_5_9b cancel_unknown_session`); a harness without that hook does reach `on_cancel` |
| `on_process` (or `on_result`) raises | the exception propagates to your test | caught by the router: HTTP **200** with `{"decision":"end","end":{"reason":"error","summary":"<exception>"}}` (`test_handler_crash` pins this as the contract) |
| `harness.health().active_sessions` after one round trip | `0` — `MockHermes` never calls the router's `_track_session`, so the router's tracking stays empty | `1` — `POST /v1/process` tracks the session as active, and `GET /v1/health` counts that tracking |
| A request missing `identity` / `context.config` | not possible — `MockHermes` builds a valid request | `422` from Pydantic validation before the harness is called |

Both paths run the same harness state: a session recorded inside `on_process`
is equally visible to your own `get_session_info` in either mode. Only the
router-side tracking (`_live_sessions`, which `GET /v1/health` and the
`GET /v1/sessions/{id}` fallback read) is exclusive to the wire.

---

## Example: request/response round trip (pytest)

Runnable verbatim: as a test (`pytest this_file.py`) or as a plain script
(`uv run python this_file.py`). It is written against the shipped
`EchoHarness`.

```python
import asyncio

import pytest
from h3_harness import DecisionType, EndReason, ResultPayload, ResultType
from h3_harness.examples.echo import EchoHarness
from h3_harness.testbed import MockHermes


@pytest.mark.asyncio
async def test_echo_round_trip() -> None:
    mock = MockHermes(EchoHarness())

    # process: message in → Decision out
    decision = await mock.send_message("Hello!")
    assert decision.decision == DecisionType.TEXT
    assert decision.text.content == "Echo: Hello!"
    assert decision.text.finished is True

    # result: the outcome of the previous decision → the harness's next
    # Decision. EchoHarness treats a FINISHED exchange as complete, so
    # on_result answers END/TASK_COMPLETE — not another text decision.
    result = ResultPayload(
        type=ResultType.TEXT_SENT,
        success=True,
        data={"content": "Echo: Hello!"},
    )
    next_decision = await mock.send_result(result, decision_id=decision.decision_id)
    assert next_decision.decision == DecisionType.END
    assert next_decision.end.reason == EndReason.TASK_COMPLETE

    # cancel: interrupt → harness confirms
    assert await mock.cancel() is True


if __name__ == "__main__":
    asyncio.run(test_echo_round_trip())
```

The example above also demonstrates the agent-loop round trip: `send_message`
drives `on_process`, `send_result` drives `on_result`, and `cancel` drives
`on_cancel` — the three abstract/optional hooks a harness implements.

Two notes on reading the outcome:

- a harness that keeps streaming (e.g. `EchoHarness` on a message containing
  "do not finish") answers `send_result` with another `TEXT` decision instead
  of `END` — the decision type is the harness's call, not the testbed's.
- `send_result` needs a `decision_id`; pass the one from the previous
  `Decision` (`decision.decision_id`) so the harness can correlate the result,
  or let `MockHermes` generate one when your harness ignores it.
