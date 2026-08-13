"""Regression tests for the echo example template port (GAP-031).

The battery-ready template (``echo.py``) is the copy-paste starting point for
harness developers, so it must serve the battery port (9191) by default:
AGENTS.md quickstart and the README battery docs point ``h3-test
--endpoint http://localhost:9191`` at it. The port is argv-configurable
(``python echo.py 8000``) for local overrides. No server is launched here —
only the importable ``_server_port`` helper is exercised.
"""

from __future__ import annotations

from h3_harness.examples.echo import _server_port


def test_server_port_defaults_to_battery_port(monkeypatch):
    """No argv → the battery port 9191 (matches h3-test --endpoint docs)."""
    # Pin sys.argv so the helper's no-arg path doesn't read pytest's own args.
    monkeypatch.setattr("sys.argv", ["echo.py"])
    assert _server_port() == 9191
    assert _server_port([]) == 9191


def test_server_port_override_from_argv():
    """An explicit argv argument wins over the default."""
    assert _server_port(["8000"]) == 8000
    assert _server_port(["0"]) == 0
