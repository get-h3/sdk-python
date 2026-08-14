# Changelog

All notable changes to the H3 Python SDK.

## [0.1.3] — 2026-08-14

### Added
- `DELETE /v1/sessions/{id}` for unknown sessions now returns 404 (was a
  200 `{"terminated": true}`), matching cancel/GET semantics
- `SessionResponse.status` pass-through: `get_session_info` may carry a
  `status` key (`"active"` / `"completed"`); unknown values fall back to
  `"active"` (the pre-0.1.3 default)
- `MockHermes.send_message(models=...)` kwarg — testbeds can now supply a
  model list (empty-models guard, battery `test_5_8`)
- `/v1/health` reports the real package version (`__version__`) and
  lazy-initializes uptime — quickstart harnesses show sane
  `uptime_seconds` instead of a Unix epoch
- Handler-exception masking contract documented: exceptions from
  `on_process`/`on_result` are caught by the router and returned as HTTP
  200 `end`/`error` (README → "Error handling", locked in by
  `tests/test_handler_crash.py`)
- CI release-readiness gate: compares the published PyPI version against
  `pyproject.toml` and fails the build when the published wheel is stale

### Fixed
- Published 0.1.2 wheel was stale vs repo HEAD — 0.1.3 ships the
  accumulated fixes above (DELETE-404, health uptime/version, MockHermes
  `models` kwarg)

## [0.1.2] — 2026-08-08

### Added
- `GET /v1/sessions/{id}` and `/v1/cancel` now return 404 for unknown/untracked sessions (shim battery 43→44)
- Quickstart and AGENTS.md snippets now track sessions (battery-compliant: history echo, `finished=false` streaming, empty-models guard) — verified 44/44 against the published PyPI page
- CI battery job gate updated to 44/44

### Fixed
- README.md "Passing the battery" section: 43/43 → 44/44 references
- sdist excludes `.coding-hermes`, `.gitreins`, `.vfs` stray files (sdist hygiene)

## [0.1.1] — 2026-08-08

### Fixed
- sdist (.tar.gz) now published alongside the wheel — `pip install --no-binary h3-harness-sdk` works (0.1.0 was wheel-only)

## [0.1.0] — 2026-08-03

### Added
- `protocol.py`: Pydantic models generated from H3 JSON Schema
- `harness.py`: BaseHarness ABC + FastAPI router
- `middleware.py`: Request logging middleware
- `testbed.py`: MockHermes for pytest
- Echo example harness (examples/echo/)
- Structured access logging
- Pydantic defaults for optional fields (max_iterations, session_state)
- response_model_exclude_none=True for wire-compatible JSON
- GitReins quality gate
- Hilo code graph
