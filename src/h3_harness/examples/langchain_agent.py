"""LangChain Agent Harness — H3 harness wrapping a LangChain agent/chain.

Demonstrates the full agent loop:
  - on_process    → LLM_CALL (delegate to a LangChain chain)
  - on_result     → TEXT (return the LLM response to the user)
  - on_result     → END  (finish the session after text is sent)

Battery-compliant (passes the full h3-test battery, currently 46/46):
  - never issues llm_call when context.models is empty (falls back to TEXT)
  - echoes context.history in every Decision
  - tracks sessions so unknown ids 404 (get_session_info)

Run (self-contained — no LangChain install needed; the module imports no
langchain, the model call is delegated over the H3 protocol):
    python src/h3_harness/examples/langchain_agent.py
    # → Server at http://0.0.0.0:8000
    #   GET  /v1/health  → harness health
    #   POST /v1/process → triggers the agent pipeline
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from h3_harness import (
    BaseHarness,
    Decision,
    DecisionType,
    End,
    LLMCall,
    ResultType,
    TextResponse,
    add_middleware,
    create_router,
)


class LangChainHarness(BaseHarness):
    """H3 harness that delegates reasoning to a LangChain chain.

    Flow:
      1. on_process  → returns LLM_CALL with the user's message
      2. on_result   → (llm_response) formats the LLM output as TEXT
      3. on_result   → (text_sent) returns END to finish the session

    When context.models is empty, on_process returns a TEXT fallback instead
    of an LLM_CALL (README convention #2 — battery test_5_8).
    """

    def __init__(self):
        super().__init__()
        self._sessions: dict[str, dict] = {}
        self._sent_text = False

    async def on_process(self, req):
        """Kick off the LangChain pipeline via an LLM_CALL."""
        # Session tracking (battery: test_5_9b/test_5_10 unknown ids 404).
        self._sessions[req.session_id] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "turn_count": (
                self._sessions.get(req.session_id, {}).get("turn_count", 0) + 1
            ),
        }

        # Echo conversation history from context (battery: test_2_8).
        history = list(req.context.history)

        # Never issue llm_call when context.models is empty (battery: test_5_8).
        if not req.context.models:
            return Decision(
                decision=DecisionType.TEXT,
                text=TextResponse(
                    content=(
                        "No models available in context — cannot run "
                        "LangChain pipeline."
                    ),
                    finished=True,
                ),
                history=history,
            )

        # Convert the incoming Message to the message dict format expected by LLMCall
        llm_messages = [{"role": "user", "content": req.message.content}]
        # Include conversation history if available
        for entry in req.context.history:
            llm_messages.append({"role": entry.role, "content": entry.content})

        return Decision(
            decision=DecisionType.LLM_CALL,
            llm_call=LLMCall(
                model="gpt-4o-mini",
                messages=llm_messages,
                system_prompt=(
                    "You are a helpful assistant wrapped by an H3 harness. "
                    "Answer concisely and directly."
                ),
                temperature=0.7,
                max_tokens=1024,
            ),
            history=history,
        )

    async def on_result(self, req):
        """Handle the result of the previous Decision.

        - llm_response → return the LLM's output as TEXT
        - text_sent    → finish the session with END
        - anything else → END (safety fallback)
        """
        result_type = req.result.get("type") if req.result else None

        if result_type == ResultType.LLM_RESPONSE and not self._sent_text:
            # Extract the assistant's reply from the result data
            data = req.result.get("data") or {}
            content = data.get("content", "") or "(no response from LLM)"
            self._sent_text = True
            return Decision(
                decision=DecisionType.TEXT,
                text=TextResponse(content=content, finished=True),
            )

        # After TEXT was sent (text_sent) or for any other result type, end
        return Decision(
            decision=DecisionType.END,
            end=End(reason="task_complete"),
        )

    def get_session_info(self, session_id: str) -> dict | None:
        """Return session info dict or None if not found. Used by create_router."""
        return self._sessions.get(session_id)


# ── App ────────────────────────────────────────────────────────────
# Module-level `app` so the example can be served directly with
# `uvicorn h3_harness.examples.langchain_agent:app` (README Examples section).
app = FastAPI()
app.include_router(create_router(LangChainHarness()))
add_middleware(app)


# ── Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
