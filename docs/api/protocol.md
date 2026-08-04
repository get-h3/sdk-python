# `h3_harness.protocol` — Protocol Types

Pydantic models and enums of the H3 v1 protocol, generated from the
`get-h3/protocol` JSON Schema (`schemas/v1/*.json`). All models are
`pydantic.BaseModel` subclasses; all enums are `str, Enum` subclasses (their
values serialize to the plain strings shown below).

**Module:** `h3_harness.protocol`

**Top-level exports:** 21 of the 33 types below are re-exported from
`h3_harness` (see [index.md](index.md)). The remaining 12 — marked
*not re-exported* — are still public API and are imported directly from
`h3_harness.protocol`:

```python
from h3_harness.protocol import Context, Message, Identity, Capability, ...
```

---

## Enums

### `DecisionType` *(re-exported)*

Which kind of `Decision` a harness is returning. The matching payload field
(`tool_call`, `llm_call`, `text`, `wait`, `delegate`, `end`) carries the
details.

| Member | Value |
|---|---|
| `TOOL_CALL` | `"tool_call"` |
| `LLM_CALL` | `"llm_call"` |
| `TEXT` | `"text"` |
| `WAIT` | `"wait"` |
| `DELEGATE` | `"delegate"` |
| `END` | `"end"` |

### `EndReason` *(re-exported)*

Why a session ended. Used in `End.reason`.

| Member | Value |
|---|---|
| `TASK_COMPLETE` | `"task_complete"` |
| `USER_REQUESTED` | `"user_requested"` |
| `ERROR` | `"error"` |
| `TIMEOUT` | `"timeout"` |
| `RATE_LIMITED` | `"rate_limited"` |
| `CANCELLED` | `"cancelled"` |

### `HealthStatus` *(re-exported)*

Harness health state, reported by `GET /v1/health`.

| Member | Value |
|---|---|
| `OK` | `"ok"` |
| `DEGRADED` | `"degraded"` |
| `DOWN` | `"down"` |

### `Capability` *(not re-exported)*

A capability a harness advertises in `HealthResponse.capabilities`. Mirrors
`DecisionType`'s member set. Used by `BaseHarness.health()` (the default
implementation advertises `list(Capability)`).

| Member | Value |
|---|---|
| `TOOL_CALL` | `"tool_call"` |
| `LLM_CALL` | `"llm_call"` |
| `TEXT` | `"text"` |
| `WAIT` | `"wait"` |
| `DELEGATE` | `"delegate"` |
| `END` | `"end"` |

### `CancelReason` *(re-exported)*

Why a session is being cancelled, sent in `CancelRequest.reason`.

| Member | Value |
|---|---|
| `USER_INTERRUPT` | `"user_interrupt"` |
| `TIMEOUT` | `"timeout"` |
| `SYSTEM` | `"system"` |

### `ResultType` *(re-exported)*

What kind of result Hermes is reporting back in a `ResultPayload`. Note this
is a documentation enum: `ResultPayload.type` is a plain `str` field, so the
enum members are the canonical string values.

| Member | Value |
|---|---|
| `TOOL_RESULT` | `"tool_result"` |
| `LLM_RESPONSE` | `"llm_response"` |
| `TEXT_SENT` | `"text_sent"` |
| `DELEGATE_RESULT` | `"delegate_result"` |
| `WAIT_TIMEOUT` | `"wait_timeout"` |
| `ERROR` | `"error"` |

### `ErrorCode` *(re-exported)*

Machine-readable error codes used in `ErrorDetail.code` and by the built-in
error responses (`middleware.py`, `harness.py` internal helpers).

| Member | Value |
|---|---|
| `INVALID_REQUEST` | `"INVALID_REQUEST"` |
| `INVALID_DECISION` | `"INVALID_DECISION"` |
| `UNKNOWN_TOOL` | `"UNKNOWN_TOOL"` |
| `UNKNOWN_MODEL` | `"UNKNOWN_MODEL"` |
| `SESSION_NOT_FOUND` | `"SESSION_NOT_FOUND"` |
| `SESSION_EXPIRED` | `"SESSION_EXPIRED"` |
| `HARNESS_TIMEOUT` | `"HARNESS_TIMEOUT"` |
| `INTERNAL_ERROR` | `"INTERNAL_ERROR"` |

### `SessionStatus` *(re-exported)*

Lifecycle state of a session, reported in `SessionResponse.status`.

| Member | Value |
|---|---|
| `ACTIVE` | `"active"` |
| `COMPLETED` | `"completed"` |
| `EXPIRED` | `"expired"` |
| `CANCELLED` | `"cancelled"` |

---

## Request / Response models

### `ProcessRequest` *(re-exported)*

Request body for `POST /v1/process` — a new user message triggers the harness
agent loop.

| Field | Type | Default | Description |
|---|---|---|---|
| `context` | `Context` | required | Conversation state: config, history, models, tools, session state. |
| `identity` | `Identity` | required | Who is talking to the harness. |
| `message` | `Message` | required | The new user message. |
| `session_id` | `str` | required | Stable session identifier. |

### `ResultRequest` *(re-exported)*

Request body for `POST /v1/result` — the execution result of a previously
returned Decision.

| Field | Type | Default | Description |
|---|---|---|---|
| `decision_id` | `str` | required | ID of the Decision this result belongs to. |
| `result` | `dict[str, Any]` | required | Raw result payload (see `ResultPayload` for the canonical shape). |
| `session_id` | `str` | required | Session the decision ran in. |

### `CancelRequest` *(re-exported)*

Request body for `POST /v1/cancel` — cancel an in-flight operation.

| Field | Type | Default | Description |
|---|---|---|---|
| `reason` | `str` | required | Why the cancellation was requested (see `CancelReason` for canonical values). |
| `session_id` | `str` | required | Session to cancel. |

### `HealthResponse` *(re-exported)*

Response from `GET /v1/health` — harness health status.

| Field | Type | Default | Description |
|---|---|---|---|
| `status` | `str` | required | `"ok"`, `"degraded"`, or `"down"` (see `HealthStatus`). |
| `version` | `str` | required | Harness version. |
| `active_sessions` | `int \| None` | `None` | Number of active sessions, if tracked. |
| `capabilities` | `list[str] \| None` | `None` | Advertised capabilities (see `Capability`). |
| `degraded_reason` | `str \| None` | `None` | Why the harness is degraded. |
| `error` | `str \| None` | `None` | Error detail if unhealthy. |
| `protocol_version` | `str \| None` | `None` | H3 protocol version implemented. |
| `transport` | `str \| None` | `None` | Transport in use (e.g. `"rest"`). |
| `uptime_seconds` | `int \| None` | `None` | Seconds since the harness started. |

### `ErrorResponse` *(re-exported)*

Standard error response for H3 endpoints.

| Field | Type | Default | Description |
|---|---|---|---|
| `error` | `dict[str, Any]` | required | Error object; serialized `ErrorDetail` (`code`, `message`, optional `field`). |

### `SessionResponse` *(re-exported)*

Response from `GET /v1/sessions/{session_id}` — session metadata.

| Field | Type | Default | Description |
|---|---|---|---|
| `last_active` | `str` | required | ISO timestamp of last activity. |
| `session_id` | `str` | required | Session identifier. |
| `started_at` | `str` | required | ISO timestamp when the session started. |
| `status` | `str` | required | Session status (see `SessionStatus`). |
| `turn_count` | `int` | required | Number of turns so far. |
| `current_decision` | `str \| None` | `None` | ID of the current decision, if any. |
| `current_decision_type` | `str \| None` | `None` | Type of the current decision, if any. |

### `Decision` *(re-exported)*

Top-level decision object sent from the harness to Hermes. `decision` selects
which payload field is valid; the matching sub-model should be populated.

| Field | Type | Default | Description |
|---|---|---|---|
| `decision` | `DecisionType` | required | Kind of decision. |
| `decision_id` | `str` | auto `uuid4()` | Unique decision ID, generated if omitted. |
| `history` | `list[HistoryEntry]` | `[]` | Conversation history to carry forward. **The h3-test battery requires echoing `context.history` here.** |
| `tool_call` | `ToolCall \| None` | `None` | Set when `decision == DecisionType.TOOL_CALL`. |
| `llm_call` | `LLMCall \| None` | `None` | Set when `decision == DecisionType.LLM_CALL`. |
| `text` | `TextResponse \| None` | `None` | Set when `decision == DecisionType.TEXT`. |
| `wait` | `Wait \| None` | `None` | Set when `decision == DecisionType.WAIT`. |
| `delegate` | `Delegate \| None` | `None` | Set when `decision == DecisionType.DELEGATE`. |
| `end` | `End \| None` | `None` | Set when `decision == DecisionType.END`. |

---

## Decision payloads

### `ToolCall` *(re-exported)*

Decision to execute a Hermes tool.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | Tool name. |
| `params` | `dict[str, Any]` | required | Tool arguments. |
| `reasoning` | `str \| None` | `None` | Reasoning behind the call. |

### `LLMCall` *(re-exported)*

Decision to run an LLM prompt.

| Field | Type | Default | Description |
|---|---|---|---|
| `messages` | `list[dict[str, Any]]` | required | Chat messages (`{"role": ..., "content": ...}` dicts). |
| `model` | `str` | required | Model identifier. |
| `max_tokens` | `int \| None` | `None` | Output token cap. |
| `system_prompt` | `str \| None` | `None` | System prompt for the call. |
| `temperature` | `float \| None` | `None` | Sampling temperature. |

### `TextResponse` *(re-exported)*

Decision to send text to the user.

| Field | Type | Default | Description |
|---|---|---|---|
| `content` | `str` | required | Text to send. |
| `finished` | `bool` | required | Whether this text finishes the turn. **The battery requires `finished=False` for "do not finish" prompts.** |

### `Wait` *(re-exported)*

Decision to pause for an external signal.

| Field | Type | Default | Description |
|---|---|---|---|
| `reason` | `str` | required | Why the harness is waiting. |
| `duration_seconds` | `int \| None` | `None` | Suggested wait time; if set, must be ≥ 1 (pydantic `ge=1`). |
| `poll_endpoint` | `str \| None` | `None` | Endpoint Hermes can poll for completion. |

### `Delegate` *(re-exported)*

Decision to spawn a sub-agent.

| Field | Type | Default | Description |
|---|---|---|---|
| `task` | `str` | required | Task description for the sub-agent. |
| `agent` | `str \| None` | `None` | Agent to delegate to. |
| `context` | `str \| None` | `None` | Context to pass along. |
| `model` | `str \| None` | `None` | Model for the sub-agent. |
| `provider` | `str \| None` | `None` | Provider for the sub-agent. |

### `End` *(re-exported)*

Decision to terminate the session.

| Field | Type | Default | Description |
|---|---|---|---|
| `reason` | `str` | required | Why the session ends (see `EndReason` for canonical values). |
| `summary` | `str \| None` | `None` | Optional session summary. |

### `LLMMessage` *(not re-exported)*

Single message in an LLM conversation. (`LLMCall.messages` uses plain dicts,
not this model.)

| Field | Type | Default | Description |
|---|---|---|---|
| `role` | `str` | required | Message role (`"user"`, `"assistant"`, …). |
| `content` | `str` | required | Message content. |

### `ErrorDetail` *(not re-exported)*

Detailed error information.

| Field | Type | Default | Description |
|---|---|---|---|
| `field` | `str \| None` | `None` | Field the error relates to, if any. |
| `message` | `str` | required | Human-readable error message. |
| `code` | `str \| None` | `None` | Machine-readable code (see `ErrorCode`). |

### `ResultPayload` *(re-exported)*

Payload for a result returned to the harness (the canonical shape of the
`ResultRequest.result` dict).

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `str` | required | Result kind (see `ResultType` for canonical values). |
| `success` | `bool` | required | Whether the operation succeeded. |
| `tool_name` | `str \| None` | `None` | Tool that produced the result, for tool results. |
| `data` | `dict[str, Any] \| None` | `None` | Result data. |
| `duration_ms` | `int \| None` | `None` | Execution duration; if set, must be ≥ 0 (pydantic `ge=0`). |

---

## Common types

### `Attachment` *(not re-exported)*

| Field | Type | Default | Description |
|---|---|---|---|
| `mime_type` | `str` | required | MIME type of the attachment. |
| `type` | `str` | required | Attachment kind. |
| `url` | `str` | required | Where the attachment is hosted. |

### `Message` *(not re-exported)*

A user message, carried in `ProcessRequest.message`.

| Field | Type | Default | Description |
|---|---|---|---|
| `content` | `str` | required | Message text. |
| `role` | `str` | `"user"` | Message role. |
| `timestamp` | `str \| None` | `None` | ISO timestamp of the message. |
| `attachments` | `list[Attachment] \| None` | `None` | Attachments, if any. |

### `Identity` *(not re-exported)*

Who is talking to the harness, carried in `ProcessRequest.identity`.

| Field | Type | Default | Description |
|---|---|---|---|
| `chat_id` | `str` | required | Chat identifier on the platform. |
| `platform` | `str` | required | Platform name (e.g. `"test"`, `"telegram"`). |
| `user_id` | `str \| None` | `None` | Platform user ID. |
| `user_name` | `str \| None` | `None` | Display name. |
| `thread_id` | `str \| None` | `None` | Thread within the chat, if any. |

### `HistoryEntry` *(not re-exported)*

One entry of conversation history, used in `Context.history` and
`Decision.history`.

| Field | Type | Default | Description |
|---|---|---|---|
| `content` | `str` | required | Message text. |
| `role` | `str` | required | Message role. |

### `Tool` *(not re-exported)*

Tool description, carried in `Context.tools`.

| Field | Type | Default | Description |
|---|---|---|---|
| `description` | `str` | required | What the tool does. |
| `name` | `str` | required | Tool name. |
| `parameters` | `dict[str, Any]` | required | JSON Schema of the tool's parameters. |

### `Model` *(not re-exported)*

Model description, carried in `Context.models`. **The battery fails harnesses
that issue `llm_call` when `Context.models` is empty.**

| Field | Type | Default | Description |
|---|---|---|---|
| `context_window` | `int` | required | Context window size in tokens. |
| `name` | `str` | required | Model name. |
| `provider` | `str` | required | Model provider. |
| `cost_per_1k_input` | `float \| None` | `None` | Cost per 1k input tokens. |
| `cost_per_1k_output` | `float \| None` | `None` | Cost per 1k output tokens. |
| `supports_tool_calling` | `bool \| None` | `None` | Whether the model supports tool calling. |
| `supports_vision` | `bool \| None` | `None` | Whether the model supports vision input. |

### `SessionState` *(not re-exported)*

Per-session counters, carried in `Context.session_state`.

| Field | Type | Default | Description |
|---|---|---|---|
| `cost_so_far` | `float` | `0.0` | Accumulated cost. |
| `started_at` | `str \| None` | `None` | ISO timestamp of session start. |
| `total_llm_calls` | `int` | `0` | LLM calls so far. |
| `total_tool_calls` | `int` | `0` | Tool calls so far. |
| `turn_count` | `int` | `0` | Turns so far. |

### `Config` *(not re-exported)*

Harness configuration, carried in `Context.config`.

| Field | Type | Default | Description |
|---|---|---|---|
| `max_iterations` | `int \| None` | `None` | Cap on agent-loop iterations. |
| `timeout_seconds` | `int` | `300` | Request timeout. |
| `max_tool_calls_per_turn` | `int \| None` | `None` | Cap on tool calls per turn. |
| `project_dir` | `str \| None` | `None` | Working directory for the session. |
| `temperature` | `float \| None` | `None` | Default sampling temperature. |

### `Context` *(not re-exported)*

Full conversation context, carried in `ProcessRequest.context`. Required
fields must be present; list fields default to empty.

| Field | Type | Default | Description |
|---|---|---|---|
| `config` | `Config` | required | Harness configuration. |
| `history` | `list[HistoryEntry]` | `[]` | Conversation history. |
| `models` | `list[Model]` | `[]` | Models available to the harness. |
| `session_state` | `SessionState` | required | Session counters. |
| `tools` | `list[Tool]` | `[]` | Tools available to the harness. |
| `memory` | `str \| None` | `None` | Persistent memory blob, if any. |
| `skills` | `list[str] \| None` | `None` | Skill names available, if any. |
