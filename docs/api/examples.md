# `h3_harness.examples` — Shipped Examples

Three runnable harness examples ship inside the package under
`src/h3_harness/examples/`. Each defines a `BaseHarness` subclass, exposes a
module-level `app`, and, when run as a script, boots a uvicorn server with
the router and logging middleware attached. Default ports (what each example
binds when run as a script):

- `echo.py` → **9191** (the h3-test battery port — `h3-test --endpoint
  http://localhost:9191` works against it out of the box; an optional argv
  argument overrides it, e.g. `python echo.py 8000`)
- `minimal.py` → **8000**
- `langchain_agent.py` → **8000**

| File | Harness class | Demonstrates |
|---|---|---|
| [echo.py](../../src/h3_harness/examples/echo.py) | `EchoHarness` | Full H3-compliant harness: session tracking, streaming detection, history echo. The battery-ready template (46/46 on h3-test). |
| [minimal.py](../../src/h3_harness/examples/minimal.py) | `MinimalHarness` | The smallest runnable harness — a starting template. |
| [langchain_agent.py](../../src/h3_harness/examples/langchain_agent.py) | `LangChainHarness` | The LLM-call agent loop: `llm_call` → result → `text` → `end`. |

---

## `echo.py` — `EchoHarness`

Echoes back whatever the user sends. The canonical, battery-ready template
(implements all three h3-test conventions):

- **History echo** — `on_process` copies `req.context.history` into the
  returned `Decision(history=...)`.
- **Streaming detection** — a message containing `"do not finish"` produces
  `TextResponse(finished=False)`; anything else finishes.
- **Session tracking** — keeps `self._sessions: dict[str, dict]` keyed by
  session ID with `started_at` and `turn_count`, and implements
  `get_session_info(session_id) -> dict | None` so the router's
  `GET /v1/sessions/{session_id}` returns real metadata.
- `on_result` replies `"Result received: <decision_id>"` with a text Decision,
  still respecting the per-session streaming flag.

## `minimal.py` — `MinimalHarness`

Bare-bones subclass with no real logic: `on_process` always replies with
`TextResponse(content="Hello from minimal!", finished=True)` and `on_result`
always ends the session (`End(reason="task_complete")`). Use as a starting
template.

## `langchain_agent.py` — `LangChainHarness`

Demonstrates the LLM-call decision loop (the example is self-contained and
does not import langchain — the model is hardcoded; it shows the protocol
pattern for delegating reasoning to an external LLM pipeline):

1. `on_process` → returns `Decision(decision=DecisionType.LLM_CALL,
   llm_call=LLMCall(model="gpt-4o-mini", messages=[...], system_prompt=...,
   temperature=0.7, max_tokens=1024))`, building the message list from the
   incoming `Message` plus `req.context.history`.
2. `on_result` with `result.type == "llm_response"` → returns a
   `DecisionType.TEXT` Decision with the LLM's reply
   (`finished=True`), extracted from `result.data["content"]`
   (fallback: `"(no response from LLM)"`).
3. `on_result` with `result.type == "text_sent"` (or anything else) → returns
   `DecisionType.END` (`End(reason="task_complete")`) to finish the session.

Run it with `python src/h3_harness/examples/langchain_agent.py`.
