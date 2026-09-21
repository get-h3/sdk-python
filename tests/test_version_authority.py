"""GAP-068: one version authority — the drift guard.

``pyproject.toml`` ``[project] version`` is the release authority;
``h3_harness.__version__`` must be derived from it (installed metadata
first, falling back to pyproject.toml in a source tree) — never a
hardcoded literal that can go stale when a release bump half-lands
(0.1.5 was served on the wire while pyproject said 0.1.6).
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_MODULE_PATH = REPO_ROOT / "src" / "h3_harness" / "_version.py"


def _pyproject_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_version_matches_pyproject():
    """h3_harness.__version__ equals the [project] version in pyproject.toml.

    This is the guard that fails when a release bump half-lands (pyproject
    bumped, hardcoded version string not).
    """
    import h3_harness

    assert h3_harness.__version__ == _pyproject_version()


def test_version_module_resolves_without_install(monkeypatch):
    """Reloading _version.py in isolation yields the pyproject version.

    importlib.metadata.version is monkeypatched to raise
    PackageNotFoundError so the metadata path is provably dead and the
    pyproject fallback is what resolves the value (source tree, no
    install).
    """

    def _not_installed(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", _not_installed)

    spec = importlib.util.spec_from_file_location(
        "_version_gap068_no_install", VERSION_MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.__version__ == _pyproject_version()


def test_version_is_a_string():
    import h3_harness

    assert isinstance(h3_harness.__version__, str)
    assert h3_harness.__version__
    # Loose semver: major.minor.patch.
    assert re.fullmatch(r"\d+\.\d+\.\d+", h3_harness.__version__)
