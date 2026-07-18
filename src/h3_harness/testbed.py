"""H3 Testbed — MockHermes for testing harnesses without a running Hermes Core.

Usage:
    from h3_harness.testbed import MockHermes

    mock = MockHermes(my_harness)
    decision = await mock.send_message("Hello!")
    assert decision.decision == DecisionType.TEXT
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .harness import BaseHarness
from .protocol import (
    CancelReason,
    CancelRequest,
    Config,
    Context,
    Decision,
    Identity,
    Message,
    ProcessRequest,
    ResultPayload,
    ResultRequest,
    SessionState,
)


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _default_identity() -> Identity:
    """Minimal valid Identity for testing."""
    return Identity(
        platform="test",
        chat_id="test",
        user_name="test",
        user_id="test-user",
    )


def _default_config() -> Config:
    """Canonical minimal Config: 10 iterations, 300 s timeout."""
    return Config(max_iterations=10, timeout_seconds=300)


def _default_session_state() -> SessionState:
    """Fresh SessionState with a started_at timestamp."""
    return SessionState(started_at=_now_iso())


def _default_context() -> Context:
    """Minimal valid Context with config and session_state."""
    return Context(
        config=_default_config(),
        session_state=_default_session_state(),
    )


class MockHermes:
    """Simulate Hermes Core for testing H3-compliant harnesses.

    Wraps a BaseHarness instance and provides convenience methods that
    build protocol-correct requests and return the harness's Decision.
    """

    def __init__(self, harness: BaseHarness) -> None:
        self.harness = harness

    async def send_message(
        self,
        content: str,
        *,
        session_id: str = "test-session",
    ) -> Decision:
        """Send a user message to the harness → return its Decision."""
        req = ProcessRequest(
            session_id=session_id,
            message=Message(content=content, timestamp=_now_iso()),
            identity=_default_identity(),
            context=_default_context(),
        )
        return await self.harness.on_process(req)

    async def send_result(
        self,
        result: ResultPayload,
        *,
        session_id: str = "test-session",
        decision_id: str | None = None,
    ) -> Decision:
        """Send a result back to the harness → return its next Decision.

        If decision_id is not provided, a UUID is auto-generated.
        """
        req = ResultRequest(
            session_id=session_id,
            decision_id=decision_id or str(uuid4()),
            result=result if isinstance(result, dict) else result.model_dump(),
        )
        return await self.harness.on_result(req)

    async def cancel(
        self,
        session_id: str = "test-session",
        reason: CancelReason = CancelReason.USER_INTERRUPT,
    ) -> bool:
        """Send a cancel request → return whether the harness confirmed."""
        req = CancelRequest(session_id=session_id, reason=reason)
        return await self.harness.on_cancel(req)
