"""DF-H3-SDK-PYTHON-FOREMAN-2: `make generate` must work on a standalone clone.

scripts/generate-protocol.py used to resolve schemas only from a sibling
``../protocol`` dev checkout (absent on a clone) and from
``protocol-src/schemas/v1`` (never present in this repo), so ``make generate``
died with ``ERROR: Schema directory not found: protocol-src/schemas/v1`` even
though this repo vendors the same schema files under ``tests/schemas/v1``
(GAP-050).

These tests pin the resolution order (``--schema-dir``, ``$H3_SCHEMA_DIR``,
sibling checkout, vendored copy, actionable error) and prove the vendored copy
regenerates the committed ``src/h3_harness/protocol.py`` exactly — after the
same ruff pass the Makefile's ``generate`` target applies.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "scripts" / "generate-protocol.py"
VENDORED_SCHEMAS = REPO_ROOT / "tests" / "schemas" / "v1"
COMMITTED_PROTOCOL = REPO_ROOT / "src" / "h3_harness" / "protocol.py"
PROTOCOL_REPO_URL = "https://github.com/get-h3/protocol"


def _load_generator():
    spec = importlib.util.spec_from_file_location("h3_generate_protocol", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load_generator()


def _make_clone(root: Path, with_vendored: bool = True) -> Path:
    """A tmp repo root that looks like a fresh clone (no sibling checkout)."""
    if with_vendored:
        vendored = root / "tests" / "schemas" / "v1"
        vendored.mkdir(parents=True)
        for schema in sorted(VENDORED_SCHEMAS.glob("*.json")):
            shutil.copy(schema, vendored / schema.name)
    return root


def _schemas_dir(root: Path) -> Path:
    """A populated schemas dir at an arbitrary location (for explicit/env)."""
    target = root / "schemas" / "v1"
    target.mkdir(parents=True)
    for schema in sorted(VENDORED_SCHEMAS.glob("*.json")):
        shutil.copy(schema, target / schema.name)
    return target


def _ruff_binary() -> str:
    bundled = Path(sys.executable).parent / "ruff"
    if bundled.exists():
        return str(bundled)
    found = shutil.which("ruff")
    if found is None:
        pytest.fail(
            "ruff is required: src/h3_harness/protocol.py is stored in ruff "
            "format, so the generated text must be ruff-normalized before it "
            "can be compared. Install the dev extra (pip install -e '.[dev]')."
        )
    return found


def _ruff_normalize(code: str, tmp_dir: Path, name: str) -> str:
    """Apply the ruff pass the Makefile's `generate` target applies."""
    path = tmp_dir / name
    path.write_text(code)
    for args in (["check", "--fix"], ["format"]):
        subprocess.run(
            [
                _ruff_binary(),
                "--config",
                str(REPO_ROOT / "pyproject.toml"),
                *args,
                "--quiet",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    return path.read_text()


def test_cli_argument_wins_over_env_and_fallback(tmp_path, monkeypatch):
    explicit = _schemas_dir(tmp_path / "explicit")
    env_dir = _schemas_dir(tmp_path / "from-env")
    monkeypatch.setenv("H3_SCHEMA_DIR", str(env_dir))

    assert gen.resolve_schema_dir(str(explicit), tmp_path) == explicit


def test_missing_explicit_dir_fails_loudly_instead_of_falling_back(tmp_path):
    clone = _make_clone(tmp_path / "clone")
    missing = tmp_path / "typo-schemas" / "v1"

    with pytest.raises(gen.SchemaDirNotFoundError) as excinfo:
        gen.resolve_schema_dir(str(missing), clone)

    assert str(missing) in str(excinfo.value)
    assert "--schema-dir" in str(excinfo.value)


def test_vendored_copy_resolves_when_no_sibling_checkout(tmp_path, monkeypatch):
    monkeypatch.delenv("H3_SCHEMA_DIR", raising=False)
    clone = _make_clone(tmp_path / "clone")
    assert not (clone.parent / "protocol").exists()

    resolved = gen.resolve_schema_dir(None, clone)

    assert resolved == clone / "tests" / "schemas" / "v1"
    assert resolved.is_dir()


def test_env_var_wins_over_sibling_and_vendored(tmp_path, monkeypatch):
    clone = _make_clone(tmp_path / "clone")
    sibling = clone.parent / "protocol" / "schemas" / "v1"
    sibling.mkdir(parents=True)
    env_dir = _schemas_dir(tmp_path / "from-env")
    monkeypatch.setenv("H3_SCHEMA_DIR", str(env_dir))

    assert gen.resolve_schema_dir(None, clone) == env_dir


def test_stale_env_var_falls_through_to_vendored_copy(tmp_path, monkeypatch):
    clone = _make_clone(tmp_path / "clone")
    monkeypatch.setenv("H3_SCHEMA_DIR", str(tmp_path / "does-not-exist"))

    assert gen.resolve_schema_dir(None, clone) == clone / "tests" / "schemas" / "v1"


def test_sibling_dev_checkout_wins_over_vendored(tmp_path, monkeypatch):
    monkeypatch.delenv("H3_SCHEMA_DIR", raising=False)
    clone = _make_clone(tmp_path / "clone")
    sibling = clone.parent / "protocol" / "schemas" / "v1"
    sibling.mkdir(parents=True)

    # The candidate is returned as constructed (`<clone>/../protocol/...`), so
    # compare canonically.
    assert gen.resolve_schema_dir(None, clone).resolve() == sibling.resolve()


def test_no_schema_source_names_every_candidate(tmp_path, monkeypatch):
    monkeypatch.delenv("H3_SCHEMA_DIR", raising=False)
    clone = _make_clone(tmp_path / "clone", with_vendored=False)
    assert not (clone / "tests").exists()
    assert not (clone.parent / "protocol").exists()

    with pytest.raises(gen.SchemaDirNotFoundError) as excinfo:
        gen.resolve_schema_dir(None, clone)

    message = str(excinfo.value)
    # Every candidate is named, in resolution order.
    assert "--schema-dir" in message
    assert "H3_SCHEMA_DIR" in message
    assert str(clone / ".." / "protocol" / "schemas" / "v1") in message
    assert str(clone / "tests" / "schemas" / "v1") in message
    # And the error says what to do about it.
    assert "--schema-dir /path/to/schemas/v1" in message
    assert PROTOCOL_REPO_URL in message


def test_cli_error_path_prints_candidates_and_writes_nothing(tmp_path):
    before = COMMITTED_PROTOCOL.read_bytes()
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--schema-dir", str(tmp_path / "nope")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "ERROR: Schema directory not found" in result.stderr
    assert str(tmp_path / "nope") in result.stderr
    assert PROTOCOL_REPO_URL in result.stderr
    assert COMMITTED_PROTOCOL.read_bytes() == before


def test_vendored_schemas_regenerate_the_committed_protocol(tmp_path):
    generated = gen.generate_protocol(str(VENDORED_SCHEMAS))
    committed = COMMITTED_PROTOCOL.read_text()

    # No semantic drift: the only difference between the raw generated text and
    # the committed file is whitespace, which the Makefile's `generate` target
    # fixes by running ruff.
    assert re.sub(r"\s+", "", generated) == re.sub(r"\s+", "", committed)

    # Exact equality of the normalized text — the committed artifact must be
    # reproducible from the vendored schemas byte-for-byte.
    assert _ruff_normalize(generated, tmp_path, "generated.py") == _ruff_normalize(
        committed, tmp_path, "committed.py"
    )


def test_standalone_clone_generates_from_vendored_copy(tmp_path):
    clone = _make_clone(tmp_path / "clone")
    scripts = clone / "scripts"
    scripts.mkdir()
    shutil.copy(GENERATOR, scripts / GENERATOR.name)
    (clone / "src" / "h3_harness").mkdir(parents=True)
    assert not (clone.parent / "protocol").exists()

    result = subprocess.run(
        [sys.executable, str(scripts / GENERATOR.name)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "tests/schemas/v1" in result.stdout
    written = (clone / "src" / "h3_harness" / "protocol.py").read_text()
    assert _ruff_normalize(written, tmp_path, "clone-generated.py") == _ruff_normalize(
        COMMITTED_PROTOCOL.read_text(), tmp_path, "clone-committed.py"
    )
