# `h3_harness.middleware` — `add_middleware`

**Module:** `h3_harness.middleware` — re-exported at the top level via
`from h3_harness import add_middleware`.

---

## `add_middleware(app: FastAPI) -> None`

Attach request-logging middleware to a FastAPI application. The middleware is
a `BaseHTTPMiddleware` (`_RequestLoggingMiddleware`, private) that logs every
request and converts unhandled exceptions into a JSON 500 error response.

```python
from fastapi import FastAPI
from h3_harness import add_middleware, create_router

app = FastAPI()
app.include_router(create_router(MyHarness()))
add_middleware(app)
```

### What it logs

For every request, at `INFO` level on the `h3_harness` logger:

```
[<UTC ISO8601 timestamp>] <METHOD> <path> <status> <duration_ms>ms
```

Example: `[2026-08-04T12:00:00Z] POST /v1/process 200 12ms`

The timestamp is formatted `%Y-%m-%dT%H:%M:%SZ` in UTC.

### Error handling

If the wrapped handler raises, the middleware logs at `ERROR` level (same
format with status `500` and the exception appended) and returns a JSON 500
response built from the H3 error shape:

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "<exception text>"
  }
}
```

(`ErrorResponse(error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, ...))`.)

### Wiring notes

- **Call it on your app** — the middleware is attached manually. (The module
  docstring mentions `create_router()` calling it automatically "if an app
  reference is provided"; the current code does not do this —
  `create_router(harness, *, prefix="")` accepts no app argument. All shipped
  examples call `add_middleware(app)` explicitly.)
- **Call BEFORE adding routes** — per the function's docstring, middleware
  order matters: attach the middleware before `include_router` so it wraps the
  routes.
- The logger name is `h3_harness` — configure it with the standard
  `logging` module (`logging.getLogger("h3_harness")`) to control verbosity.
