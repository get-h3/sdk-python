# H3 Python SDK — Model Router Task Matrix

**Core purpose:** Python SDK for the H3 protocol — Pydantic models, BaseHarness ABC, FastAPI router, test bed (MockHermes), pytest suite (98 tests). Package: `hermes-h3-sdk`.

## Active Tasks

- [ ] **E2E-001 — E2E Testing Tick (self-improving loop)** 🔁 Every 5-10 ticks
  Spawn Luna (browser/screenshots) or Step 3.7 Flash (CLI/API). Deploy/build, Playwright, screenshots, endpoints, console. → e2e-output/tasks.md → inject into board.

| ID | Task | Pri | Cpx | Deps | Tags | Model | Reasoning | Fallback |
|----|------|-----|-----|------|------|-------|-----------|----------|
| QV-SDK-03 | ~~Python Pydantic validation matches JSON Schema~~ | ✅ Done | 2 | 856922c | ++testing, ++python | DeepSeek V4 Pro | Python validation audit | GLM-5.2 |
| PERF-ND-02 | Zero performance benchmarks — add pytest-benchmark | Low | 2 | — | ++performance, +python | Step 3.7 Flash | Benchmark authoring | DeepSeek V4 Flash |
| DEPS-02 | 7 Python packages outdated | Low | 2 | — | +python, +deps | DeepSeek V4 Flash | Mechanical upgrades | Step 3.7 Flash |
| NEVER-DONE | 11-point audit sweep | High | 2 | — | ++code-review, +testing | DeepSeek V4 Pro | Audit runs every tick | GLM-5.2 |

**Assumptions:** Python 3.11+, Pydantic v2. All 98 tests pass (34 original + 58 schema validation). Ruff clean. make build green. 15+ Pydantic models covering all 14 JSON schemas. FastAPI router with 6 endpoints.

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

> Tick #21: Cooldown 404 no-op diagnosed. Project NOT in scheduler DB. 98/98 tests pass. Build clean. CI all green. QV-SDK-03 completed.
