# `h3_harness.testbed` — `MockHermes`

**Module:** `h3_harness.testbed` — import directly:
`from h3_harness.testbed import MockHermes`.

`MockHermes` simulates Hermes Core for testing H3-compliant harnesses without
a running server. It wraps a `BaseHarness` instance and provides convenience
methods that build protocol-correct requests and return the harness's
`Decision` — exactly what the router would produce, minus the HTTP layer.

---

## `MockHermes(harness: BaseHarness)`

Constructor takes the harness instance to drive.

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `harness` | `BaseHarness` | The harness under test (set from the constructor argument). |

### Methods

#### `async send_message(content: str, *, session_id: str = "test-session") -> Decision`

Send a user message to the harness and return its Decision (calls
`harness.on_process`).

The request is built with:

- `Message(content=content, timestamp=<current UTC ISO 8601>)`
- `Identity(platform="test", chat_id="test", user_name="test", user_id="test-user")`
- `Context(config=Config(max_iterations=10, timeout_seconds=300),
  session_state=SessionState(started_at=<current UTC ISO 8601>))` — history,
  models, and tools are empty.

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

---

## Example: request/response round trip (pytest)

```python
import pytest
from h3_harness import DecisionType, ResultPayload, ResultType
from h3_harness.examples.echo import EchoHarness
from h3_harness.testbed import MockHermes


@pytest.mark.asyncio
async def test_echo_round_trip():
    mock = MockHermes(EchoHarness())

    # process: message in → Decision out
    decision = await mock.send_message("Hello!")
    assert decision.decision == DecisionType.TEXT
    assert decision.text.content == "Echo: Hello!"
    assert decision.text.finished is True

    # result: prior decision's outcome → next Decision
    result = ResultPayload(
        type=ResultType.TEXT_SENT,
        success=True,
        data={"content": "Echo: Hello!"},
    )
    next_decision = await mock.send_result(result, decision_id=decision.decision_id)
    assert next_decision.decision == DecisionType.TEXT

    # cancel: interrupt → harness confirms
    assert await mock.cancel() is True
```

The example above also demonstrates the agent-loop round trip: `send_message`
drives `on_process`, `send_result` drives `on_result`, and `cancel` drives
`on_cancel` — the three abstract/optional hooks a harness implements.
