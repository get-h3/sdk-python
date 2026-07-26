
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
