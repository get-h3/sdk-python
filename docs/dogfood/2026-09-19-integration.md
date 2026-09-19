# Dogfood Integration — 2026-09-19 — h3-harness-sdk (PyPI 0.1.5 @ HEAD a7be001)

**Verdict: SHIPPABLE (4th consecutive: 08-23, 09-01, 09-04, 09-19).**
Install-from-scratch proven on an ephemeral bunker; a real consumer harness
worked end-to-end, but only after three doc-driven dead ends that a fresh
user cannot avoid today.

## Promise under test

"A developer can build an H3-compliant agent harness by installing
`h3-harness-sdk` and following the README quickstart: subclass `BaseHarness`,
implement `on_process`/`on_result`, mount `create_router`, serve with uvicorn."

## What was built (real consumer, outside the repo)

A todo-note harness (`/tmp/dogfood-h3sdk-0919/todo_harness.py`): per-session
todo list persisted to JSON, text replies, one tool_call round trip
(harness PROPOSES `add_todo`, caller executes, posts the result, harness
applies it), session tracking so cancel/GET 404 on unknown ids.

Time-to-first-200: ~18 min (fresh venv 6s pip; the rest was request-shape
discovery). Friction count: 7 (3 422 rounds, 1 flat-vs-nested response shape
miss, 1 ToolCall kwarg guess, 1 raw-dict result surprise, 1 tool-execution
semantics realization).

## The working round trip (verified live)

```bash
# 1. propose-a-tool turn
curl -s -X POST :9191/v1/process -H 'Content-Type: application/json' -d '{
  "session_id": "s1",
  "identity": {"user_id": "u", "chat_id": "c", "platform": "cli"},
  "message": {"content": "remind me to call the dentist", "role": "user"},
  "context": {"config": {}, "session_state": {}, "history": []}}'
# -> {"decision":"tool_call","decision_id":"...","tool_call":{"name":"add_todo","params":{...}}}
```

```python
# 2. harness side: propose, never execute
return Decision(decision=DecisionType.TOOL_CALL,
                tool_call=ToolCall(name="add_todo",
                                   params={"item": msg},
                                   reasoning="user asked"),
                history=list(req.context.history))
```

```bash
# 3. caller executes, posts the result; harness applies state in on_result
curl -s -X POST :9191/v1/result -H 'Content-Type: application/json' -d '{
  "session_id": "s1", "decision_id": "<decision_id from step 1>",
  "result": {"type": "tool", "success": true, "tool_name": "add_todo",
             "data": {"output": "added #1: call the dentist"}}}'
```

## Errors hit and fixes (the part the docs should say)

| What happened | Why | The right way |
|---|---|---|
| 422 `identity Field required`, then `identity.chat_id/platform` | ProcessRequest requires a full Identity | Always send `{user_id, chat_id, platform}` |
| 422 `context.config`, `context.session_state` | Context requires both, even when empty | `context: {"config": {}, "session_state": {}, "history": []}` |
| Nested response assumed (`decision.text`) | Wire is FLAT: `decision` is a string discriminator; fields sit at top level | Read `resp["text"]["content"]`, not `resp["decision"]["text"]` |
| `ToolCall(arguments=..., call_id=...)` ValidationError | Fields are `name / params / reasoning` | `params` carries the arguments; no call_id exists |
| Error arrives as HTTP 200 `end(error)` | Router masks harness exceptions (battery design) | Read `end.summary`; the traceback is also in server logs |
| `req.result.data` AttributeError | `ResultRequest.result` is a raw dict on the wire; the exported `ResultPayload` model is not applied | Use `req.result.get("data", {})` |
| Todos never appeared from on_process | H3 semantics: the harness never executes tools | Apply tool effects in `on_result` after the caller posts success |

## Persistence / restart probe

Todos written to disk on apply; after killing uvicorn and restarting, the
same session returned `Todos: #1 added #1: call the dentist`. Session
tracking resets on restart (turn_count 1, fresh started_at) — expected for
an in-memory harness, worth knowing when you embed state.

## Verdict rationale

Works: yes (full loop, 404s on ghost sessions, persistence across restart).
Useful: yes — one-file FastAPI harness with battery-compliant defaults is a
real 80/20. Usable: the happy path (echo) is 5 minutes, but the moment you
want tool-calls you are reverse-engineering the wire — three docs gaps filed
as GAP-064/065/066. Trustworthy: errors are masked but never lost; no data
corruption observed.
