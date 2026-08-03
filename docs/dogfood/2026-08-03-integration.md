# H3 Python SDK — Integration Report (2026-08-03)

**Dogfood run:** field-test of `h3-harness-sdk` 0.1.0 as a real consumer.
**Verdict:** 🟡 PROMISING-BUT-ROUGH — protocol engine is genuinely good; the
install path is broken and one shipped example crashes.

---

## 1. What I built

A todo-list assistant harness ("TodoBrain") — NOT an echo — exercising the full
decision surface a real agent needs: `TOOL_CALL`, `LLM_CALL`, `TEXT`, `END`,
session tracking, streaming flag. Built in `/tmp/dogfood-h3-sdk/consumer/`
against the public SDK surface only (`from h3_harness import ...`).

```python
from fastapi import FastAPI
from h3_harness import (
    BaseHarness,
    Decision,
    DecisionType,
    End,
    LLMCall,
    TextResponse,
    ToolCall,
    add_middleware,
    create_router,
)


class TodoBrain(BaseHarness):
    def __init__(self):
        super().__init__()
        self._todos: dict[str, list[str]] = {}
        self._sessions: dict[str, dict] = {}

    async def on_process(self, req) -> Decision:
        sid = req.session_id
        self._sessions[sid] = {
            "started_at": __import__("time").time(),
            "turn_count": self._sessions.get(sid, {}).get("turn_count", 0) + 1,
        }
        content = req.message.content.strip().lower()
        history = list(req.context.history)  # battery convention #1
        streaming = "do not finish" in content  # battery convention #3
        finished = not streaming

        if content.startswith("add "):
            task = req.message.content[4:].strip()
            return Decision(
                decision=DecisionType.TOOL_CALL,
                tool_call=ToolCall(
                    name="todo_add", params={"session_id": sid, "task": task}
                ),
                history=history,
            )
        if content in ("list", "ls"):
            todos = self._todos.get(sid, [])
            body = "\n".join(f"- {t}" for t in todos) if todos else "(empty)"
            return Decision(
                decision=DecisionType.TEXT,
                text=TextResponse(content=f"Your todos:\n{body}", finished=finished),
                history=history,
            )
        if not req.context.models:  # battery convention #2
            return Decision(
                decision=DecisionType.TEXT,
                text=TextResponse(
                    content="No models available — try 'add X' or 'list'.",
                    finished=finished,
                ),
                history=history,
            )
        return Decision(
            decision=DecisionType.LLM_CALL,
            llm_call=LLMCall(
                model=req.context.models[0].name,
                messages=[{"role": "user", "content": req.message.content}],
                max_tokens=128,
            ),
            history=history,
        )

    async def on_result(self, req) -> Decision:
        result = req.result or {}  # req.result is a DICT — use .get()
        if result.get("type") == "tool_result":
            data = result.get("data") or {}
            if data.get("tool_name") == "todo_add":
                self._todos.setdefault(req.session_id, []).append(
                    data.get("params", {}).get("task", "?")
                )
                return Decision(
                    decision=DecisionType.TEXT,
                    text=TextResponse(
                        content=f"Added (now {len(self._todos[req.session_id])} todos)",
                        finished=True,
                    ),
                )
        if result.get("type") == "llm_response":
            return Decision(
                decision=DecisionType.TEXT,
                text=TextResponse(
                    content=(result.get("data") or {}).get("content") or "(no reply)",
                    finished=True,
                ),
            )
        if result.get("type") == "text_sent":
            return Decision(decision=DecisionType.END, end=End(reason="task_complete"))
        return Decision(
            decision=DecisionType.END, end=End(reason="task_complete", summary="done")
        )

    def get_session_info(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)


app = FastAPI()
app.include_router(create_router(TodoBrain()))
add_middleware(app)  # request logging
```

Full runnable version (with uvicorn runner): see the dogfood run's consumer at
`/tmp/dogfood-h3-sdk/consumer/todobrain_v2.py`.

## 2. The install saga (a real user's Friday afternoon)

| Step | Command | Result |
|---|---|---|
| 1 | `pip install h3-harness-sdk` | ❌ `No matching distribution found` — **not on PyPI** (DF-002) |
| 2 | `pip install /path/to/sdk-python` | ✅ installs… but `from h3_harness import BaseHarness` → **ImportError** — wheel has no `__init__.py` (DF-001) |
| 3 | `pip install -e /path/to/sdk-python` | ✅ works — this is the ONLY working path today |

**Time-to-first-success:** ~20 min (mostly diagnosing steps 1–2).

## 3. What worked (the good news)

Once installed editable, everything the SDK promises works:

- README quickstart import + Testbed (`MockHermes`) quickstart — ✅
- `GET /v1/health` — 200, capabilities list, protocol_version 1.0 ✅
- Full Hermes loop over HTTP: `process → tool_call → result(tool_result) → text → process → llm_call → result(llm_response) → text → result(text_sent) → end(task_complete)` — ✅ flawlessly
- Session endpoints: GET known session → 200 with turn_count; unknown → 404; DELETE → 200; POST cancel → 200 ✅
- Validation: malformed body → 422 with clear pydantic detail ✅
- **Official `h3-test` battery: 43/43 PASSED** (0.33s, p50 1.43ms) with the TodoBrain harness ✅
- Stress: 50 rapid calls, 10 concurrent sessions, memory flat — all ✅

The decision/result loop is clean, fast, and the router's error containment
(exceptions → `end(reason=error)`) means a crashing harness never 500s.

## 4. Friction points (→ board tasks)

1. **P0 DF-001 — wheel ships without `__init__.py`.** Root cause: `.gitignore`
   line `_*.py` ("temp audit scripts") matches `__init__.py` in any directory,
   and hatchling applies gitignore patterns to wheel file selection. Verified:
   building from a clean dir without that pattern includes the files; anchoring
   to `/_*.py` fixes the wheel. **Add a CI check that the wheel contains
   `h3_harness/__init__.py`.**
2. **P0 DF-002 — not on PyPI.** README/AGENTS install command dead for every
   real user. Publish (after DF-001) or document the fallback.
3. **P1 DF-003 — `examples/langchain_agent.py` crashes on first message:**
   `LLMCall.messages` is `list[dict]`, example passes `LLMMessage` objects →
   ValidationError → router silently answers `{"decision":"end","reason":"error"}`.
   Also `req.result.type` on a dict. Fix: dicts + `.get()`.
4. **P2 DF-004 — three battery conventions are undocumented** (history echo,
   `context.models` guard before LLM_CALL, "do not finish" → `finished=false`).
   Doc-following user scores 41/43 and must read `shim/src/h3_shim/test_battery.py`
   to find them. My journey: 41 → 42 → 43 as I discovered each.
5. **P2 DF-005 — `SessionResponse.started_at/last_active` always `""`** even
   when `get_session_info` supplies them.

## 5. How to run the acceptance gate

```bash
# install shim test battery (from get-h3/shim)
pip install hermes-h3-shim        # or use an existing h3-test binary

# run your harness
uvicorn my_harness:app --port 9191

# THE GATE — exit code 0 = compliant
h3-test --endpoint http://127.0.0.1:9191
```

## 6. Verdict

**PROMISING-BUT-ROUGH.** The SDK's protocol engine is genuinely good — a real
consumer harness hit 43/43 on the first battery-correct pass and the loop is a
pleasure to drive. But "install and go" is currently fiction: two P0s block the
documented path, and the flagship non-echo example crashes. Fix DF-001 + DF-002
and this is shippable.
