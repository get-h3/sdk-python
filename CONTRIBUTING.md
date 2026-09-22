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

The tracked tree (verify any time with `git ls-files src tests scripts`):

```
sdk-python/
├── src/h3_harness/
│   ├── __init__.py            # Public surface (re-exports)
│   ├── _version.py            # Derives the version at import time (pyproject.toml is authority)
│   ├── protocol.py            # Pydantic models (generated from protocol repo JSON Schema)
│   ├── harness.py             # BaseHarness ABC + FastAPI router
│   ├── middleware.py          # Request logging middleware
│   ├── testbed.py             # MockHermes for pytest
│   └── examples/
│       ├── __init__.py
│       ├── echo.py            # Echo harness (battery-ready template)
│       ├── minimal.py         # Bare-minimum example
│       └── langchain_agent.py # LangChain integration demo
├── tests/                     # 18 pytest modules + __init__.py (220 tests)
│   ├── __init__.py
│   ├── test_benchmarks.py
│   ├── test_count_guard.py
│   ├── test_example_echo.py
│   ├── test_example_langchain.py
│   ├── test_example_launch_forms.py
│   ├── test_example_minimal.py
│   ├── test_generate_protocol.py
│   ├── test_handler_crash.py
│   ├── test_harness.py
│   ├── test_middleware.py
│   ├── test_protocol.py
│   ├── test_quickstart.py
│   ├── test_schema_validation.py
│   ├── test_session_gc.py
│   ├── test_session_health_parity.py
│   ├── test_session_status.py
│   ├── test_testbed.py
│   └── test_version_authority.py
├── scripts/
│   ├── check-test-count.sh        # Polices the count prose in this repo (battery/suite)
│   ├── generate-protocol.py       # Regenerates protocol.py from get-h3/protocol schemas
│   ├── refresh-vendored-schemas.sh # Re-vendors the upstream JSON Schemas
│   ├── serve_echo.py              # Serve the echo example for the test battery
│   └── test-count.txt             # Canonical counts (battery=46, suite=220)
├── Makefile
├── pyproject.toml             # Packaging, version authority, dev extras
├── pytest.ini                 # pytest config (testpaths, asyncio_mode)
└── uv.lock                    # Locked dependency set
```

This inventory is kept equal to the tracked tree (the acceptance for a doc PR
is that the list and `git ls-files` agree). `docs/`, `skills/`, `.github/` and
the governance files at the repo root are described in
[docs/repository-layout.md](docs/repository-layout.md).

## Before Making Changes

### Run Tests

```bash
make test          # uv run pytest -x --tb=short -q
# 220 tests
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
# 46 compliance tests, exit code 0 = compliant
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

`src/h3_harness/examples/echo.py` is the battery-ready template (46/46 compliant).
If you modify it, keep the conventions intact — a naive harness that drops them
scores well below 46/46 (README measures one at 40/46): echo `context.history` in
every Decision, never issue `llm_call`
when `context.models` is empty, return `text.finished=false` for "do not finish"
prompts, and 404 unknown sessions.

## Quality Gates

### Pre-Commit

```bash
make lint          # uv run ruff check src/ tests/
make fmt           # uv run ruff format src/ tests/ (then re-check)
make test          # uv run pytest -x --tb=short -q (220 tests)
```

### CI Pipeline

GitHub Actions runs on every PR:
1. Lint (ruff)
2. Tests (pytest, 220 tests)
3. `h3-test --endpoint http://localhost:9191` (against echo example — 46/46 battery)

All must pass.

## Release

```bash
git tag v0.1.3
git push origin v0.1.3
# CI publishes to PyPI automatically
```

Current published version: `0.1.6` (`h3-harness-sdk` on PyPI; single source
`pyproject.toml` `[project] version`, derived into `h3_harness.__version__`
at import time — the CI `docs-version-sweep` job fails if a living doc
references an older version).

### Version bump checklist

1. Bump `[project] version` in `pyproject.toml`.
2. `uv lock` (refreshes the lockfile's own-package version).
3. `src/h3_harness/_version.py` needs NO manual edit — it derives the
   version at import time from installed metadata, falling back to
   `pyproject.toml`.
4. Add a `CHANGELOG.md` section for the new version.
5. Update any docs version references in the same commit — the CI
   `docs-version-sweep` job fails on a living doc that lags the release.

## Review Checklist

- [ ] `make test` passes (220 tests)
- [ ] `make lint` passes
- [ ] `h3-test --endpoint http://localhost:9191` passes against echo example (46/46)
- [ ] New Pydantic fields use `Optional` where appropriate
- [ ] Protocol changes regenerated via `make generate`
- [ ] No hand-edits to generated types

## Questions?

See the umbrella project at [get-h3/h3](https://github.com/get-h3/h3) for architecture, specs, and the cross-repo task board.
