# Contributing to H3 Harness SDK for Python

## Setup

```bash
git clone https://github.com/get-h3/sdk-python.git
cd sdk-python
make install
```

Requires Python 3.10+ and `uv`.

## Development Workflow

| Command | What it does |
|---------|-------------|
| `make install` | Create venv, install dev dependencies |
| `make build` | Verify package imports cleanly |
| `make test` | Run test suite (pytest, 34 tests) |
| `make test-full` | Run tests with verbose output |
| `make lint` | Ruff check (E, F, I, N, W, UP) |
| `make fmt` | Ruff auto-format |
| `make all` | install → lint → build → test |
| `make generate` | Regenerate `protocol.py` from JSON Schema |

## Project Structure

```
sdk-python/
├── src/h3_harness/
│   ├── __init__.py          # Public API exports
│   ├── protocol.py          # Pydantic models (generated from get-h3/protocol)
│   ├── harness.py           # BaseHarness ABC + FastAPI router
│   ├── middleware.py         # Request logging middleware
│   ├── testbed.py           # MockHermes for pytest
│   └── examples/
│       ├── echo.py           # Echo harness
│       ├── minimal.py        # Minimal harness with health endpoint
│       └── langchain_agent.py # LangChain integration
├── tests/
│   ├── test_protocol.py      # Protocol serialization + validation
│   └── test_harness.py       # Harness router endpoint tests
├── scripts/
│   └── generate-protocol.py  # JSON Schema → Pydantic code generator
├── CONTRIBUTING.md
├── README.md
├── AGENTS.md
├── Makefile
└── pyproject.toml
```

## Making Changes

1. Create a feature branch from `main`
2. Make your changes
3. Run `make lint` and `make test` — both must pass
4. If you changed the protocol spec, run `make generate` to regenerate `protocol.py`
5. Submit a PR against `main`

## Protocol Regeneration

The `protocol.py` file is generated from the JSON Schema definitions in [get-h3/protocol](https://github.com/get-h3/protocol). When the protocol spec changes:

```bash
make generate
```

This runs `scripts/generate-protocol.py`, applies ruff fixes, and formats the output. Verify with `make lint && make test`.

## Testing

Tests use pytest with httpx `TestClient` for FastAPI route testing. The testbed (`MockHermes`) provides a lightweight harness runner for unit tests.

```bash
# Run all tests
make test

# Run with verbose output
make test-full
```

New features should include tests. Test files live in `tests/` and follow the pattern `test_<module>.py`.

## Code Style

Python 3.10+, formatted with ruff. Type hints encouraged on public API surfaces.

## Quality Gate

All PRs must pass the GitReins quality gate before merge. This includes lint, build, and test checks across Python 3.10, 3.11, and 3.12 via GitHub Actions CI.

## References

- H3 umbrella: [get-h3/h3](https://github.com/get-h3/h3)
- Protocol spec: [get-h3/protocol](https://github.com/get-h3/protocol)
- SDK spec: [specs/04-SDK-Libraries.md](https://github.com/get-h3/h3/blob/main/specs/04-SDK-Libraries.md)
