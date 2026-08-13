"""Regression tests for the LangChain example harness (DF-003, GAP-028).

Covers the DF-003 fix: LLMCall.messages must be a list of plain dicts
(not LLMMessage objects), and ResultRequest.result must be read via
dict access (.get) since it is a plain dict, not an object.

GAP-028 adds the battery-compliance guard: on_process only issues an
LLM_CALL when context.models is non-empty (README convention #2, battery
test_5_8) — with empty models it falls back to TEXT. Decisions echo
context.history and sessions are tracked (get_session_info).

These tests import only fastapi + h3_harness — LangChain itself is not
required, matching the example module's top-level imports.
"""

from __future__ import annotations

from h3_harness import DecisionType
from h3_harness.examples.langchain_agent import LangChainHarness
from h3_harness.protocol import Model
from h3_harness.testbed import MockHermes


def _models() -> list[Model]:
    """Non-empty model list for the LLM_CALL-path tests."""
    return [Model(name="gpt-4o-mini", provider="openai", context_window=128000)]


async def test_on_process_returns_llm_call_with_dict_messages():
    """send_message with models available returns an LLM_CALL whose messages
    are dicts with role/content."""
    mock = MockHermes(LangChainHarness())
    decision = await mock.send_message("hello", models=_models())
    assert decision.decision == DecisionType.LLM_CALL
    assert decision.llm_call is not None
    messages = decision.llm_call.messages
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0] == {"role": "user", "content": "hello"}
    assert all(isinstance(m, dict) and "role" in m and "content" in m for m in messages)


async def test_on_process_empty_models_returns_text():
    """GAP-028: with empty context.models the harness falls back to TEXT —
    never issues llm_call (battery test_5_8)."""
    mock = MockHermes(LangChainHarness())
    decision = await mock.send_message("hello")
    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.finished is True
    assert "No models available" in decision.text.content
    assert decision.llm_call is None


async def test_get_session_info_tracks_processed_sessions():
    """GAP-028: sessions are recorded on process; unknown ids return None so
    create_router 404s (battery test_5_9b/test_5_10)."""
    harness = LangChainHarness()
    mock = MockHermes(harness)
    await mock.send_message("hello", session_id="sess-lc", models=_models())
    info = harness.get_session_info("sess-lc")
    assert info is not None
    assert info["turn_count"] == 1
    assert info["started_at"]
    assert harness.get_session_info("sess-unknown") is None


async def test_on_result_llm_response_returns_text():
    """send_result with llm_response returns a TEXT decision with the LLM content."""
    mock = MockHermes(LangChainHarness())
    await mock.send_message("hello", models=_models())
    decision = await mock.send_result(
        {"type": "llm_response", "data": {"content": "hi there"}}
    )
    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.content == "hi there"
    assert decision.text.finished is True


async def test_on_result_text_sent_returns_end():
    """A second send_result (text_sent) finishes the session with END."""
    mock = MockHermes(LangChainHarness())
    await mock.send_message("hello", models=_models())
    await mock.send_result({"type": "llm_response", "data": {"content": "hi"}})
    decision = await mock.send_result({"type": "text_sent", "data": {}})
    assert decision.decision == DecisionType.END
    assert decision.end is not None


async def test_on_result_missing_data_is_tolerated():
    """send_result with llm_response but no data dict falls back to a placeholder."""
    mock = MockHermes(LangChainHarness())
    await mock.send_message("hello", models=_models())
    decision = await mock.send_result({"type": "llm_response"})
    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.content == "(no response from LLM)"
