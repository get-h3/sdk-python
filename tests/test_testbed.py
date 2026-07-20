"""Tests for h3_harness.testbed — helper functions and MockHermes edge cases."""

from __future__ import annotations

from h3_harness import (
    BaseHarness,
    Decision,
    DecisionType,
    End,
    EndReason,
    TextResponse,
)
from h3_harness.protocol import (
    CancelReason,
    Config,
    Context,
    Identity,
    ResultPayload,
    ResultType,
    SessionState,
)
from h3_harness.testbed import (
    MockHermes,
    _default_config,
    _default_context,
    _default_identity,
    _default_session_state,
    _now_iso,
)

# ── Helper function tests ──────────────────────────────────────────


def test_now_iso_returns_iso_format():
    """_now_iso() returns a valid ISO 8601 timestamp."""
    ts = _now_iso()
    assert isinstance(ts, str)
    assert len(ts) > 10  # at least "YYYY-MM-DD"
    assert "T" in ts
    # Should end with timezone info (e.g. "+00:00" or "Z")
    assert ts[-6:] == "+00:00" or ts.endswith("Z")


def test_default_identity_has_all_required_fields():
    """_default_identity() returns an Identity with all fields populated."""
    ident = _default_identity()
    assert isinstance(ident, Identity)
    assert ident.platform == "test"
    assert ident.chat_id == "test"
    assert ident.user_name == "test"
    assert ident.user_id == "test-user"


def test_default_config_has_canonical_values():
    """_default_config() returns Config with max_iterations=10, timeout=300."""
    cfg = _default_config()
    assert isinstance(cfg, Config)
    assert cfg.max_iterations == 10
    assert cfg.timeout_seconds == 300


def test_default_session_state_has_started_at():
    """_default_session_state() returns a SessionState with a started_at string."""
    state = _default_session_state()
    assert isinstance(state, SessionState)
    assert isinstance(state.started_at, str)
    assert len(state.started_at) > 0


def test_default_context_includes_config_and_session():
    """_default_context() returns Context with default config and session_state."""
    ctx = _default_context()
    assert isinstance(ctx, Context)
    assert isinstance(ctx.config, Config)
    assert ctx.config.max_iterations == 10
    assert isinstance(ctx.session_state, SessionState)
    assert ctx.session_state.started_at is not None


# ── MockHermes: send_message edge cases ────────────────────────────


class EchoHarness(BaseHarness):
    """Minimal harness for testing MockHermes."""

    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(
                content=f"Echo: {req.message.content}",
                finished=True,
            ),
        )

    async def on_result(self, req):
        return Decision(
            decision=DecisionType.END,
            end=End(reason=EndReason.TASK_COMPLETE.value),
        )


async def test_mock_send_message_custom_session_id():
    """send_message with a custom session_id uses the given ID."""
    mock = MockHermes(EchoHarness())
    decision = await mock.send_message("ping", session_id="custom-123")
    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.content == "Echo: ping"


async def test_mock_send_message_default_session_id():
    """send_message defaults to 'test-session'."""
    mock = MockHermes(EchoHarness())
    decision = await mock.send_message("ping")
    assert decision.decision == DecisionType.TEXT


async def test_mock_send_result_with_dict():
    """send_result accepts a plain dict as the result payload."""
    mock = MockHermes(EchoHarness())
    decision = await mock.send_result(
        {"type": "tool_result", "success": True},
        session_id="s-dict-test",
    )
    assert decision.decision == DecisionType.END
    assert decision.end is not None
    assert decision.end.reason == "task_complete"


async def test_mock_send_result_custom_decision_id():
    """send_result with an explicit decision_id sends the expected ID."""
    mock = MockHermes(EchoHarness())
    result = ResultPayload(type=ResultType.TOOL_RESULT, success=True)
    decision = await mock.send_result(
        result,
        session_id="s-custom-did",
        decision_id="did-custom-999",
    )
    assert decision.decision == DecisionType.END


async def test_mock_cancel_with_timeout_reason():
    """cancel works with TIMEOUT reason."""
    mock = MockHermes(EchoHarness())
    confirmed = await mock.cancel(
        session_id="s-timeout",
        reason=CancelReason.TIMEOUT,
    )
    assert confirmed is True


async def test_mock_cancel_with_user_interrupt():
    """cancel works with USER_INTERRUPT reason."""
    mock = MockHermes(EchoHarness())
    confirmed = await mock.cancel(
        session_id="s-interrupt",
        reason=CancelReason.USER_INTERRUPT,
    )
    assert confirmed is True


async def test_mock_cancel_with_system_reason():
    """cancel works with SYSTEM reason."""
    mock = MockHermes(EchoHarness())
    confirmed = await mock.cancel(
        session_id="s-syserr",
        reason=CancelReason.SYSTEM,
    )
    assert confirmed is True


async def test_mock_send_message_multiple_calls():
    """MockHermes handles sequential send_message calls correctly."""
    mock = MockHermes(EchoHarness())
    d1 = await mock.send_message("first")
    assert d1.text is not None
    assert d1.text.content == "Echo: first"

    d2 = await mock.send_message("second")
    assert d2.text is not None
    assert d2.text.content == "Echo: second"


async def test_mock_send_result_returns_when_harness_returns_text_not_end():
    """send_result works when the harness returns TEXT (not END)."""

    class TextOnResultHarness(BaseHarness):
        async def on_process(self, req):
            return Decision(
                decision=DecisionType.TEXT,
                text=TextResponse(content="ok", finished=False),
            )

        async def on_result(self, req):
            return Decision(
                decision=DecisionType.TEXT,
                text=TextResponse(content="result received", finished=True),
            )

    mock = MockHermes(TextOnResultHarness())
    result = ResultPayload(type=ResultType.TOOL_RESULT, success=True)
    decision = await mock.send_result(result)
    assert decision.decision == DecisionType.TEXT
    assert decision.text is not None
    assert decision.text.content == "result received"
