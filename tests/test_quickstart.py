"""Tests asserting the README and AGENTS.md Quickstart harnesses pass the
h3-test battery conventions.

The Quickstart harnesses are extracted directly from README.md and AGENTS.md
and exec'd, so any edit to either snippet that breaks battery compliance fails
this module — no "keep in sync" drift possible.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from h3_harness import DecisionType
from h3_harness.protocol import (
    Config,
    Context,
    HistoryEntry,
    Identity,
    Message,
    Model,
    ProcessRequest,
    SessionState,
)

# ── Quickstart extraction ───────────────────────────────────────────

_QUICKSTART_BLOCK_PATTERN = r"## Quickstart\s*\n+```python\n(?P<code>.*?)\n```"

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_quickstart_harness(markdown_path: Path) -> type:
    """Extract and exec the Quickstart python block from a markdown file.

    Returns the harness class defined in the snippet.
    """
    match = re.search(
        _QUICKSTART_BLOCK_PATTERN,
        markdown_path.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert match is not None, f"Quickstart python block not found in {markdown_path}"
    ns: dict = {}
    exec(match.group("code"), ns)
    return ns["MyHarness"]


_QUICKSTART_HARNESSES = {
    "README": _load_quickstart_harness(_REPO_ROOT / "README.md"),
    "AGENTS.md": _load_quickstart_harness(_REPO_ROOT / "AGENTS.md"),
}

_QUICKSTART_HARNESS_CASES = [
    pytest.param(harness, id=name) for name, harness in _QUICKSTART_HARNESSES.items()
]


def _process_request(
    content: str,
    *,
    history: list[HistoryEntry] | None = None,
    models: list[Model] | None = None,
) -> ProcessRequest:
    """Build a ProcessRequest with explicit history/models control."""
    return ProcessRequest(
        context=Context(
            config=Config(),
            history=list(history or []),
            models=list(models or []),
            session_state=SessionState(),
        ),
        identity=Identity(chat_id="c-1", platform="test"),
        message=Message(content=content),
        session_id="s-1",
    )


# ── Battery conventions ─────────────────────────────────────────────


@pytest.mark.parametrize("harness", _QUICKSTART_HARNESS_CASES)
async def test_quickstart_echoes_context_history(harness: type):
    """Battery test_2_8: prior history flows back through the Decision."""
    prior = [
        HistoryEntry(role="user", content="earlier user"),
        HistoryEntry(role="assistant", content="earlier assistant"),
        HistoryEntry(role="user", content="another user"),
        HistoryEntry(role="assistant", content="another assistant"),
    ]
    req = _process_request("what did we say before?", history=prior)

    decision = await harness().on_process(req)

    assert decision.history == prior


@pytest.mark.parametrize("harness", _QUICKSTART_HARNESS_CASES)
async def test_quickstart_do_not_finish_sets_finished_false(harness: type):
    """Battery test_2_4: 'do not finish' prompts return text.finished=False."""
    req = _process_request("Just start a thought, do not finish it yet.")

    decision = await harness().on_process(req)

    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.finished is False


@pytest.mark.parametrize("harness", _QUICKSTART_HARNESS_CASES)
async def test_quickstart_normal_message_sets_finished_true(harness: type):
    """Battery test_2_5: normal prompts return text.finished=True."""
    req = _process_request("Give me the final answer in one short sentence.")

    decision = await harness().on_process(req)

    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.finished is True


@pytest.mark.parametrize("harness", _QUICKSTART_HARNESS_CASES)
async def test_quickstart_no_llm_call_with_empty_models(harness: type):
    """Battery test_5_8: empty context.models never yields an llm_call decision."""
    req = _process_request("use any model you want")

    decision = await harness().on_process(req)

    assert decision.decision is not DecisionType.LLM_CALL
    assert decision.decision == DecisionType.TEXT


@pytest.mark.parametrize("harness", _QUICKSTART_HARNESS_CASES)
async def test_quickstart_no_llm_call_with_models_available(harness: type):
    """The quickstart stays text-only even when models are listed."""
    model = Model(context_window=128000, name="test-model", provider="test")
    req = _process_request("hello", models=[model])

    decision = await harness().on_process(req)

    assert decision.decision == DecisionType.TEXT
    assert decision.llm_call is None
