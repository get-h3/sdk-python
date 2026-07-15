"""LangChain Agent Harness — H3 harness wrapping a LangChain agent/chain.

Demonstrates the full agent loop:
  - on_process    → LLM_CALL (delegate to a LangChain chain)
  - on_result     → TEXT (return the LLM response to the user)
  - on_result     → END  (finish the session after text is sent)

Run (requires LangChain):
    pip install langchain langchain-openai
    python src/h3_harness/examples/langchain_agent.py
    # → Server at http://0.0.0.0:8000
    #   GET  /v1/health  → harness health
    #   POST /v1/process → triggers the LangChain pipeline
"""

from __future__ import annotations

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
from h3_harness.protocol import LLMMessage


class LangChainHarness(BaseHarness):
    """H3 harness that delegates reasoning to a LangChain chain.

    Flow:
      1. on_process  → returns LLM_CALL with the user's message
      2. on_result   → (llm_response) formats the LLM output as TEXT
      3. on_result   → (text_sent) returns END to finish the session
    """

    def __init__(self):
        super().__init__()
        self._sent_text = False

    async def on_process(self, req):
        """Kick off the LangChain pipeline via an LLM_CALL."""
        # Convert the incoming Message to the LLMMessage format expected by Hermes
        llm_messages = [
            LLMMessage(role="user", content=req.message.content)
        ]
        # Include conversation history if available
        for entry in req.context.history:
            llm_messages.append(LLMMessage(role=entry.role, content=entry.content))

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
        )

    async def on_result(self, req):
        """Handle the result of the previous Decision.

        - llm_response → return the LLM's output as TEXT
        - text_sent    → finish the session with END
        - anything else → END (safety fallback)
        """
        result_type = req.result.type if req.result else None

        if result_type == ResultType.LLM_RESPONSE and not self._sent_text:
            # Extract the assistant's reply from the result data
            data = req.result.data or {}
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


# ── Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    app = FastAPI()
    app.include_router(create_router(LangChainHarness()))
    add_middleware(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)
