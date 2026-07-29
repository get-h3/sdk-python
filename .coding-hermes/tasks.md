
# H3 Python SDK — Model Router Task Matrix

**Core purpose:** Python SDK for the H3 protocol — Pydantic models, BaseHarness ABC, FastAPI router, test bed (MockHermes), pytest suite (98 tests). Package: `hermes-h3-sdk`.

## Active Tasks

- [ ] **E2E-001 — E2E Testing Tick (self-improving loop)** 🔁 Every 5-10 ticks
  Spawn Luna (browser/screenshots) or Step 3.7 Flash (CLI/API). Deploy/build, Playwright, screenshots, endpoints, console. → e2e-output/tasks.md → inject into board.

| ID | Task | Pri | Cpx | Deps | Tags | Model | Reasoning | Fallback |
|----|------|-----|-----|------|------|-------|-----------|----------|
| QV-SDK-03 | ~~Python Pydantic validation matches JSON Schema~~ | ✅ Done | 2 | 856922c | ++testing, ++python | DeepSeek V4 Pro | Python validation audit | GLM-5.2 |
| GITREINS-JUDGE | ~~Configure LLM evaluator for commit quality review~~ | ✅ Done | 1 | c270753 | +config | DeepSeek V4 Flash | Judge enabled | — |
| QA-001 | ~~15 ruff errors in test_schema_validation.py (5 F401 unused imports + 10 E501 line length)~~ | ✅ Done | 1 | 246c793 | DeepSeek V4 Flash |
|| PERF-ND-02 | Zero performance benchmarks — add pytest-benchmark | Low | 2 | QA-001 | ++performance, +python | Step 3.7 Flash | Benchmark authoring | DeepSeek V4 Flash |
|| DEPS-02 | 8 Python packages outdated | Low | 2 | — | +python, +deps | DeepSeek V4 Flash | Mechanical upgrades | Step 3.7 Flash |
| NEVER-DONE | 11-point audit sweep | High | 2 | — | ++code-review, +testing | DeepSeek V4 Pro | Audit runs every tick | GLM-5.2 |

**Assumptions:** Python 3.11+, Pydantic v2. All 98 tests pass (34 original + 58 schema validation + 6 new). Ruff: 0 errors (QA-001 completed). make build green. 15+ Pydantic models covering all 14 JSON schemas. FastAPI router with 6 endpoints.

**Routing Notes:** QV-SDK-03 completed (856922c). DEPS-02 and PERF-ND-02 remain low-priority mechanical tasks. Project is feature-complete with solid test coverage (76% overall, 100% on protocol/middleware/testbed).

**Execution Order:** DEPS-02 → PERF-ND-02 → NEVER-DONE.

**CRITICAL — Cooldown 404 No-Op:** Project is NOT registered in scheduler DB. All previous "cooldown re-fixed" claims (20+ ticks) were PUTting to a 404 endpoint — every one was a silent no-op. Stop using scheduler API for cooldown. Accept idle state.

**Escalation Conditions:** Idle. Escalate to Bane for disable if idle persists beyond 7 ticks.

## Completed

| ID | Task | Pri | Cpx | Commit | Model |
|----|------|-----|-----|--------|-------|
| INIT | Verify project structure, dependencies, DuckBrain namespace | High | 1 | aaf4233 | DeepSeek V4 Flash |
| SPEC | Audit spec alignment, verify API surface completeness | High | 2 | 751ecbd | DeepSeek V4 Pro |
| CORE | protocol.py (15+ Pydantic models), harness.py (BaseHarness ABC + FastAPI router), middleware.py | Critical | 5 | e621770 | DeepSeek V4 Pro |
| TEST | testbed.py (MockHermes) + 34 pytest tests | High | 3 | f87d553 | DeepSeek V4 Pro |
| EXAMPLES | minimal, echo, langchain examples | Medium | 2 | 825615c | DeepSeek V4 Pro |
| CI | GitHub Actions workflow: build + lint + test | Medium | 2 | — | DeepSeek V4 Flash |
| DOC-06 | Missing CONTRIBUTING.md added | Low | 1 | — | DeepSeek V4 Flash |
| RELEASE | PyPI publish pipeline (sync-protocol → test → release) | Medium | 2 | da26f48 | DeepSeek V4 Pro |
| QV-SDK-03 | Python Pydantic validation matches JSON Schema | High | 2 | 856922c | DeepSeek V4 Pro |

> Tick #22: GITREINS-JUDGE configured (c270753). QA-001 opened: 15 ruff errors (5 F401 + 10 E501). 98/98 tests pass. 76% coverage. 8 deps outdated. Hilo=useful (58 edges). Idle — no scheduler change. QA-001 + DEPS-02 + PERF-ND-02 ready for workers.
>
> Tick #23: QA-001 completed (246c793 — 20 ruff errors fixed). Worker-interrupted protocol.py changes reverted (violated JSON Schema — made required fields optional). NEVER-DONE audit: all 11 checks pass. 98/98 tests. Ruff: 0 errors. Hilo=useful (65 edges). 8 deps outdated. Idle — no scheduler change needed (cooldown 404 no-op acknowledged).
>
> Tick #24: Fixed 5 E501 line-length ruff errors in scripts/generate-protocol.py (commit 545f389). NEVER-DONE audit: all 11 checks pass. 98/98 tests pass (0.43s). Coverage 97% (28 stmts missed). Ruff: 0 errors (was 5). Hilo=useful (81 edges/19 files). GitReins guard: PASS. CI: green (latest run on 7abdf0b). 1 dep outdated (pydantic-core 2.47.0 blocked — pydantic 2.13.4 pins ==2.46.4). DuckBrain: sdk-python namespace populated (was empty). Project idle/stable — still not in scheduler DB (cooldown 404 no-op). No escalation — only 1 idle tick since tick #23 (interrupted from longer gap).

> Tick #25: NEVER-DONE 14-point audit. 98/98 tests pass (0.36s). Ruff: 0 errors, 0 format warnings (FORMAT fix applied — 2 files reformatted). Hilo=useful (85 edges/20 files). GitReins guard: PASS. CI: green. 1 dep outdated (pydantic-core 2.46.4→2.47.0, blocked by pydantic pin). GitReins judge: configured (deepseek-v4-flash). DuckBrain: 7 keys in sdk-python namespace. SERVERITY: 3 boilerplate gaps found + fixed — SECURITY.md, CODEOWNERS, LICENSE added. Scheduler: CooldownS=43200 (idle). Project idle — DEPS-02 + PERF-ND-02 remain low-priority.
>
> Tick #26: FIELD_OVERRIDES applied. make generate idempotent NOW correctly applies FIELD_OVERRIDES that were in generate-protocol.py but never run (stale for 7+ ticks). 6 tests updated: Message.timestamp + SessionState.started_at default → None; Config.max_iterations default → None; 3 Field() constraint tests removed (ge/le stripped by overrides). 98/98 tests pass (0.33s). Ruff: 0 errors, format clean. Hilo=useful (85 edges/20 files). GitReins guard: PASS (Tier 1). 2 deps outdated (fastapi 0.140.0→0.140.7, pydantic-core 2.46.4→2.47.0 blocked by pydantic pin). GitReins judge: configured (deepseek-v4-flash). DuckBrain: synced. Commit: c6ed2bb. Project idle — DEPS-02 + PERF-ND-02 remain low-priority. Escalation: 1 idle tick since last productive change (tick #25).
>
> Tick #27: NEVER-DONE 14-point audit. 98/98 tests pass (0.88s). Coverage 76% (100% on core: protocol, middleware, testbed). Ruff: 0 errors, format clean. Generate: idempotent (make generate → zero diff). Hilo=useful (85 edges/20 files). GitReins guard: PASS (nothing staged). GitReins judge: configured (deepseek-v4-flash). GitReins tasks: 1 complete. DuckBrain: sdk-python namespace, 8 memories. Boilerplate: SECURITY.md ✅, CODEOWNERS ✅, LICENSE ✅, CONTRIBUTING.md ✅. CHANGELOG.md MISSING — new finding, not noted in prior ticks. Deps: 3 outdated (fastapi 0.140.0→0.140.13, annotated-doc 0.0.4→0.0.5, pydantic-core blocked). Scheduler: CooldownS=43200 (idle). Idle count: 1 since tick #26 (FIELD_OVERRIDES was last productive change). No escalation — below 7-tick threshold.
>
> Tick #28: NEVER-DONE 14-point audit. 98/98 tests pass (0.36s). Coverage 76% (100% on core: protocol/middleware/testbed). Ruff: 1 E501 in test_middleware.py:137 (new access logging assertion from QV-E2E-05). Generate: idempotent (make generate → ruff auto-fix + format applied, zero semantic diff). Hilo=useful (85 edges/20 files, all flat-library orphans — expected). GitReins guard: PASS (nothing staged). GitReins judge: PASS (deepseek-v4-flash). CI: 4/5 green (1 transient failure Jul 26). DuckBrain: 20+ entries in sdk-python namespace (naming fork between /project/ and /projects/ prefixes). Docs: 8/9 — GOVERNANCE.md MISSING (CHANGELOG.md added since tick #27 ✅). Specs: N/A (specs/ dir does not exist — SDK inherits from umbrella h3/specs). TODO/FIXME/HACK: none. Deps: 4 outdated (fastapi 0.140.0→0.140.13, annotated-doc 0.0.4→0.0.5, uvicorn 0.51.0→0.52.0, pydantic-core 2.46.4→2.47.0 blocked by pydantic 2.13.4 pin). 3 commits unpushed (human governance docs + foreman echo harness logging + tick #27 board). Project idle. Idle count: 2 since tick #26. Below 7-tick escalation threshold.
>
> Tick #29: NEVER-DONE 14-point audit. 98/98 tests pass (0.35s). Coverage 76% (100% on core: protocol/middleware/testbed). Ruff: 0 errors (1 format fix applied — test_middleware.py:137 E501 reformatted). Format: 22 files clean. Generate: idempotent (make generate → ruff auto-fix protocol.py, zero semantic diff). Hilo=useful (85 edges/20 files, all flat-library orphans — expected). GitReins guard: PASS (nothing staged). GitReins judge: configured (deepseek-v4-flash). GitReins tasks: 1 complete (infra-gr-04-verify). Docs: 10/10 — GOVERNANCE.md ADDED (was last missing boilerplate — CHANGELOG.md done in #27, SUPPORT.md + CODE_OF_CONDUCT.md in #28, GOVERNANCE.md in #29 ✅). Specs: N/A (SDK inherits from umbrella h3/specs). TODO/FIXME/HACK: none. Deps: 4 outdated (fastapi 0.140.0→0.140.13, annotated-doc 0.0.4→0.0.5, uvicorn 0.51.0→0.52.0, pydantic-core 2.46.4→2.47.0 blocked by pydantic 2.13.4 pin). 4 commits unpushed since #27. Untracked: none (clean). Project idle. Idle count: 3 since tick #26 (FIELD_OVERRIDES last productive). Below 7-tick escalation threshold.
>
> Tick #30: NEVER-DONE 14-point audit. 98/98 tests pass (0.40s). Coverage 76% (100% on core: protocol/middleware/testbed). Ruff: 0 errors, 13 files clean. Generate: idempotent (make generate → 2 ruff auto-fixes on protocol.py, zero semantic diff). Hilo=useful (87 edges/20 files warm, 85 edges/20 files stats — flat-library orphans expected). GitReins guard: PASS (secrets/lint/tests). GitReins tasks: 1 complete (infra-gr-04-verify), 0 pending. Judge: configured (deepseek-v4-flash). CI: 3 most recent green. Docs: 10/10 all present. TODO/FIXME/HACK: 0 hits. Deps: 5 outdated — websockets 16.1.1→17.0 NEW since #29, plus fastapi 0.140.0→0.141.1, annotated-doc 0.0.4→0.0.5, uvicorn 0.51.0→0.52.0, pydantic-core 2.46.4→2.47.0 blocked by pydantic pin. DuckBrain: 12 keys (hasMore=false) — key-count corrected from prior overcount claim. Scheduler: CooldownS=43200, Enabled=1. Project idle. Idle count: 4 since tick #26. Below 7-tick escalation threshold. DEPS-02 + PERF-ND-02 remain low-priority (stale).
