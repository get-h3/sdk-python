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
- [x] Git identity: correct
- [x] **Commit:** `aaf4233`

## [x] SPEC — Audit spec alignment, verify API surface completeness
- [x] All 6 decision types verified against schema: match
- [x] ProcessRequest, ResultRequest verified: match
- [x] ToolCall, LLMCall, TextResponse, Wait verified: match
- [x] BaseHarness ABC methods verified: match
- [x] FastAPI router endpoints verified: match
- [x] Testbed/MockHermes verified: match
- [x] **8 gaps found** — documented below, none are blocking for CORE:

### SPEC GAP-1: End.reason missing `rate_limited` and `cancelled`
- Spec has 4 values. Schema has 6. Add `rate_limited` and `cancelled` to implementation.

### SPEC GAP-2: HealthResponse missing optional fields
- Schema has `uptime_seconds`, `active_sessions`, `degraded_reason`, `error`. All optional. Include in implementation.

### SPEC GAP-3: Delegate missing `agent` field
- Schema has `agent` (sub-agent name/role). Include in implementation.

### SPEC GAP-4: SessionResponse not defined in spec
- Schema defines GET /v1/sessions/{id} response. Add SessionResponse model.

### SPEC GAP-5: ErrorResponse not defined in spec
- Schema has 8 error codes. Add ErrorResponse model for middleware.

### SPEC GAP-6: CancelRequest not explicitly shown in spec types
- Schema defined. Ensure it's implemented (implied by BaseHarness.on_cancel).

### SPEC GAP-7: Pydantic v2 Field(default_factory) preferred over custom __init__
- Spec uses old `__init__` pattern for decision_id UUID. Use `Field(default_factory=...)`.

### SPEC GAP-8: LLMCall.messages typed as `list[dict]` — use structured model
- Schema defines `{role, content}` objects. Use proper Pydantic model.

- [x] **Verdict:** Spec is comprehensive and implementation-ready. All gaps are minor — implement during CORE with schema as authority.
- [x] **Commit:** _pending_

## [ ] CORE — Implement protocol.py, harness.py, middleware.py
### protocol.py — Pydantic models generated from protocol JSON schemas
- Files: `src/h3_harness/protocol.py`
- [ ] All 15+ protocol types as Pydantic BaseModel classes
- [ ] DecisionType enum (6 values: tool_call, llm_call, text, wait, delegate, end)
- [ ] ProcessRequest, ResultRequest, CancelRequest, HealthResponse, SessionResponse, ErrorResponse
- [ ] ToolCall (name, params, reasoning?), LLMCall (model, messages, system_prompt?, temperature?, max_tokens?)
- [ ] TextResponse (content, finished), Wait (reason, duration_seconds?, poll_endpoint?)
- [ ] Delegate (agent?, task, context?, model?, provider?), End (reason, summary?)
- [ ] Common types: Message (role, content, attachments?, timestamp), Attachment, Identity, HistoryEntry, Tool, Model, Config, Context, SessionState
- [ ] Decision with discriminated union + Field(default_factory=uuid4) for decision_id
- [ ] JSON Schema compliance: field names match wire format, camelCase in JSON
- [ ] AC: `make build` passes, imports work, Pydantic validates schemas correctly

### harness.py — BaseHarness ABC + FastAPI router
- Files: `src/h3_harness/harness.py`
- [ ] BaseHarness ABC: abstract on_process, on_result; optional on_cancel, on_session_terminate, health
- [ ] create_router(harness) → FastAPI APIRouter
- [ ] Endpoints: GET /v1/health, POST /v1/process, POST /v1/result, POST /v1/cancel, DELETE /v1/sessions/{id}, GET /v1/sessions/{id}
- [ ] Input validation via Pydantic, ErrorResponse on failures
- [ ] AC: `make build` passes

### middleware.py — Logging, timeout, error handling
- Files: `src/h3_harness/middleware.py`
- [ ] Request logging + timing middleware
- [ ] Error handler → ErrorResponse with proper error codes
- [ ] AC: `make build` passes

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
