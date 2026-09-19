# Integration Guide — from `pip install` to a battery-passing H3 harness

This guide takes you from nothing to a running H3 harness that passes the
compliance battery (`h3-test`, **46 tests across 6 categories**). Every command
and response below was run against `h3-harness-sdk` **0.1.5**; the harness in
[step 3](#3-write-your-first-harness) is the exact file that produced the
transcripts — it scores **46/46 PASSED** (`h3-test` exit code `0`).

For the full field-by-field surface, see the [API Reference](api-reference.md).

- [1. Prerequisites](#1-prerequisites)
- [2. Install](#2-install)
- [3. Write your first harness](#3-write-your-first-harness)
- [4. Smoke test it with curl](#4-smoke-test-it-with-curl)
- [5. Run the compliance battery](#5-run-the-compliance-battery)
- [6. Reach a battery-passing harness in <15 minutes](#6-reach-a-battery-passing-harness-in-15-minutes)
- [7. Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

| Requirement | Why |
|---|---|
| Python **3.10+** (`requires-python = ">=3.10"`) | SDK runtime. |
| `fastapi>=0.109`, `pydantic>=2.0`, `uvicorn[standard]>=0.25` | Installed automatically as SDK dependencies. |
| `pip` + `git` | The compliance battery (`h3-test`) ships in `get-h3/shim`, which is not on PyPI — it installs from git. |
| A free TCP port (the examples use **9191**) | `h3-test --endpoint http://localhost:9191` needs a listener. |

Nothing here needs Hermes Core, an LLM key, or network access beyond the two
`pip install` commands.

---

## 2. Install

```bash
pip install h3-harness-sdk
```

Verify:

```bash
python -c "import h3_harness; print(h3_harness.__version__)"
# 0.1.5
```

### Install fallback (git / source)

Use this when a release isn't on PyPI yet or you want unreleased changes:

```bash
# From git
pip install git+https://github.com/get-h3/sdk-python.git

# Editable source install (development)
git clone https://github.com/get-h3/sdk-python.git
cd sdk-python
pip install -e ".[dev]"
```

On a minimal container with no system `pip`, bootstrap a venv first:
`python3 -m venv .venv && .venv/bin/pip install h3-harness-sdk` (the repo also
has a one-command equivalent, `make install`).

The version you just printed is the single source of truth
(`src/h3_harness/_version.py`) — it is also what `GET /v1/health` reports as
`version`. Any doc quoting a different version is stale.

---

## 3. Write your first harness

Save this as `my_harness.py`. It is the README Quickstart harness with the
session-terminate cleanup added — a complete, runnable, battery-compliant
harness:

```python
"""My first H3 harness — a battery-compliant echo harness."""

from datetime import datetime, timezone

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
    def __init__(self) -> None:
        # Track sessions so cancel/session lookups 404 on unknown ids
        # (battery: test_5_9b cancel_unknown_session, test_5_10 session_not_found).
        super().__init__()
        self._sessions: dict[str, dict] = {}

    async def on_process(self, req):
        sid = req.session_id
        now = datetime.now(timezone.utc).isoformat()
        # Streaming: "do not finish" in message -> unfinished text
        # (battery: test_2_4_process_text_finished_false).
        streaming = "do not finish" in req.message.content
        self._sessions[sid] = {
            "started_at": self._sessions.get(sid, {}).get("started_at", now),
            "last_active": now,
            "turn_count": self._sessions.get(sid, {}).get("turn_count", 0) + 1,
            "status": "active",
        }
        # Echo conversation history from context (battery: test_2_8).
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(
                content=f"Echo: {req.message.content}",
                finished=not streaming,
            ),
            history=list(req.context.history),
        )

    async def on_result(self, req):
        # ResultRequest has no `context` field -- never touch req.context here.
        self._sessions.setdefault(req.session_id, {})["status"] = "completed"
        return Decision(decision=DecisionType.END, end=End(reason="task_complete"))

    def get_session_info(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    async def on_session_terminate(self, session_id: str) -> None:
        # DELETE /v1/sessions/{id} -> forget the session so a later GET 404s.
        self._sessions.pop(session_id, None)


app = FastAPI()
app.include_router(create_router(MyHarness()))
```

What each piece is for:

- `on_process` / `on_result` are the **only required methods** (`BaseHarness` is
  an ABC — it cannot be instantiated without them).
- `get_session_info` is **not** on the ABC, but the router duck-types it: with
  it, unknown session ids 404 on `cancel` / `GET` / `DELETE`; without it every
  session id looks valid and `GET` always reports `active`.
- `on_session_terminate` is optional (base = no-op). Override it or a
  terminated session stays retrievable.
- `history=list(req.context.history)` and `finished=not streaming` are the two
  battery conventions that live inside `on_process` (conventions 1 and 3 of the
  README's *Passing the battery* list).

The `if __name__ == "__main__"` runner is optional — the module-level `app` is
enough for uvicorn.

### Run it

```bash
uvicorn my_harness:app --port 9191
# Uvicorn running on http://127.0.0.1:9191
```

Add `--host 0.0.0.0` to accept connections from outside the container/host, and
`--reload` while iterating. If you prefer a self-contained file, append:

```python
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9191)
```

then `python my_harness.py`.

---

## 4. Smoke test it with curl

With the server running, the five calls below are the whole protocol. Health
first — note the path is **`/v1/health`**, not `/health`:

```bash
curl http://localhost:9191/v1/health
```

```json
{"status":"ok","version":"0.1.5","active_sessions":0,"capabilities":["tool_call","llm_call","text","wait","delegate","end"],"degraded_reason":null,"error":null,"protocol_version":"1.0","transport":"rest","uptime_seconds":5}
```

### Send a message: `POST /v1/process`

The payload must carry `session_id`, `identity`, `message`, and a `context`
containing at least `config` and `session_state` — omit `context` (or either of
those two sub-objects) and FastAPI rejects the call with `422` before your code
runs.

```bash
curl -X POST http://localhost:9191/v1/process \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "sess-001",
    "identity": {"chat_id": "chat-1", "platform": "cli", "user_name": "dev"},
    "message": {"content": "Hello, harness!"},
    "context": {
      "config": {"max_iterations": 10, "timeout_seconds": 300},
      "session_state": {"turn_count": 0, "cost_so_far": 0.0},
      "history": [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"}
      ]
    }
  }'
```

```json
{"decision":"text","decision_id":"6e0f92e4-4919-4a7a-b739-927a546e375a","history":[{"content":"hi","role":"user"},{"content":"hello","role":"assistant"}],"text":{"content":"Echo: Hello, harness!","finished":true}}
```

Three things to read out of that response: `decision` (`"text"`), the
`decision_id` (a fresh UUID4, auto-generated by pydantic), and `history` — the
request's history coming straight back, which is what the battery asserts.

### Chain `decision_id` into `POST /v1/result`

This is the part that is easy to get wrong and hard to find in the README: the
`decision_id` returned by `/v1/process` **is the id Hermes sends back** on
`/v1/result`, and it is how your `on_result` knows which decision the result
belongs to. Capture it from the response instead of typing it by hand:

```bash
# 1. Ask for a decision and capture its id.
DID=$(curl -s -X POST http://localhost:9191/v1/process \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "sess-002",
    "identity": {"chat_id": "chat-1", "platform": "cli"},
    "message": {"content": "Hello, harness!"},
    "context": {"config": {}, "session_state": {}, "history": []}
  }' | python3 -c 'import sys, json; print(json.load(sys.stdin)["decision_id"])')

echo "captured decision_id=$DID"
# captured decision_id=9d7f48a7-f22a-4ab0-b450-5545d41a427e

# 2. Send the execution result for THAT decision back to the harness.
curl -X POST http://localhost:9191/v1/result \
  -H 'Content-Type: application/json' \
  -d "{
    \"session_id\": \"sess-002\",
    \"decision_id\": \"$DID\",
    \"result\": {\"type\": \"text_sent\", \"success\": true, \"data\": {\"delivered\": true}}
  }"
```

```json
{"decision":"end","decision_id":"7fff792b-5c95-4f81-8b43-fe6fc5e739da","history":[],"end":{"reason":"task_complete"}}
```

The harness replies with the *next* decision — here an `end`
(`reason: "task_complete"`) that closes the session. Note the second
`decision_id` is a **new** id: every Decision gets its own, and the one you sent
is what the harness reads as `req.decision_id`. `result` is a plain dict (the
canonical shape is `ResultPayload`: `type`, `success`, plus optional
`tool_name`/`data`/`duration_ms`) — read it with `.get()`, never attribute
access.

Two contract details worth knowing before you write real logic:

- `ResultRequest` has **no `context` field** — do not try to echo
  `req.context.history` from `on_result` (it raises `AttributeError`, which the
  router masks as a 200 `end/error`; the session just dies).
- `result["tool_calls"]` is a **list** of dicts, one per call — never a single
  dict.

### Cancel, and inspect the session

```bash
# Cancel an in-flight operation (the harness confirms with true).
curl -X POST http://localhost:9191/v1/cancel \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "sess-001", "reason": "user_interrupt"}'
# {"session_id":"sess-001","cancelled":true}

# Cancel an unknown session -> 404, because the harness tracks sessions.
curl -s -w ' HTTP %{http_code}' -X POST http://localhost:9191/v1/cancel \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "nope", "reason": "user_interrupt"}'
# {"detail":"Session not found"} HTTP 404

# Session metadata comes from your get_session_info() dict.
curl http://localhost:9191/v1/sessions/sess-001
# {"last_active":"2026-09-18T09:06:47.676588+00:00","session_id":"sess-001","started_at":"2026-09-18T09:06:47.676588+00:00","status":"active","turn_count":1,"current_decision":null,"current_decision_type":null}

# Terminate: the hook drops the session, so a later GET 404s.
curl -X DELETE http://localhost:9191/v1/sessions/sess-001
# {"session_id":"sess-001","terminated":true}

curl -s -w ' HTTP %{http_code}' http://localhost:9191/v1/sessions/sess-001
# {"detail":"Session not found"} HTTP 404
```

That last pair is the `on_session_terminate` override earning its keep: without
it, DELETE still returns `{"terminated": true}` but the session remains fully
retrievable.

---

## 5. Run the compliance battery

`h3-test` is the gate: it speaks the H3 protocol to **any** endpoint and asserts
the contract. It ships in [get-h3/shim](https://github.com/get-h3/shim), which
is not on PyPI — install from git:

```bash
pip install git+https://github.com/get-h3/shim
```

Then, with your harness running:

```bash
h3-test --endpoint http://localhost:9191
```

Real output for the harness in [step 3](#3-write-your-first-harness):

```
H3 Compliance Test Battery v0.1.0
Target: http://localhost:9191
Transport: REST

  Health & Protocol                   7/7  ✅ PASSED
  Process Basic Flows                 8/8  ✅ PASSED
  Decision Types                      6/6  ✅ PASSED
  Result Handling                     7/7  ✅ PASSED
  Error & Edge Cases                 13/13  ✅ PASSED
  Stress & Performance                5/5  ✅ PASSED
  TOTAL                               46/46  PASSED
  Duration                            0.39s
  Latency p50/p95                     2.00ms / 55.46ms
```

**The battery is 46 tests across 6 categories** (health/process/decisions/
results/errors/stress groups as shown above). If you see a different number in
an older doc, that doc is stale — trust the `TOTAL` line you just printed.

### Exit codes

`h3-test` distinguishes "your harness is broken" from "you pointed it at the
wrong thing", which matters in CI:

| Exit code | Meaning |
|---|---|
| `0` | **Compliant** — target is an H3 endpoint and every check passed. |
| `1` | **Compliance failure** — target is a real H3 endpoint but some protocol checks failed. Fix the harness. |
| `2` | **Not an H3 endpoint** — connection refused, non-JSON body, HTTP ≥ 400, or `/v1/health` missing required H3 fields. Check the URL / that the server is running. |

Measured examples on this SDK: the step-3 harness → `TOTAL 46/46 PASSED`,
exit `0`; a deliberately naive harness (no history echo, no session tracking, no
streaming flag) → `TOTAL 40/46 FAILED`, exit `1`; the same command against a
dead port → exit `2` with `Warning: … does not look like an H3 endpoint
(connection error)`.

Useful flags: `--json` (machine-readable report), `--categories
health,process` (run a subset), `--help` (full exit-code text).

---

## 6. Reach a battery-passing harness in <15 minutes

1. `pip install h3-harness-sdk` and confirm `h3_harness.__version__` → `0.1.5`.
   *(1 min)*
2. Save the step-3 `my_harness.py`. *(2 min)*
3. `uvicorn my_harness:app --port 9191`, then
   `curl http://localhost:9191/v1/health` → `{"status":"ok", …}`. *(2 min)*
4. `curl -X POST http://localhost:9191/v1/process` with the step-4 payload and
   confirm you get a `decision` + `decision_id` back (not a `422`). *(2 min)*
5. Chain it: capture `decision_id` from that response and `POST /v1/result` —
   confirm `decision: "end"`. *(2 min)*
6. `pip install git+https://github.com/get-h3/shim`, then
   `h3-test --endpoint http://localhost:9191`. Exit `0` = done. *(1 min)*
7. If any check fails, keep these four conventions intact — they are what the
   battery actually asserts:
   - [ ] `get_session_info` returning `None` for unknown ids (404s on
         cancel/GET),
   - [ ] `history=list(req.context.history)` on every `on_process` Decision,
   - [ ] `text.finished=False` when the message says "do not finish",
   - [ ] never return `llm_call` when `context.models` is empty.

`src/h3_harness/examples/echo.py` (`EchoHarness`) is the canonical template if
you want to diff your harness against a known 46/46 implementation:
`python -m h3_harness.examples.echo 9191`.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `422` with `{"loc": ["body", "context"], "msg": "Field required"}` | Missing `context` | Send `context.config` **and** `context.session_state` (both required; `history`/`models`/`tools` default to `[]`). |
| `404` on every `GET /v1/sessions/{id}` | No `get_session_info`... | ...or the session id was never seen by `on_process`. Implement `get_session_info` and key it on `req.session_id`. |
| `{"detail":"Session not found"}` on `DELETE` | You deleted it, or the id is unknown | Expected for tracked harnesses; check the id. |
| Session returns `{"status":"active"}` forever | No `get_session_info` | The router has no session store without it and always reports `active`. |
| The session just stops, HTTP 200, `{"decision":"end","end":{"reason":"error"}}` | Your `on_process`/`on_result` raised | Handler exceptions are masked as a *successful* `end/error` decision (the router logs `on_process failed`). Check the server log; `end.reason == "error"` is the only wire signal. |
| `AttributeError: 'ResultRequest' object has no attribute 'context'` | Reading `req.context` in `on_result` | `ResultRequest` has only `decision_id`/`result`/`session_id`; omit `history` from `on_result` decisions. |
| `406`/404 on `/health` | Endpoint is `/v1/health` | Use the `/v1/` prefix (or whatever `prefix=` you passed to `create_router`). |
| Port already in use | Another harness/server on 9191 | `ss -tlnp \| grep 9191`, stop it or pick another port, and pass the same port to `h3-test --endpoint`. |
| `h3-test` exits `2` | Wrong URL, or the harness isn't running | `curl <endpoint>/v1/health` — a non-H3 body or a connection error gives exit `2`, not a compliance failure. |

---

## See also

| Doc | Covers |
|---|---|
| [API Reference](api-reference.md) | Every endpoint, request/response model, field table and error case. |
| [api/index.md](api/index.md) | Map of the hand-written reference pages. |
| [api/harness.md](api/harness.md) | `BaseHarness` ABC + `create_router` semantics. |
| [api/testbed.md](api/testbed.md) | `MockHermes` — test a harness in-process, no server. |
| [api/examples.md](api/examples.md) | The three shipped examples. |
| [README](../README.md) | Install, quickstart, battery conventions, error handling. |
