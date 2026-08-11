# Contributing to H3 SDK for Python

Python SDK for building H3-compliant agent harnesses. Implements the harness side of the H3 protocol using Pydantic + FastAPI.

## Development Setup

```bash
cd sdk-python/
python -m venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Or use the Makefile: `make install` creates the venv and installs dev deps.

## Package Structure

```
sdk-python/
├── src/h3_harness/
│   ├── protocol.py    # Pydantic models (generated from protocol repo JSON Schema)
│   ├── harness.py     # BaseHarness ABC + FastAPI router
│   ├── middleware.py  # Request logging middleware
│   ├── testbed.py     # MockHermes for pytest
│   └── examples/
│       ├── echo.py            # Echo harness (battery-ready template)
│       ├── minimal.py         # Bare-minimum example
│       └── langchain_agent.py # LangChain integration demo
├── tests/
│   ├── test_protocol.py
│   ├── test_harness.py
│   ├── test_middleware.py
│   ├── test_testbed.py
│   ├── test_schema_validation.py
│   ├── test_quickstart.py
│   ├── test_example_langchain.py
│   └── test_benchmarks.py
├── scripts/
│   ├── generate-protocol.py   # Regenerates protocol.py from get-h3/protocol schemas
│   └── serve_echo.py          # Serve the echo example for the test battery
└── Makefile
```

## Before Making Changes

### Run Tests

```bash
make test          # uv run pytest -x --tb=short -q
# 128 tests
```

### Run Lint + Format Check

```bash
make lint          # uv run ruff check src/ tests/
make fmt           # uv run ruff format src/ tests/
```

### Run the Test Battery

```bash
# Install the shim (not yet published to PyPI — install from source):
pip install git+https://github.com/get-h3/shim

# Start the echo example in one terminal:
uv run python src/h3_harness/examples/echo.py

# In another terminal, run the compliance test battery:
h3-test --endpoint http://localhost:9191
# 44 compliance tests, exit code 0 = compliant
```

### Regenerate Protocol Types

If the upstream protocol changed:

```bash
make generate      # uv run python scripts/generate-protocol.py + ruff fix/format
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

### Echo Example (Battery Conventions)

`src/h3_harness/examples/echo.py` is the battery-ready template (44/44 compliant).
If you modify it, keep the conventions intact — a naive harness that drops them
scores 41/44: echo `context.history` in every Decision, never issue `llm_call`
when `context.models` is empty, return `text.finished=false` for "do not finish"
prompts, and 404 unknown sessions.

## Quality Gates

### Pre-Commit

```bash
make lint          # uv run ruff check src/ tests/
make fmt           # uv run ruff format src/ tests/ (then re-check)
make test          # uv run pytest -x --tb=short -q (128 tests)
```

### CI Pipeline

GitHub Actions runs on every PR:
1. Lint (ruff)
2. Tests (pytest, 128 tests)
3. `h3-test --endpoint http://localhost:9191` (against echo example — 44/44 battery)

All must pass.

## Release

```bash
git tag v0.1.2
git push origin v0.1.2
# CI publishes to PyPI automatically
```

Current published version: `0.1.2` (`h3-harness-sdk` on PyPI).

## Review Checklist

- [ ] `make test` passes (128 tests)
- [ ] `make lint` passes
- [ ] `h3-test --endpoint http://localhost:9191` passes against echo example (44/44)
- [ ] New Pydantic fields use `Optional` where appropriate
- [ ] Protocol changes regenerated via `make generate`
- [ ] No hand-edits to generated types

## Questions?

See the umbrella project at [get-h3/h3](https://github.com/get-h3/h3) for architecture, specs, and the cross-repo task board.
