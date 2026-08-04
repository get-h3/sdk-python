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
    async def on_process(self, req):
        # Echo conversation history from context (battery: history preserved).
        history = list(req.context.history)
        # Streaming: "do not finish" in message -> unfinished text.
        streaming = "do not finish" in req.message.content
        finished = not streaming
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


app = FastAPI()
app.include_router(create_router(MyHarness()))
```

## Testbed

```python
from h3_harness.testbed import MockHermes
from h3_harness.examples.echo import EchoHarness

mock = MockHermes(EchoHarness())
decision = await mock.send_message("Hello!")
assert decision.text.content == "Echo: Hello!"
```

## Examples

- **[echo.py](src/h3_harness/examples/echo.py)** — Echo harness that mirrors user messages
- **[minimal.py](src/h3_harness/examples/minimal.py)** — Minimal harness with health endpoint, uvicorn runner
- **[langchain_agent.py](src/h3_harness/examples/langchain_agent.py)** — LangChain integration: LLM call with text response

## Passing the battery (h3-test compliance)

The gate for any H3 harness is the **test battery** (`test_battery.py` from
[get-h3/shim](https://github.com/get-h3/shim) — 43 tests across 6 categories).
Run it against any running harness endpoint:

```bash
pip install hermes-h3-shim
h3-test --endpoint http://localhost:9191   # exit 0 = compliant
```

The Quickstart harness above implements all three conventions and is fully
battery-compliant (**43/43**). If you modify it, keep the conventions intact —
a naive harness that drops them scores **41/43**. The three conventions the
battery checks (beyond "return a Decision") are:

1. **Echo `context.history` in every Decision.** The battery sends a session
   with prior history and asserts it flows back through the response
   (`test_2_8_process_preserves_history`). Pass it through explicitly:
   ```python
   history = list(req.context.history)
   return Decision(..., history=history)
   ```
2. **Never issue `llm_call` when `context.models` is empty.** The battery
   sends `context.models: []` and FAILS any harness that returns an `llm_call`
   decision (`test_5_8_no_models_available` — "hallucinated model"). Only
   return `LLM_CALL` when the request actually lists models.
3. **Return `text.finished=false` for "do not finish" prompts.** The battery
   sends *"Just start a thought, do not finish it yet."* and asserts the
   response has `text.finished == False` (`test_2_4_process_text_finished_false`).
   Detect streaming/unfinished intent and set `finished` accordingly.

The canonical battery-ready template is **[echo.py](src/h3_harness/examples/echo.py)**
— it implements all three conventions and scores 43/43. Use it as the starting
point for your own harness.

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
