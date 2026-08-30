# Dogfood Integration Report — 2026-08-23

**Project:** get-h3/sdk-python (h3-harness-sdk)
**Verdict:** 🟡 PROMISING-BUT-ROUGH — core promise HOLDS on the released artifact;
the published wheel is content-stale for exactly one fix (GAP-035).
**Run:** coding-hermes-dogfood cron, 2026-08-23. Fresh user journey, published
package only (PyPI 0.1.3). Scratch: `/tmp/dogfood-h3sdk-0823/`.

---

## 1. Promise (null hypothesis)

> "A Python developer can `pip install h3-harness-sdk` (PyPI), subclass
> `BaseHarness`, mount `create_router()` on FastAPI, run uvicorn, and ship an
> H3-compliant harness that passes the 45-test h3-test battery."

H3 = "Hermes Harness Hooks": the SDK builds the *body* — a harness that Hermes
Core drives over HTTP as its thinking *brain* (brain-swap protocol; see
get-h3 umbrella AGENTS.md).

## 2. What I built and how it went

### 2.1 Install (documented path) — ✅ 0 friction

```bash
python3 -m venv venv && ./venv/bin/pip install h3-harness-sdk
# → 0.1.3 installed (2s), `import h3_harness` OK, __version__ == "0.1.3"
```

### 2.2 Verbatim README quickstart — ✅ 0 friction

Extracted the README quickstart code block byte-for-byte to
`quickstart_harness.py`, ran `uvicorn quickstart_harness:app --port 9193`.
Probed the whole HTTP surface:

| Probe | Result |
|---|---|
| `GET /v1/health` | `{"status":"ok","version":"0.1.3","uptime_seconds":0,...}` ✅ (GAP-025/029 hold on the wheel) |
| `DELETE /v1/sessions/nope-123` | **404** `{"detail":"Session not found"}` ✅ (GAP-019 holds) |
| `GET /v1/sessions/nope-123` | 404 ✅ |
| `POST /v1/cancel` unknown session | 404 ✅ |
| `POST /v1/process` "Hello world" | `decision:text`, `content:"Echo: Hello world"`, `finished:true`, history echoed ✅ |
| `POST /v1/process` "…do not finish it yet." | `finished:false` ✅ (battery convention 3) |
| `GET /v1/sessions/s1` after 2 turns | `turn_count:2`, `started_at` ISO-8601 UTC, `status:"active"` ✅ |

### 2.3 Verbatim README Testbed snippet — ✅ 0 friction

Extracted the "## Testbed" block (the `async def main()` + `asyncio.run` version,
GAP-026 fix) → `python testbed_snippet.py` → exit 0, assert passes.

### 2.4 From-scratch harness: TaskBrain — ✅ mostly, 2 findings

Built `taskbrain.py` — a task-manager harness — following ONLY the README
(quickstart + "Passing the battery" + "Error handling" + "Result payloads"):
full loop `process → (llm_call | tool_call) → result → text → end`, session
tracking with `status` transitions, streaming heuristic, models guard,
`tool_calls` list-of-dicts handling (GAP-036 pattern).

- **MockHermes loop** (`drive_loop.py`): all 7 assertions pass — TOOL_CALL
  dispatch, tool_result → TEXT, text round → END, LLM_CALL when
  `models=[Model(...)]` (GAP-032d holds on the wheel), llm-result tool_calls,
  streaming, session info.
- **Live over HTTP** (uvicorn :9194, published 0.1.3): full loop
  `tool_call → text → end` works; malformed body → 422; unknown route → 404.
- **h3-test battery** (installed via the documented from-source fallback
  `pip install git+https://github.com/get-h3/shim` — shim still NOT on PyPI,
  404 verified 2026-08-23):

```
Health & Protocol    7/7   ✅ PASSED
Process Basic Flows  8/8   ✅ PASSED
Decision Types       6/6   ✅ PASSED
Result Handling      7/7   ✅ PASSED
Error & Edge Cases   11/11 ✅ PASSED
Stress & Performance 5/5   ✅ PASSED
TOTAL                45/45 PASSED  (0.26s, p50 0.90ms / p95 35.86ms)
```

**The from-scratch harness passes 45/45 against the PUBLISHED package.** The
promise holds.

### 2.5 The two findings (both live-verified, both surprises)

**F1 — session status can never be "completed" on the published wheel (GAP-043).**
TaskBrain sets `get_session_info()[...]["status"] = "completed"` when the loop
ends. `GET /v1/sessions/tb-3` after a full loop (`end/task_complete` confirmed
in the response) returns `"status":"active"`. MockHermes (in-process, repo
source via editable install? No — same wheel) … actually the drive script shows
`status: completed` because it reads the raw dict, not the router. The wire
says "active". Root cause found by diffing the installed wheel against repo
HEAD:

```diff
--- repo HEAD src/h3_harness/harness.py        +++ installed wheel harness.py
+def _session_status(value): ...                 (absent)
- status=_session_status(info.get("status")),
+ status=SessionStatus.ACTIVE,
```

Timeline: wheel uploaded 08-13T19:18-0500; GAP-035 commit `1098bf1` landed
08-13T19:21-0500 — **3 minutes later, never re-published**. The
`release-readiness` CI job (GAP-032's fix) compares *version numbers* only:
repo 0.1.3 == PyPI 0.1.3 → green while content drifts. This is the GAP-032
"board says COMPLETE, users install the broken artifact" pattern one level
deeper — same-version content drift. GAP-043 filed (P1).

**F2 — DELETE /v1/sessions/{id} terminates nothing (GAP-044).**
`DELETE /v1/sessions/tb-3` → `{"terminated":true}`; immediately after,
`GET /v1/sessions/tb-3` → **200** with `turn_count`/`started_at`/`status`.
The base `on_session_terminate` is a no-op, and neither the README quickstart
nor `examples/echo.py` override it — so every quickstart-following user gets a
wire that promises termination while the session lives on. Battery 45/45 has
no delete-then-get case. GAP-044 filed (P2).

## 3. Friction log (what a new user hits)

1. **Status:"active" forever (F1)** — surfaced while debugging my own harness;
   explained only by diffing the installed wheel vs repo source. "Had to read
   source to proceed" — release-staleness, not docs.
2. **DELETE-then-GET 200 (F2)** — undocumented lifecycle semantics; the base
   no-op is only visible in the method docstring.
3. **Protocol field names not in README** — `Decision`/`ToolCall`/`LLMCall`
   field names (`params` vs `arguments`, `messages: list[dict]`) required a
   peek at `protocol.py`; `docs/api/protocol.md` exists but the README doesn't
   link it inline at the quickstart.
4. **Shim install** — `hermes-h3-shim` still 404s on PyPI; the README's
   from-source fallback (`pip install git+https://github.com/get-h3/shim`)
   works exactly as documented. Not a new gap (GAP-005 closed), just a
   recurring minor.

**Time-to-first-success:** ~2 min (install 30s → import → uvicorn up).
**Full loop incl. battery:** ~15 min.

## 4. What held up (promises kept)

- Install path: PyPI 0.1.3 wheel + sdist, works (GAP-010/013 hold).
- Verbatim quickstart + testbed snippets both runnable (GAP-017/026 hold).
- All four battery conventions documented and working (DF-004/GAP-002 hold).
- 45/45 battery from a from-scratch harness (the compliance story holds).
- Error masking documented (GAP-034) — README "Error handling" section.
- Wheel contains `__init__.py` (DF-001) — verified implicitly by import.

## 5. The working recipe (use this next time)

```bash
python3 -m venv venv && ./venv/bin/pip install h3-harness-sdk
# subclass BaseHarness: on_process (echo history, models guard, do-not-finish
#   → finished=False), on_result (ResultRequest has NO context — omit history),
#   get_session_info (tracked sessions → 404s work), optionally
#   on_session_terminate (pop session state — see GAP-044).
app = FastAPI(); app.include_router(create_router(MyHarness()))
uvicorn my_harness:app --port 9191
./venv/bin/pip install git+https://github.com/get-h3/shim   # battery CLI
./venv/bin/h3-test --endpoint http://localhost:9191          # 45/45 = compliant
```

## 6. Files

- `/tmp/dogfood-h3sdk-0823/quickstart_harness.py` — verbatim README quickstart
- `/tmp/dogfood-h3sdk-0823/testbed_snippet.py` — verbatim README Testbed block
- `/tmp/dogfood-h3sdk-0823/taskbrain.py` — from-scratch tool-calling harness
- `/tmp/dogfood-h3sdk-0823/drive_loop.py` — MockHermes full-loop assertions
- Board: GAP-043 (P1), GAP-044 (P2), GAP-045 (P3) in `.coding-hermes/board/tasks.jsonl`
  + mirror rows in `.coding-hermes/tasks.md`.
