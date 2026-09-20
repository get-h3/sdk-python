"""Regression tests for the examples' documented launch forms (GAP-062).

README's Examples section and docs/api/examples.md promise that every shipped
example exposes a module-level ``app`` (so ``uvicorn
h3_harness.examples.<name>:app`` works) and state the port each example binds
when run as a script. GAP-062: ``langchain_agent.py`` built its app only
inside the main guard, so the advertised uvicorn form died with
``Attribute ... app not found``, and docs/api/examples.md claimed a blanket
``:8000`` default while ``echo.py`` serves the battery port 9191.

No server is launched here — these pin the importable surface (module
attribute + uvicorn's dotted loader contract) and the documented default
ports.
"""

from __future__ import annotations

import ast
import importlib
import inspect

import pytest
from fastapi import FastAPI

# (module name, port the example binds when run as a script) — mirrors the
# "Default ports" list in docs/api/examples.md.
EXAMPLE_PORTS = [
    ("echo", 9191),  # battery port: h3-test --endpoint works out of the box
    ("minimal", 8000),
    ("langchain_agent", 8000),
]


def _script_port(module) -> int:
    """Extract the literal ``port=`` keyword passed to a call in the module
    (the ``uvicorn.run(...)`` in its ``__main__`` runner)."""
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "port" and isinstance(kw.value, ast.Constant):
                    return kw.value.value
    raise AssertionError(f"no literal port= keyword found in {module.__name__}")


@pytest.mark.parametrize("name", [name for name, _ in EXAMPLE_PORTS])
def test_example_exposes_module_level_app(name):
    """``uvicorn h3_harness.examples.<name>:app`` resolves: uvicorn's dotted
    loader is import_module + getattr, so the module must expose a FastAPI
    ``app`` attribute."""
    module = importlib.import_module(f"h3_harness.examples.{name}")
    assert isinstance(getattr(module, "app"), FastAPI)


@pytest.mark.parametrize(("name", "port"), EXAMPLE_PORTS)
def test_example_script_runner_binds_documented_port(name, port):
    """The port each example binds as a script equals the port
    docs/api/examples.md states for it (echo 9191, the others 8000)."""
    module = importlib.import_module(f"h3_harness.examples.{name}")
    if name == "echo":
        # echo.py derives its port via the argv-overridable helper
        # (tests/test_example_echo.py pins the default and the override).
        assert module._server_port([]) == port
    else:
        assert _script_port(module) == port
