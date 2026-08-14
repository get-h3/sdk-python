# `h3_harness.harness` — `BaseHarness` and `create_router`

**Module:** `h3_harness.harness` — re-exported at the top level via
`from h3_harness import BaseHarness, create_router`.

---

## `class BaseHarness(ABC)`

Abstract base class for H3-compliant agent harnesses.

Subclasses **must** implement `on_process` and `on_result`. `on_cancel`,
`on_session_terminate`, and `health` are optional overrides with working
defaults.

```python
class BaseHarness(ABC):
    _started_at: float = 0.0

    def __init__(self) -> None:
        self._started_at = time.time()
```

`__init__` records `self._started_at` (used by the default `health()` to
compute `uptime_seconds`). Call `super().__init__()` from subclasses that
define their own `__init__`.

### Methods

| Method | Kind | Signature | Returns |
|---|---|---|---|
| `on_process` | **abstract** | `async def on_process(self, req: ProcessRequest) -> Decision` | The first `Decision` of the agent loop |
| `on_result` | **abstract** | `async def on_result(self, req: ResultRequest) -> Decision` | The next `Decision` |
| `on_cancel` | optional override | `async def on_cancel(self, req: CancelRequest) -> bool` | `True` (base) |
| `on_session_terminate` | optional override | `async def on_session_terminate(self, session_id: str) -> None` | `None` (base, no-op) |
| `health` | optional override | `def health(self) -> HealthResponse` | Default health payload (below) |

### `on_process(req: ProcessRequest) -> Decision` — abstract

Called when a new user message arrives (`POST /v1/process`). Return the first
Decision in the agent loop.

### `on_result(req: ResultRequest) -> Decision` — abstract

Called after Hermes executes a Decision (`POST /v1/result`). Return the next
Decision. Return `Decision(decision=DecisionType.END, ...)` to finish the
session.

Note: `ResultRequest` carries only `decision_id`/`result`/`session_id` — there
is **no** `context` field, so decisions returned from `on_result` must omit
`history` (see README → convention #1).

### `on_cancel(req: CancelRequest) -> bool` — optional

Called when the user interrupts (`POST /v1/cancel`). Return `True` to confirm
cancellation. The base implementation always returns `True`.

### `on_session_terminate(session_id: str) -> None` — optional

Called on `DELETE /v1/sessions/{session_id}`. Override to perform cleanup when
a session is terminated. The base implementation is a no-op.

### `health() -> HealthResponse` — optional

Return harness health status; override for custom health logic. The base
implementation returns:

```python
HealthResponse(
    status=HealthStatus.OK,
    version="1.0.0",
    transport="rest",
    protocol_version="1.0",
    uptime_seconds=int(time.time() - self._started_at),
    capabilities=list(Capability),
)
```

### `get_session_info` — optional duck-typed method (not on the ABC)

`BaseHarness` does **not** declare `get_session_info`, but `create_router`
checks for it with `hasattr(harness, "get_session_info")`. If your harness
implements:

```python
def get_session_info(self, session_id: str) -> dict | None: ...
```

then `GET /v1/sessions/{session_id}` will return real session metadata. The
dict may contain keys `started_at`, `last_active`, and `turn_count` (used to
populate `SessionResponse`); returning `None` makes the router answer `404`.
Without this method, the router always reports the session as
`SessionStatus.ACTIVE` with empty timestamps and `turn_count=0`. See
`src/h3_harness/examples/echo.py` for a working implementation.

---

## `create_router(harness: BaseHarness, *, prefix: str = "") -> APIRouter`

Create a FastAPI router wired to the given harness, registering all H3
endpoints. `prefix` is prepended to every path (e.g. `prefix="/api"` yields
`/api/v1/health`).

```python
app = FastAPI()
app.include_router(create_router(MyHarness()))
# or with a prefix:
app.include_router(create_router(MyHarness(), prefix="/api"))
```

### Endpoint table

| Method | Path | Request body | Response |
|---|---|---|---|
| `GET` | `/v1/health` | — | `HealthResponse` |
| `POST` | `/v1/process` | `ProcessRequest` | `Decision` (serialized with `response_model_exclude_none=True`) |
| `POST` | `/v1/result` | `ResultRequest` | `Decision` (serialized with `response_model_exclude_none=True`) |
| `POST` | `/v1/cancel` | `CancelRequest` | `{"session_id": str, "cancelled": bool}` |
| `GET` | `/v1/sessions/{session_id}` | — | `SessionResponse` |
| `DELETE` | `/v1/sessions/{session_id}` | — | `{"session_id": str, "terminated": bool}` |

### Per-endpoint behavior

- **`GET /v1/health`** — returns `harness.health()`.
- **`POST /v1/process`** — calls `await harness.on_process(req)` and returns
  the Decision. If the harness method raises, the router logs
  `"on_process failed"` and returns `Decision(decision=DecisionType.END,
  end=End(reason=EndReason.ERROR, summary=str(exc)))` — i.e. an exception in
  your harness becomes an `end/error` decision, not a 500.
- **`POST /v1/result`** — same contract as `process`, calling
  `await harness.on_result(req)`; exceptions become an `end/error` Decision.
- **`POST /v1/cancel`** — calls `await harness.on_cancel(req)` and returns
  `{"session_id": req.session_id, "cancelled": confirmed}`. If
  `on_cancel` raises, the router logs `"on_cancel failed"` and raises
  `HTTPException(500, detail=str(exc))`.
- **`GET /v1/sessions/{session_id}`** — uses `harness.get_session_info` if
  present (see above); `404 "Session not found"` when it returns `None`;
  otherwise a default `SessionResponse` with `SessionStatus.ACTIVE`.
- **`DELETE /v1/sessions/{session_id}`** — calls
  `await harness.on_session_terminate(session_id)` and returns
  `{"session_id": session_id, "terminated": True}`. If the hook raises, the
  router logs and raises `HTTPException(500, detail=str(exc))`.

### Agent-loop lifecycle

1. Hermes sends `POST /v1/process` → `on_process` returns the first Decision.
2. Hermes executes it (tool call, LLM call, text, wait, delegate) and sends
   `POST /v1/result` → `on_result` returns the next Decision.
3. The loop repeats until a Decision with `decision=DecisionType.END` is
   returned (or the request limit in `Context.config.max_iterations` is hit).
4. At any point the user can interrupt: `POST /v1/cancel` →
   `on_cancel(req)`.
5. Session lifecycle: `GET /v1/sessions/{session_id}` for metadata,
   `DELETE /v1/sessions/{session_id}` for termination cleanup.
