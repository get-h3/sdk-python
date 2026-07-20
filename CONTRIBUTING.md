# Contributing to H3 SDK for Python

Python SDK for building H3-compliant agent harnesses. Implements the harness side of the H3 protocol using Pydantic + FastAPI.

## Development Setup

```bash
cd sdk-python/
python -m venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Package Structure

```
sdk-python/
├── src/h3_harness/
│   ├── protocol.py    # Pydantic models (generated from protocol repo JSON Schema)
│   ├── harness.py     # BaseHarness ABC + FastAPI router
│   ├── middleware.py   # Request logging middleware
│   └── testbed.py     # MockHermes for pytest
├── tests/
│   ├── test_protocol.py
│   ├── test_harness.py
│   └── test_testbed.py
└── examples/
    ├── echo/          # Echo harness (returns messages back)
    ├── minimal/       # Bare-minimum example
    └── langchain/     # LangChain integration demo
```

## Before Making Changes

### Run Tests

```bash
python -m pytest tests/ -v
# 34 tests
```

### Run Lint + Type Check

```bash
ruff check src/ tests/
mypy src/
```

### Run the Test Battery

```bash
# Start the echo example in one terminal:
python examples/echo/main.py

# In another terminal, run the compliance test battery:
h3-test --endpoint http://localhost:9191
# 43 compliance tests, exit code 0 = compliant
```

### Sync Protocol Types

If the upstream protocol changed:

```bash
python scripts/sync_protocol.py
```

This regenerates `src/h3_harness/protocol.py` from `get-h3/protocol` schemas. Never hand-edit generated Pydantic models.

## Making Changes

### BaseHarness Interface

- `harness.py` defines the `BaseHarness` ABC with `on_process` and `on_result`
- Changes to the ABC are MAJOR — they break all existing harnesses
- New optional hooks should use separate mixins

### FastAPI Router

- `create_router()` builds a FastAPI APIRouter with `/v1/health`, `/v1/process`, `/v1/result`
- Must follow the H3 protocol exactly — see `get-h3/protocol/h3-protocol.yaml`
- All endpoints log METHOD /path STATUS DURATION via middleware

### Middleware

- `middleware.py` uses FastAPI's `BaseHTTPMiddleware`
- Logs structured request info without leaking credentials

### Pydantic Models

- Models use `Optional` types for protocol-optional fields
- Validation must match JSON Schema constraints from `get-h3/protocol/schemas/v1/`
- `model_dump(exclude_none=True)` for wire format compatibility

## Quality Gates

### Pre-Commit

```bash
ruff check src/ tests/      # Lint
ruff format --check src/ tests/  # Format
mypy src/                   # Type check
python -m pytest tests/ -v  # Tests (34)
```

### CI Pipeline

GitHub Actions runs on every PR:
1. Lint (ruff)
2. Type check (mypy)
3. Tests (pytest, 34 tests)
4. `h3-test --endpoint http://localhost:9191` (against echo example)

All must pass.

## Release

```bash
git tag v1.0.0
git push origin v1.0.0
# CI publishes to PyPI automatically
```

## Review Checklist

- [ ] `pytest tests/ -v` passes (34 tests)
- [ ] `ruff check` passes
- [ ] `mypy src/` passes
- [ ] `h3-test --endpoint http://localhost:9191` passes against echo example
- [ ] New Pydantic fields use `Optional` where appropriate
- [ ] Protocol changes regenerated via `sync_protocol.py`
- [ ] No hand-edits to generated types

## Questions?

See the umbrella project at [get-h3/h3](https://github.com/get-h3/h3) for architecture, specs, and the cross-repo task board.
