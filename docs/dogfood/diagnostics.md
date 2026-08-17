# H3 Python SDK — Diagnostics Trail

**What this is:** how `h3-harness-sdk` is built, why, the errors encountered
(dogfood run 2026-08-03 + project history), and the right way to do things.
Not raw logs — explained lessons.

**Last verified:** 2026-08-13 (tick #134, GAP-030: 44/44 battery target current; audit-2026-08.md marked superseded)

## 1. How the SDK is built

```
src/h3_harness/
├── protocol.py      Pydantic models generated from get-h3/protocol JSON Schema (v1)
├── harness.py       BaseHarness ABC + create_router() → 6 FastAPI endpoints
├── middleware.py    request logging (BaseHTTPMiddleware)
├── testbed.py       MockHermes — simulate Hermes Core without a server
└── examples/        echo.py, minimal.py, langchain_agent.py
```

- **Design:** harness authors subclass `BaseHarness` (implement `on_process`,
  `on_result`; optionally `on_cancel`, `on_session_terminate`, `health`,
  `get_session_info`) and mount `create_router(harness)` on FastAPI.
- **Protocol loop:** Hermes Core sends `POST /v1/process` (user message +
  context) → harness returns a `Decision` (`tool_call | llm_call | text |
  wait | delegate | end`) → Hermes executes it → `POST /v1/result` with the
  outcome → harness returns the next Decision → … → `end`.
- **Error containment:** the router wraps `on_process`/`on_result` in
  try/except and converts exceptions to `Decision(end, reason=error,
  summary=str(exc))` — HTTP always 200, failure visible in the decision.
  This is why a crashing example (langchain) fails *silently*.
- **Session endpoints:** `GET /v1/sessions/{id}` returns real data only if the
  harness implements `get_session_info`; otherwise 200/ACTIVE with empty
  fields. `DELETE` calls `on_session_terminate`.
- **Packaging:** hatchling, src-layout, `packages = ["src/h3_harness"]`.
  Wheel contents are NOT checked anywhere (no CI test on the artifact).

## 2. The big one: wheel builds without `__init__.py` (DF-001)

**Symptom (user's view):**
```
$ pip install h3-harness-sdk          # (even from a local path/git)
$ python -c "from h3_harness import BaseHarness"
ImportError: cannot import name 'BaseHarness' from 'h3_harness' (unknown location)
```
`h3_harness` imports as an empty **namespace package** (`__file__` is None).

**Root cause (proven by bisection):**
1. `.gitignore` contains `_*.py` — "Temp audit / inspection scripts (generated
   by foreman ticks)" (e.g. `_run_echo.py` at repo root).
2. Hatchling reads `.gitignore` (`hatchling/builders/config.py` →
   `vcs_exclusion_files` / `load_vcs_exclusion_patterns`) and applies the
   patterns to wheel file selection.
3. `_*.py` (unanchored) matches **any** file starting with `_` and ending
   `.py` in **any** directory — including `src/h3_harness/__init__.py` and
   `src/h3_harness/examples/__init__.py`.
4. Result: wheel contains `harness.py`, `protocol.py`, … but no `__init__.py`.
   (Same bug exists in get-h3/shim's wheel — same pattern.)

**Why tests stayed green:** tests run from the source tree (editable install /
`make install`), so `import h3_harness` works in CI. Only the *shipped artifact*
is broken. Classic "all tests green ≠ it works".

**The fix (verified):** anchor the pattern → `/_*.py`. Building the wheel then
includes both `__init__.py` files. Also: add a CI step that builds the wheel and
asserts `h3_harness/__init__.py` is in it. (Board: DF-001.)

**Bisection notes (for the curious):** `pip wheel` from the repo path was
consistently broken even with `--no-cache-dir`; a minimal copy of
`src/ + pyproject.toml + README.md` built fine; adding `.gitignore` reproduced
the breakage; replacing `_*.py` with `/_*.py` fixed it.

## 3. Errors hit during the dogfood run (and the right way)

| Error | Cause | Right way |
|---|---|---|
| `No matching distribution found for h3-harness-sdk` | package never published to PyPI (DF-002) | publish, or `pip install -e <checkout>` / document fallback |
| `ImportError: cannot import name 'BaseHarness'` | missing `__init__.py` in wheel (DF-001) | fix `.gitignore` pattern + CI wheel check |
| `pydantic ValidationError … messages.0 Input should be a valid dictionary` | `LLMCall.messages: list[dict]`, example passes `LLMMessage` objects (DF-003) | build messages as plain dicts |
| `AttributeError: 'dict' object has no attribute 'type'` (latent in langchain example) | `ResultRequest.result: dict`, example uses attribute access | use `req.result.get("type")` |
| battery `process_preserves_history` fail: "history shrank: 4 -> 0" | harness must echo `context.history` in Decisions (DF-004) | `history=list(req.context.history)` in every Decision |
| battery `no_models_available` fail: "hallucinated model" | harness issued LLM_CALL with `context.models == []` (DF-004) | guard: only LLM_CALL when models advertised; use `models[0].name` |
| battery `process_text_finished_false` fail | "do not finish" prompts must get `finished=false` (DF-004) | `streaming = "do not finish" in content` heuristic (echo example does this) |
| `GET /v1/sessions/{id}` returns `started_at:""` | router hardcodes empty strings; only `turn_count` passed through (DF-005) | pass through from `get_session_info` |

## 4. Project history lessons (from git log)

- The board migrated from `tasks.md` → DuckDB parquet (BOARD-V2, tick #35),
  then → JSONL canonical (JSONL-NORM-001, tick #83; board.db/parquet are
  untracked rebuildable caches). Board files:
  `.coding-hermes/board/{schema.sql,tasks.jsonl,events.jsonl,fixtures.jsonl}`.
- `E2E-001` (per-tick battery run) is the project's own self-check: the shipped
  echo example scores 44/44 against `h3-test`. **The echo example is the
  reference implementation** — when in doubt about a battery convention,
  read `src/h3_harness/examples/echo.py` (it implements all three DF-004
  conventions).
- A stale gitignored `_run_echo.py` at repo root (tick #22 era) scores 40/43 —
  ignore it; it lacks session tracking/streaming/history.
- GitReins guard: `validate-board-format.py` expects `.coding-hermes/tasks.md`
  with a matrix header — keep the file present and in v2.1 `|||` format.
- Scheduler: project registered (`Enabled=true`, CooldownS=7200, decay 1),
  ticking normally (tick #57, 2026-08-03). Fleet.toml pins cooldown; scheduler
  PUTs are a no-op by design.

## 5. The right way to add a feature / fix

1. `make install && make test && make lint` (106 tests, ruff clean).
2. Run the gate: `h3-test --endpoint http://127.0.0.1:9191` against your harness.
3. After packaging changes, ALWAYS `pip wheel --no-deps .` and inspect the
   wheel's file list (`unzip -l`) — CI does not.
4. Board storage is JSONL-canonical (JSONL-NORM-001): `tasks.jsonl` +
   `events.jsonl` are the git-tracked store; `board.db`/`*.parquet` are
   untracked rebuildable caches — never commit them.

## 6. The release-pipeline drift (2026-08-13 dogfood) — how it happened

> **SUPERSEDED (2026-08-14):** this section is a historical incident record.
> `0.1.3` was published with all four fixes (GAP-019/025/029 +
> MockHermes `send_message(models=...)`), and the CI `release-readiness`
> job (GAP-032) now fails when the published PyPI wheel lags the repo
> version. References to the PyPI `0.1.2` wheel below are intentionally
> historical — do not treat them as the current published version.

**The symptom:** a fresh `pip install h3-harness-sdk` (PyPI 0.1.2, published
2026-08-08) behaves like the repo looked ~2 weeks ago. Four board-✅ fixes are
missing from the artifact users actually install:

| Fix (board-✅) | Repo | Published 0.1.2 wheel |
|---|---|---|
| GAP-019 DELETE unknown session → 404 | ✅ | ❌ returns 200 `{"terminated":true}` |
| GAP-025 health uptime lazy-init | ✅ | ❌ epoch uptime (~1.78e9) for quickstart harnesses |
| GAP-029 health version = `__version__` | ✅ | ❌ hardcoded `"1.0.0"` |
| MockHermes `send_message(models=...)` | ✅ | ❌ TypeError (docstring documents the kwarg!) |

**Why:** the SDK's "done" definition is *repo state* (tests green, guard PASS,
board complete). Nothing ties "done" to *shipped state*. Fixes landed ticks
#106 (GAP-019) → #134 (GAP-029) after the 08-08 publish; there is no release
task, no version bump, and no CI check that compares the published PyPI
version to the repo version. The foreman's idle audits check tests/docs, not
PyPI. The board's green is thus repo-relative — the classic premature-
completion pattern moved to the release boundary.

**The right way (per GAP-032):**
1. Publish 0.1.3 with repo-HEAD `harness.py`/`testbed.py` (and re-verify with
   the four probes in GAP-032's PASS criteria — they're all cheap curls).
2. Add a release-readiness gate: CI job that queries PyPI JSON
   (`https://pypi.org/pypi/h3-harness-sdk/json`) and fails when the published
   version < repo `_version.py` AND there are merged fixes since the last
   publish — or simpler: a standing "release pending" board task that must
   close before new fix tasks land.
3. When a fix touches `harness.py`/`testbed.py`/`protocol.py` (anything a
   user imports), the foreman should check whether the last publish predates
   the fix — if yes, release. That's a 1-line check: compare commit date of
   the last PyPI upload vs the fix commit.

**Other lessons from this run:**

- **ResultRequest has no `context`** (protocol.py: decision_id/result/
  session_id only). The README's "echo context.history in every Decision"
  (convention #1) is therefore only satisfiable in `on_process`. The
  convention text predates ResultRequest's final shape; docs should say
  "every Decision returned from on_process". This is why the 08-03
  integration report's TodoBrain and this run's ConvertBrain both had to
  read source before getting on_result right.
- **Exceptions in handlers are caught by the router and returned as HTTP 200**
  with `{"decision":"end","reason":"error","summary":<exc>}`. This is the
  current contract (not a bug per se — the shim loop reads the summary) but
  it is undocumented, and the battery has no test that pins it down.
  `logger.exception` output goes to stderr only if logging is configured.
- **The battery is genuinely good at catching harness bugs**: my 43/44 first
  run was a real convention mistake the battery named precisely
  (`process_text_finished_false`). Respect it; it is the fastest feedback
  loop this repo has.
- **`tool_calls` arrives as a list** (OpenAI style) — the shipped examples
  only demonstrate single-dict decisions; a real harness needs the
  list-vs-dict guard (GAP-034 adjacent, worth an example update).
- Session lifecycle on the wire: `SessionResponse.status` is hardcoded
  `"active"` by the router even after END (GAP-035) — cosmetic today.

**Verification history:** 2026-08-03 run → DF-001..005 (install broken).
2026-08-13 run → GAP-032..035 (install fixed, wheel stale). Repo gates at
time of run: 138/138 pytest (4.6s), ruff clean, CI 6/6, board 40/40 complete.
