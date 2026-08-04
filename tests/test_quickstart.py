"""Tests asserting the README Quickstart harness passes the h3-test battery conventions.

The Quickstart harness is extracted directly from README.md and exec'd, so any
edit to the snippet that breaks battery compliance fails this module — no
"keep in sync" drift possible.
"""

from __future__ import annotations

import re
from pathlib import Path

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

# ── README Quickstart extraction ────────────────────────────────────


def _load_quickstart_harness() -> type:
    """Extract and exec the README Quickstart python block; return its harness class."""
    readme = Path(__file__).resolve().parents[1] / "README.md"
    match = re.search(
        r"## Quickstart\s*\n+```python\n(?P<code>.*?)\n```",
        readme.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert match is not None, "README Quickstart python block not found"
    ns: dict = {}
    exec(match.group("code"), ns)
    return ns["MyHarness"]


QuickstartHarness = _load_quickstart_harness()


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


async def test_quickstart_echoes_context_history():
    """Battery test_2_8: prior history flows back through the Decision."""
    prior = [
        HistoryEntry(role="user", content="earlier user"),
        HistoryEntry(role="assistant", content="earlier assistant"),
        HistoryEntry(role="user", content="another user"),
        HistoryEntry(role="assistant", content="another assistant"),
    ]
    req = _process_request("what did we say before?", history=prior)

    decision = await QuickstartHarness().on_process(req)

    assert decision.history == prior


async def test_quickstart_do_not_finish_sets_finished_false():
    """Battery test_2_4: 'do not finish' prompts return text.finished=False."""
    req = _process_request("Just start a thought, do not finish it yet.")

    decision = await QuickstartHarness().on_process(req)

    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.finished is False


async def test_quickstart_normal_message_sets_finished_true():
    """Battery test_2_5: normal prompts return text.finished=True."""
    req = _process_request("Give me the final answer in one short sentence.")

    decision = await QuickstartHarness().on_process(req)

    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.finished is True


async def test_quickstart_no_llm_call_with_empty_models():
    """Battery test_5_8: empty context.models never yields an llm_call decision."""
    req = _process_request("use any model you want")

    decision = await QuickstartHarness().on_process(req)

    assert decision.decision is not DecisionType.LLM_CALL
    assert decision.decision == DecisionType.TEXT


async def test_quickstart_no_llm_call_with_models_available():
    """The quickstart stays text-only even when models are listed."""
    model = Model(context_window=128000, name="test-model", provider="test")
    req = _process_request("hello", models=[model])

    decision = await QuickstartHarness().on_process(req)

    assert decision.decision == DecisionType.TEXT
    assert decision.llm_call is None
