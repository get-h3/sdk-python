# Dogfood Integration Report — 2026-08-13

**Project:** get-h3/sdk-python (`h3-harness-sdk` 0.1.2, PyPI)
**Verdict:** 🟡 PROMISING-BUT-ROUGH — core promise holds end-to-end; published
wheel is stale vs repo HEAD (GAP-032) + two SDK/docs gaps (GAP-033/034).
**Consumer:** `/tmp/dogfood-h3sdk-0813/` (ConvertBrain — a real tool-calling
harness built from scratch by a user who read only the README + API reference).

---

## What we built

**ConvertBrain** — a units-converter agent brain. Real integration, real loop:

```
POST /v1/process  "convert 5 km to miles"   → llm_call (model from context)
POST /v1/result   llm_response (wants tool) → tool_call  convert {value:5,src:km,dst:mi}
POST /v1/result   tool_result               → text       "5 km = 3.106855961186669 mi"
POST /v1/result   text_sent                 → end        task_complete
```

Plus: session tracking (`get_session_info`), empty-models TEXT fallback,
"do not finish" streaming flag, unknown-session 404s. All battery conventions
from the README applied.

## The install (documented path — WORKS)

```bash
python3 -m venv venv
venv/bin/pip install h3-harness-sdk        # → 0.1.2, ~30s
venv/bin/python -c "import h3_harness; print(h3_harness.__version__)"  # 0.1.2
```

No more DF-001/DF-002 — PyPI install is the real deal now. **Time-to-first-
success: ~2 min** (install + import + uvicorn up + health 200).

## The gate (documented path — WORKS)

```bash
venv/bin/pip install /path/to/get-h3/shim   # or git+https://github.com/get-h3/shim
venv/bin/h3-test --endpoint http://127.0.0.1:9191
# 44/44 PASSED, exit 0  (0.92s, p50 2.8ms / p95 130ms)
```

First attempt: **43/44** — the battery caught my own bug: I applied convention
#3 ("do not finish" → `finished=false`) only in the with-models branch and
hardcoded `finished=True` in my empty-models fallback. The convention docs
work; the battery is a real gate. Fix was one line.

## MockHermes (documented path — WORKS, one trap)

```python
from h3_harness.testbed import MockHermes
mock = MockHermes(ConvertBrain())
d = await mock.send_message("convert 5 km to miles")          # no models → TEXT
d = await mock.send_result(ResultPayload(type=ResultType.LLM_RESPONSE, ...))
```

Full loop PASS. **Trap:** on the *published* 0.1.2, `send_message(models=...)`
raises TypeError — the kwarg exists in repo HEAD (commit 2f63094) but not in
the wheel; its own docstring documents the missing kwarg. Workaround: build
the `ProcessRequest` directly (see `drive_loop.py` step 7) or install from git.

## README snippets — verified verbatim

- **Quickstart** (extracted verbatim + `uvicorn.run`): serves, echoes,
  battery conventions intact (GAP-002/017 hold). ⚠️ On published 0.1.2 its
  `/v1/health` reports `uptime_seconds` = Unix epoch (~1.78e9) and
  `version="1.0.0"` — GAP-025/029 fixes are repo-only (see findings).
- **Testbed snippet** (extracted verbatim): `python testbed_verbatim.py`
  exits 0 (GAP-026 holds).

## Errors hit and their fixes

| # | Error | Root cause | Fix / status |
|---|-------|-----------|--------------|
| 1 | `'ResultRequest' object has no attribute 'context'` (surfaced as HTTP 200 `end/error`) | README convention #1 says echo `context.history` in *every* Decision; ResultRequest has no context — only on_process can echo | Removed echo from on_result; **GAP-033** (docs ambiguity) |
| 2 | `'list' object has no attribute 'get'` (again masked as 200) | Real LLM APIs return `tool_calls` as a *list*; harness assumed dict | Handle both shapes; **GAP-034** notes the masking UX |
| 3 | 43/44 battery: `process_text_finished_false` | My empty-models fallback hardcoded `finished=True` | `finished = not streaming` in all TEXT branches |
| 4 | `MockHermes.send_message() got an unexpected keyword argument 'models'` | Wheel stale (repo added kwarg later) | Build ProcessRequest directly; **GAP-032d** |
| 5 | `DELETE /v1/sessions/nope → 200 {"terminated":true}` while cancel/GET → 404 | Wheel stale (GAP-019 is repo-only) | **GAP-032a** — publish 0.1.3 |

## What a new user needs that isn't documented

> **All four gaps below are now documented or fixed (back-propagated
> 2026-08-14, GAP-036/038)** — README → "Result payloads" / "Error
> handling" and `docs/api/protocol.md`. Kept as a historical record.

1. **`tool_calls` arrives as a LIST** (OpenAI-style) — the examples only show
   single-dict tool_call decisions. One `isinstance(tool, list)` guard saves a
   debug cycle. → **Resolved (GAP-036)**: README "Result payloads" sample +
   `docs/api/protocol.md` ResultPayload note.
2. **Exceptions are masked as HTTP 200** `{"decision":"end","reason":"error",
   "summary":...}` — if a session ends unexpectedly, read `summary`; enable
   logging to see `logger.exception` output. → **Resolved (GAP-034)**: README
   "Error handling" documents the end/error-200 contract.
3. **`req.result` is a plain dict** — `.get("type")`, never `.type` (this IS
   documented in the skill + langchain example, but not in the README).
   → **Resolved (GAP-038)**: README "Result payloads".
4. **Session status is always `"active"`** even after END (GAP-035).
   → **Fixed in 0.1.3 (GAP-035)**: `get_session_info` status pass-through.

## Bottom line for an integrator

The SDK is genuinely usable and the battery is a superb gate — you can build
a real agent brain in an afternoon and prove compliance in ~1s. Two caveats:
(a) install from **PyPI** (`pip install h3-harness-sdk`, 0.1.3+ — the stale
0.1.2 wheel is fixed by the 0.1.3 release, which carries the
DELETE-404/uptime/version/MockHermes fixes);
(b) follow the battery conventions exactly, and don't echo history in
`on_result` — it doesn't exist there.
