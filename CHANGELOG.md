# Changelog

All notable changes to the H3 Python SDK.

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
