"""Regression tests for the minimal example harness (GAP-027).

The minimal example is the copy-paste starting template, so it must stay
battery-compliant: get_session_info returns None for unknown sessions (the
create_router 404 precondition for test_5_9b/test_5_10), sessions are
recorded on process, the "do not finish" streaming heuristic drives
text.finished (test_2_4), and decisions echo context.history (test_2_8).
"""

from __future__ import annotations

from h3_harness import DecisionType
from h3_harness.examples.minimal import MinimalHarness
from h3_harness.protocol import (
    Config,
    Context,
    HistoryEntry,
    Identity,
    Message,
    ProcessRequest,
    SessionState,
)
from h3_harness.testbed import MockHermes


async def test_get_session_info_unknown_returns_none():
    """Unknown sessions → None so create_router 404s (battery 5_9b/5_10)."""
    harness = MinimalHarness()
    MockHermes(harness)
    assert harness.get_session_info("sess-unknown") is None


async def test_on_process_records_session():
    """A processed message records session info with a growing turn count."""
    harness = MinimalHarness()
    mock = MockHermes(harness)
    await mock.send_message("hello", session_id="sess-1")
    info = harness.get_session_info("sess-1")
    assert info is not None
    assert info["turn_count"] == 1
    assert info["started_at"]

    await mock.send_message("again", session_id="sess-1")
    info2 = harness.get_session_info("sess-1")
    assert info2 is not None
    assert info2["turn_count"] == 2


async def test_on_process_streaming_heuristic():
    """The 'do not finish' heuristic → text.finished is False (battery 2_4)."""
    mock = MockHermes(MinimalHarness())
    decision = await mock.send_message("do not finish yet")
    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.finished is False


async def test_on_process_echoes_history():
    """The Decision echoes context.history (battery test_2_8)."""
    req = ProcessRequest(
        session_id="sess-h",
        message=Message(content="hello", timestamp="2026-08-13T00:00:00Z"),
        identity=Identity(platform="test", chat_id="c-1"),
        context=Context(
            config=Config(max_iterations=10, timeout_seconds=300),
            session_state=SessionState(started_at="2026-08-13T00:00:00Z"),
            history=[HistoryEntry(role="user", content="earlier")],
        ),
    )
    decision = await MinimalHarness().on_process(req)
    assert decision.history == [HistoryEntry(role="user", content="earlier")]
