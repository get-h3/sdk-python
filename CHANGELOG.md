# Changelog

All notable changes to the H3 Python SDK.

## [1.0.0] — 2026-07-19

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
