"""Performance benchmarks for H3 Python SDK hot paths (pytest-benchmark).

Run with:
    pytest tests/test_benchmarks.py --benchmark-only

Covers: Pydantic model construction/validation, JSON serialization,
FastAPI router round-trips (process, health), request-logging middleware,
and MockHermes round-trips. Small rounds configured in pyproject.toml
(benchmark_min_rounds = 3, benchmark_max_time = 0.5) so the suite stays
snappy enough to run in CI on every change.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from h3_harness.harness import BaseHarness, create_router
from h3_harness.middleware import add_middleware
from h3_harness.protocol import (
    Decision,
    DecisionType,
    End,
    EndReason,
    ProcessRequest,
    TextResponse,
)
from h3_harness.testbed import MockHermes

pytest.importorskip("pytest_benchmark")


class EchoHarness(BaseHarness):
    """Minimal harness that echoes messages and ends on result."""

    async def on_process(self, req):
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content=f"Echo: {req.message.content}", finished=True),
        )

    async def on_result(self, req):
        return Decision(
            decision=DecisionType.END,
            end=End(reason=EndReason.TASK_COMPLETE.value),
        )


# ── Shared payloads ─────────────────────────────────────────────────


def _process_body() -> dict:
    """Realistic ProcessRequest payload: message, identity, context.

    Includes nested config/session_state, history, models, tools, memory,
    and skills so construction exercises the full model graph.
    """
    return {
        "session_id": "s-bench-1",
        "message": {
            "content": "Please analyze the attached files and summarize the findings.",
            "role": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "attachments": [
                {
                    "mime_type": "text/plain",
                    "type": "file",
                    "url": "https://example.com/spec.txt",
                },
                {
                    "mime_type": "image/png",
                    "type": "image",
                    "url": "https://example.com/diagram.png",
                },
            ],
        },
        "identity": {
            "platform": "slack",
            "chat_id": "C0123456789",
            "user_id": "U9876543210",
            "user_name": "bench-user",
            "thread_id": "t-42",
        },
        "context": {
            "config": {
                "max_iterations": 10,
                "timeout_seconds": 300,
                "temperature": 0.7,
            },
            "history": [
                {"role": "user", "content": "What can you do?"},
                {"role": "assistant", "content": "I can help you build H3 harnesses."},
                {"role": "user", "content": "Show me an example."},
            ],
            "models": [
                {
                    "name": "gpt-4o",
                    "provider": "openai",
                    "context_window": 128000,
                    "supports_tool_calling": True,
                },
                {
                    "name": "claude-3-5-sonnet",
                    "provider": "anthropic",
                    "context_window": 200000,
                    "supports_tool_calling": True,
                },
            ],
            "session_state": {
                "cost_so_far": 1.2345,
                "started_at": "2025-01-01T00:00:00Z",
                "total_llm_calls": 12,
                "total_tool_calls": 4,
                "turn_count": 7,
            },
            "tools": [
                {
                    "name": "web_search",
                    "description": "Search the web",
                    "parameters": {"max_results": 5},
                },
                {
                    "name": "read_file",
                    "description": "Read a file from disk",
                    "parameters": {"path": "string"},
                },
            ],
            "memory": "User prefers concise technical answers.",
            "skills": ["coding", "research"],
        },
    }


def _decision() -> Decision:
    """Populated TEXT decision."""
    return Decision(
        decision=DecisionType.TEXT,
        text=TextResponse(content="Echo: benchmark message", finished=True),
    )


# Apps/clients are built once at module level so benchmark timing measures
# the request path only, not app construction.
_APP = FastAPI()
_APP.include_router(create_router(EchoHarness()))
_CLIENT = TestClient(_APP)

_MIDDLEWARE_APP = FastAPI()
add_middleware(_MIDDLEWARE_APP)  # before routes, per the middleware contract
_MIDDLEWARE_APP.include_router(create_router(EchoHarness()))
_MIDDLEWARE_CLIENT = TestClient(_MIDDLEWARE_APP)


# ── Pydantic construction & validation ─────────────────────────────


def test_bench_process_request_construction(benchmark):
    """ProcessRequest(**payload) — nested model construction from a JSON dict."""

    def _construct() -> ProcessRequest:
        return ProcessRequest(**_process_body())

    benchmark(_construct)


def test_bench_decision_validation(benchmark):
    """Decision(decision=TEXT, text=TextResponse(...)) — nested validation."""

    def _validate() -> Decision:
        return Decision(
            decision=DecisionType.TEXT,
            text=TextResponse(content="benchmark reply", finished=True),
        )

    benchmark(_validate)


# ── JSON serialization ─────────────────────────────────────────────


def test_bench_process_request_serialization(benchmark):
    """model_dump(mode="json") on a populated ProcessRequest."""
    req = ProcessRequest(**_process_body())
    benchmark(req.model_dump, mode="json")


def test_bench_decision_serialization(benchmark):
    """model_dump(mode="json") on a populated Decision."""
    benchmark(_decision().model_dump, mode="json")


# ── FastAPI router round-trips ─────────────────────────────────────


def test_bench_router_process_roundtrip(benchmark):
    """TestClient POST /v1/process through the EchoHarness router."""
    body = _process_body()

    def _roundtrip():
        r = _CLIENT.post("/v1/process", json=body)
        assert r.status_code == 200
        return r

    benchmark(_roundtrip)


def test_bench_router_health_roundtrip(benchmark):
    """TestClient GET /v1/health round-trip."""

    def _roundtrip():
        r = _CLIENT.get("/v1/health")
        assert r.status_code == 200
        return r

    benchmark(_roundtrip)


def test_bench_router_process_roundtrip_with_middleware(benchmark):
    """POST /v1/process round-trip with request-logging middleware attached."""
    body = _process_body()

    def _roundtrip():
        r = _MIDDLEWARE_CLIENT.post("/v1/process", json=body)
        assert r.status_code == 200
        return r

    benchmark(_roundtrip)


# ── MockHermes round-trip ──────────────────────────────────────────


def test_bench_mockhermes_roundtrip(benchmark):
    """MockHermes.send_message("hello") through a real harness.

    pytest-benchmark has no native coroutine support (it would time
    coroutine creation, not execution), so the async call is driven on a
    dedicated event loop; each timed call awaits the full round trip.
    """
    mock = MockHermes(EchoHarness())
    loop = asyncio.new_event_loop()
    try:

        def _roundtrip() -> Decision:
            return loop.run_until_complete(mock.send_message("hello"))

        decision = benchmark(_roundtrip)
        assert decision.decision == DecisionType.TEXT
        assert decision.text is not None
        assert decision.text.content == "Echo: hello"
    finally:
        loop.close()
