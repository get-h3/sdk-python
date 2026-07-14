# Task Board — H3 SDK for Python

## [x] INIT — Verify project structure, dependencies, and DuckBrain namespace
- [x] **Commit:** `aaf4233`

## [x] SPEC — Audit spec alignment, verify API surface completeness
- [x] **Commit:** `751ecbd`

## [x] CORE — Implement protocol.py, harness.py, middleware.py
- [x] protocol.py: 343 lines, 15+ Pydantic models, all 14 JSON schemas covered, 8 spec gaps fixed
- [x] harness.py: 190 lines, BaseHarness ABC + FastAPI router, 6 endpoints, prefix support
- [x] middleware.py: 65 lines, BaseHTTPMiddleware request logging
- [x] `__init__.py`: public API exports (Decision, DecisionType, BaseHarness, create_router, etc.)
- [x] Verification: 12 protocol checks + 8 harness checks all pass
- [x] Build: `make build` green, Lint: `ruff check` green
- [x] **Commit:** `e621770`

## [ ] TEST — Testbed + test coverage
### testbed.py — MockHermes for pytest
- Files: `src/h3_harness/testbed.py`
- [ ] MockHermes class: send_message(content), send_result(result)
- [ ] Decision assertions
- [ ] AC: `make build` passes
### Tests
- Files: `tests/test_protocol.py`, `tests/test_harness.py`
- [ ] Protocol serialization round-trip + validation
- [ ] Harness router endpoints via httpx TestClient
- [ ] AC: `make test` passes

## [ ] DOC — README.md + example harnesses
- [ ] README.md with quickstart from AGENTS.md
- [ ] Example: echo.py
- [ ] AC: `make lint` passes

## [ ] CI — GitHub Actions workflow
- [ ] CI workflow: lint + build + test on Python 3.10/3.11/3.12
- [ ] AC: CI passes on push
