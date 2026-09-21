"""Package version for h3-harness-sdk, derived at import time (GAP-068).

Resolution order:

1. ``importlib.metadata.version("h3-harness-sdk")`` — the installed
   artifact's version (wheel, editable install, fresh venv). This is what
   a published artifact serves on the wire in ``GET /v1/health``.
2. ``[project] version`` in the repository's ``pyproject.toml`` — the
   release authority, correct for a source tree where the package is not
   installed. Parsed with :mod:`tomllib` (Python >= 3.11); on Python 3.10
   (no ``tomllib``) a minimal regex reads the same field.
3. The literal ``"0.0.0"`` — last resort only, so importing this module
   can never crash (no metadata, no readable ``pyproject.toml``).

``pyproject.toml`` is the single version authority for releases; this
module derives from it at import time and must never be hand-edited to
bump the version.

Imported by :mod:`h3_harness` (as ``h3_harness.__version__``) and by
:mod:`h3_harness.harness` for the ``GET /v1/health`` version field.
Deliberately imports only the standard library, so either importer can
use it without an import cycle.
"""

from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

_DIST_NAME = "h3-harness-sdk"
# src/h3_harness/_version.py -> parents[2] is the repo root.
_PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"
_LAST_RESORT = "0.0.0"


def _version_from_installed_dist() -> str | None:
    """Version of the installed ``h3-harness-sdk`` artifact, if any."""
    try:
        return importlib.metadata.version(_DIST_NAME)
    except Exception:
        # PackageNotFoundError (not installed) or a broken metadata
        # environment — either way, fall through to the repo authority.
        return None


def _version_from_pyproject() -> str | None:
    """``[project] version`` from the repo's ``pyproject.toml``."""
    try:
        text = _PYPROJECT_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        import tomllib
    except ImportError:
        # Python 3.10: no tomllib — minimal regex fallback over the same
        # ``version = "..."`` field under ``[project]``.
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        return match.group(1) if match else None
    try:
        version = tomllib.loads(text)["project"]["version"]
    except (KeyError, TypeError, tomllib.TOMLDecodeError):
        return None
    return str(version)


def _resolve_version() -> str:
    derived = _version_from_installed_dist() or _version_from_pyproject()
    return derived if derived else _LAST_RESORT


__version__ = _resolve_version()
