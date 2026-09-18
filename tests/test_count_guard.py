"""Guard tests for scripts/check-test-count.sh (H3-GAP-087).

This repo's counts are declared in exactly two machine-readable places — the
repo-owned ``scripts/test-count.txt`` (battery + suite) and the live sources the
guard derives them from (pytest's own collection for the suite, the sibling
shim's canonical file for the battery) — and quoted in prose everywhere else.
Nothing in this repo policed that prose, so the stale-count class re-offended
here repeatedly: CONTRIBUTING advertised a battery total and a suite size the
repo had long outgrown, and CI gates pinned a literal count while every test
passed.

These tests drive the guard's documented outcomes hermetically through its env
overrides, so a plain ``pytest`` run catches prose drift before CI does:

* exit 0 — canonical counts, the live pytest collection and current-state prose
  all agree;
* exit 1 — drift (the suite grew, the battery moved upstream, a tracked
  current-state surface still quotes a retired count, or a dated report quotes
  one without a point-in-time banner);
* exit 2 — the guard is misconfigured (missing / malformed canonical counts, no
  usable interpreter, an uncollectable suite, a non-numeric sibling count).

Retired counts are assembled from digit fragments so this file's own source
carries none of them: the guard sweeps tracked ``*.py`` files too, and a test
that hardcoded them would fail the very sweep it is testing.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD = REPO_ROOT / "scripts" / "check-test-count.sh"
CANON = REPO_ROOT / "scripts" / "test-count.txt"
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PROTECTED = REPO_ROOT / "AGENTS.md"


def retired_battery() -> str:
    """A battery total the shim has retired (assembled, never literal)."""
    return "4" + "5"


def read_canonical() -> dict[str, int]:
    found: dict[str, int] = {}
    for line in CANON.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        assert value.isdigit(), f"{CANON}: {key} value {value!r} is not a bare number"
        assert key not in found, f"{CANON} declares {key}= twice"
        found[key] = int(value)
    for key in ("battery", "suite"):
        assert found.get(key), f"{CANON} must declare a positive {key}="
    return found


def run_guard(
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the guard with a clean H3_SDK_* environment plus any overrides."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("H3_SDK_")}
    env.update(env_overrides or {})
    return subprocess.run(
        ["sh", str(GUARD)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def scratch_tree(tmp_path: Path, suite: int) -> tuple[Path, Path]:
    """A self-contained scan root: ``suite`` collectable tests + canonical file.

    Battery parity is pointed at an absent sibling count so every exit code below
    is driven by the check under test, and the interpreter is the one running
    these tests (it always has pytest).
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    body = [f"def test_scratch_{i}():\n    assert True\n" for i in range(suite)]
    (tests_dir / "test_scratch.py").write_text("\n".join(body), encoding="utf-8")
    canon = tmp_path / "canon.txt"
    canon.write_text(f"battery=46\nsuite={suite}\n", encoding="utf-8")
    return tmp_path, canon


def scratch_env(
    root: Path, canon: Path, extra: dict[str, str] | None = None
) -> dict[str, str]:
    env = {
        "H3_SDK_SCAN_ROOT": str(root),
        "H3_SDK_COUNT_FILE": str(canon),
        "H3_SDK_SHIM_COUNT_FILE": str(root / "absent-shim-count.txt"),
        "H3_SDK_PYTHON": sys.executable,
    }
    env.update(extra or {})
    return env


# --- the canonical inputs agree with reality ---------------------------------


def test_canonical_counts_agree_with_the_battery_and_the_suite() -> None:
    counts = read_canonical()

    shim_canon = REPO_ROOT.parent / "shim" / "scripts" / "test-count.txt"
    if shim_canon.is_file():
        shim_battery = shim_canon.read_text(encoding="utf-8").strip()
        assert shim_battery == str(counts["battery"]), (
            "the shim's canonical battery count and this repo's disagree"
        )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"^(\d+) tests? collected", result.stdout, re.MULTILINE)
    assert match, f"pytest did not report a collection count:\n{result.stdout[-2000:]}"
    assert int(match.group(1)) == counts["suite"], (
        f"pytest collects {match.group(1)} tests but scripts/test-count.txt says "
        f"suite={counts['suite']}"
    )


def test_guard_passes_on_the_current_tree() -> None:
    result = run_guard()
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS" in result.stdout
    counts = read_canonical()
    for value in (counts["battery"], counts["suite"]):
        assert str(value) in result.stdout, result.stdout


def test_guard_reports_the_protected_agents_file_instead_of_sweeping_it() -> None:
    """AGENTS.md is edit-protected; the guard must note it, not fail or hide it."""
    result = run_guard()
    assert result.returncode == 0, result.stderr + result.stdout

    agents_text = PROTECTED.read_text(encoding="utf-8")
    stale = re.search(rf"{retired_battery()}[/-]", agents_text)
    if stale is None:
        pytest.skip("AGENTS.md no longer quotes a retired count")
    assert "AGENTS.md (protected, not swept)" in result.stderr, result.stderr
    assert "H3-GAP-086" in result.stderr, result.stderr


# --- exit 2: guard misconfigured ---------------------------------------------


def test_guard_exits_two_when_canonical_file_is_missing(tmp_path: Path) -> None:
    result = run_guard({"H3_SDK_COUNT_FILE": str(tmp_path / "absent.txt")})
    assert result.returncode == 2, result.stdout
    assert "canonical count file missing" in result.stderr


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("battery=46\nsuite=one hundred\n", "exactly one 'suite="),
        ("battery=46\n", "exactly one 'suite="),
        ("suite=157\n", "exactly one 'battery="),
        ("battery=46\nsuite=157\nsuite=158\n", "exactly one 'suite="),
    ],
)
def test_guard_exits_two_when_canonical_counts_are_malformed(
    tmp_path: Path, content: str, expected: str
) -> None:
    canon = tmp_path / "canon.txt"
    canon.write_text(content, encoding="utf-8")
    result = run_guard({"H3_SDK_COUNT_FILE": str(canon)})
    assert result.returncode == 2, result.stdout
    assert expected in result.stderr


def test_guard_exits_two_when_the_interpreter_is_missing() -> None:
    result = run_guard({"H3_SDK_PYTHON": "/nonexistent/bin/python"})
    assert result.returncode == 2, result.stdout
    assert "is not executable" in result.stderr


def test_guard_exits_two_when_the_suite_cannot_be_collected(tmp_path: Path) -> None:
    canon = tmp_path / "canon.txt"
    canon.write_text("battery=46\nsuite=3\n", encoding="utf-8")
    result = run_guard(scratch_env(tmp_path, canon))
    assert result.returncode == 2, result.stdout
    assert "could not derive the pytest suite count" in result.stderr


def test_guard_exits_two_when_sibling_count_is_not_a_number(tmp_path: Path) -> None:
    counts = read_canonical()
    canon = tmp_path / "canon.txt"
    canon.write_text(
        f"battery={counts['battery']}\nsuite={counts['suite']}\n", encoding="utf-8"
    )
    shim = tmp_path / "shim-count.txt"
    shim.write_text("forty-six\n", encoding="utf-8")
    result = run_guard(
        {"H3_SDK_COUNT_FILE": str(canon), "H3_SDK_SHIM_COUNT_FILE": str(shim)}
    )
    assert result.returncode == 2, result.stdout
    assert "is not a bare number" in result.stderr


def test_guard_exits_two_on_a_path_with_whitespace(tmp_path: Path) -> None:
    root, canon = scratch_tree(tmp_path, 3)
    (root / "odd name.md").write_text("nothing here\n", encoding="utf-8")
    result = run_guard(scratch_env(root, canon))
    assert result.returncode == 2, result.stdout
    assert "whitespace in a tracked path" in result.stderr


# --- exit 1: drift -----------------------------------------------------------


def test_guard_exits_one_when_the_suite_moved(tmp_path: Path) -> None:
    counts = read_canonical()
    canon = tmp_path / "canon.txt"
    canon.write_text(
        f"battery={counts['battery']}\nsuite={counts['suite'] + 1}\n", encoding="utf-8"
    )
    result = run_guard({"H3_SDK_COUNT_FILE": str(canon)})
    assert result.returncode == 1, result.stdout
    assert "suite drift" in result.stderr


def test_guard_exits_one_when_the_battery_moved_upstream(tmp_path: Path) -> None:
    counts = read_canonical()
    canon = tmp_path / "canon.txt"
    canon.write_text(
        f"battery={counts['battery']}\nsuite={counts['suite']}\n", encoding="utf-8"
    )
    shim = tmp_path / "shim-count.txt"
    shim.write_text(f"{counts['battery'] + 1}\n", encoding="utf-8")
    result = run_guard(
        {"H3_SDK_COUNT_FILE": str(canon), "H3_SDK_SHIM_COUNT_FILE": str(shim)}
    )
    assert result.returncode == 1, result.stdout
    assert "battery drift" in result.stderr


def test_guard_flags_a_retired_battery_literal_in_a_current_state_surface(
    tmp_path: Path,
) -> None:
    root, canon = scratch_tree(tmp_path, 100)
    stale = f"{retired_battery()}/{retired_battery()}"
    (root / "drift.md").write_text(
        f"the battery reports {stale} PASSED\n", encoding="utf-8"
    )

    result = run_guard(scratch_env(root, canon))
    assert result.returncode == 1, result.stderr
    assert "drift.md:1" in result.stdout
    assert "stale count literal" in result.stderr


def test_guard_flags_a_stale_suite_claim(tmp_path: Path) -> None:
    root, canon = scratch_tree(tmp_path, 100)
    (root / "suite-claim.md").write_text(
        f"Run the suite: {101} tests green.\n", encoding="utf-8"
    )

    result = run_guard(scratch_env(root, canon))
    assert result.returncode == 1, result.stderr
    assert "suite-claim.md:1" in result.stdout
    assert "suite claim" in result.stdout


def test_guard_flags_a_retired_count_inside_a_python_docstring(tmp_path: Path) -> None:
    root, canon = scratch_tree(tmp_path, 100)
    stale = f"{retired_battery()}/{retired_battery()}"
    (root / "module.py").write_text(
        f'"""Module docstring: battery-compliant ({stale})."""\n', encoding="utf-8"
    )

    result = run_guard(scratch_env(root, canon))
    assert result.returncode == 1, result.stderr
    assert "module.py:1" in result.stdout


# --- historical exemptions ---------------------------------------------------


def test_guard_exempts_a_line_marked_historical(tmp_path: Path) -> None:
    root, canon = scratch_tree(tmp_path, 100)
    stale = f"{retired_battery()}/{retired_battery()}"
    (root / "narration.md").write_text(
        f"first run scored {stale} (count-ok-historical: the 2026-08 era).\n",
        encoding="utf-8",
    )

    result = run_guard(scratch_env(root, canon))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASS" in result.stdout


def test_guard_exempts_a_document_that_declares_itself_historical(
    tmp_path: Path,
) -> None:
    root, canon = scratch_tree(tmp_path, 100)
    stale = f"{retired_battery()}/{retired_battery()}"
    doc = root / "docs" / "dogfood" / "diagnostics.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "# Trail\n\n> **Historical (2026-08-04):** point-in-time record.\n\n"
        f"the battery scored {stale}\n",
        encoding="utf-8",
    )

    result = run_guard(scratch_env(root, canon))
    assert result.returncode == 0, result.stderr + result.stdout


def test_guard_requires_a_banner_on_dated_records(tmp_path: Path) -> None:
    root, canon = scratch_tree(tmp_path, 100)
    stale = f"{retired_battery()}/{retired_battery()}"
    report = root / "docs" / "dogfood" / "2026-01-01-integration.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(f"# Report\n\nthe battery scored {stale}\n", encoding="utf-8")

    bare = run_guard(scratch_env(root, canon))
    assert bare.returncode == 1, bare.stdout
    assert "no point-in-time banner" in bare.stderr
    assert "2026-01-01-integration.md" in bare.stderr

    report.write_text(
        "# Report\n\n"
        "> **Historical (2026-01-01):** point-in-time record — the counts below\n"
        "> are not live status.\n\n"
        f"the battery scored {stale}\n",
        encoding="utf-8",
    )
    bannered = run_guard(scratch_env(root, canon))
    assert bannered.returncode == 0, bannered.stderr + bannered.stdout


def test_guard_ignores_changelog_and_board_records(tmp_path: Path) -> None:
    root, canon = scratch_tree(tmp_path, 100)
    stale = f"{retired_battery()}/{retired_battery()}"
    (root / "CHANGELOG.md").write_text(f"battery was {stale}\n", encoding="utf-8")
    board = root / ".coding-hermes" / "board"
    board.mkdir(parents=True, exist_ok=True)
    (board / "tasks.jsonl").write_text("{}\n", encoding="utf-8")

    result = run_guard(scratch_env(root, canon))
    assert result.returncode == 0, result.stderr + result.stdout


# --- the guard is wired into normal verification -----------------------------


def test_guard_is_wired_into_make_and_ci() -> None:
    assert GUARD.is_file(), "scripts/check-test-count.sh is missing"
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert re.search(r"^\.PHONY:.*\bverify-counts\b", makefile, re.M)
    target = r"^verify-counts:\n\tsh scripts/check-test-count\.sh$"
    assert re.search(target, makefile, re.M)
    assert re.search(r"^all:.*\bverify-counts\b", makefile, re.M)
    assert "sh scripts/check-test-count.sh" in WORKFLOW.read_text(encoding="utf-8")
