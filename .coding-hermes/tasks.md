# Task Board — H3 SDK for Python

## [x] INIT — Verify project structure, dependencies, and DuckBrain namespace
- [x] Build passes (`make build` → `build: OK`)
- [x] Lint passes (`ruff check` → all checks passed)
- [x] Dependencies installed (fastapi, pydantic, pytest, ruff, httpx)
- [x] Venv configured and editable install works
- [x] DuckBrain namespace empty (fresh project, no prior context)
- [x] Protocol JSON schemas available at `get-h3/protocol/schemas/v1/` (14 files)
- [x] Full spec at `get-h3/h3/specs/04-SDK-Libraries.md` §3 (Python SDK)
- [x] No CI workflows configured yet
- [x] Git identity: correct (`totalwindupflightsystems` / `totalwindupflightsystems@gmail.com`)
- [ ] x] **Commit:** `bbcb0` (board update, no source changes)

## [ ] SPEC — Audit spec alignment, verify API surface completeness
- [ ] Verify all 14 protocol types mapped in spec §3.2 (tool_call, llm_call, text, wait, delegate, end + ProcessRequest, ResultRequest, CancelRequest, HealthResponse)
- [ ] Verify BaseHarness ABC matches spec §3.3 (on_process, on_result, on_cancel, on_session_terminate, health)
- [ ] Verify FastAPI router matches spec §3.4 (create_router, one-line integration)
- [ ] Verify middleware spec §3.1 (logging, timeout, error handling)
- [ ] Verify testbed spec (MockHermes with send_message, send_result)
- [ ] Verify examples spec (minimal.py, echo.py, langchain_agent.py)
- [ ] Cross-reference protocol JSON schemas against spec for any discrepancies
- [ ] Report any gaps as subtasks

## [ ] CORE — Implement protocol.py, harness.py, middleware.py
### protocol.py — Pydantic models generated from protocol JSON schemas
- Files: `src/h3_harness/protocol.py`
- [ ] All 14 protocol types as Pydantic BaseModel classes
- [ ] DecisionType enum (tool_call, llm_call, text, wait, delegate, end)
- [ ] ProcessRequest, ResultRequest, CancelRequest, HealthResponse
- [ ] ToolCall, LLMCall, TextResponse, Wait, Delegate, End
- [ ] Common types: Message, Attachment, Identity, HistoryEntry, Tool, Model, Config, Context, SessionState
- [ ] Decision discriminated union with auto decision_id UUID
- [ ] JSON Schema compliance (field names match wire format: `session_id` not `sessionId`)
- [ ] AC: `make build` passes, `from h3_harness.protocol import *` works
### harness.py — BaseHarness ABC + FastAPI router
- Files: `src/h3_harness/harness.py`
- [ ] BaseHarness ABC with abstract on_process, on_result
- [ ] Optional overrides: on_cancel, on_session_terminate, health
- [ ] create_router(harness) → FastAPI APIRouter with /v1/health, /v1/process, /v1/result, /v1/cancel, /v1/sessions/{id}
- [ ] Input validation via Pydantic models
- [ ] AC: `make build` passes with imports
### middleware.py — Logging, timeout, error handling
- Files: `src/h3_harness/middleware.py`
- [ ] Request logging middleware
- [ ] Timeout enforcement per session config
- [ ] Error response formatting (ErrorResponse model)
- [ ] AC: `make build` passes

## [ ] TEST — Testbed + test coverage
### testbed.py — MockHermes for pytest
- Files: `src/h3_harness/testbed.py`
- [ ] MockHermes class with send_message(content) and send_result(result) methods
- [ ] Decision matchers/assertions for test ergonomics
- [ ] Fixture for standard ProcessRequest with default tools/models/config
- [ ] AC: `make build` passes
### Tests
- Files: `tests/test_protocol.py`, `tests/test_harness.py`
- [ ] Protocol types: serialization round-trip, discriminated union validation
- [ ] Harness: mock harness integration, router endpoint tests via httpx TestClient
- [ ] AC: `make test` passes with meaningful coverage

## [ ] DOC — Generate/update SDK documentation
- [ ] README.md with quickstart from AGENTS.md
- [ ] Package docstrings (at minimum public API surface)
- [ ] Example harness: echo.py (returns user input)
- [ ] AC: `make lint` passes, docs are accurate

## [ ] CI — Verify CI pipeline health
- [ ] GitHub Actions workflow for lint + build + test
- [ ] Python 3.10, 3.11, 3.12 matrix
- [ ] AC: CI passes on push
