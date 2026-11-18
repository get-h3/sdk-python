# DF-H3-53 live repro — DELETE /v1/sessions answers terminated:false on a base no-op hook

Recorded 2026-11-18 (tick h3-foreman-2026-11-18-00-54-47, R2 worker + foreman).
This is the verbatim transcript of the acceptance criterion 1 reproduction on
the shipped router (this repo, post-fix commit 9e49efd / merged 716bb57).

Server: `.venv/bin/python -m uvicorn h3_harness.examples.minimal:app --host
127.0.0.1 --port 9191` — minimal.py is a `BaseHarness` with `get_session_info`
and NO `on_session_terminate` override (the no-op shape this criterion
targets). Port 9191 was free (`ss -tlnp` showed no listener).

Note: the row's literal curl body uses `"context":{}`, which 422s on the
current protocol — `Context` requires `config` and `session_state`. Both
replies recorded verbatim; the corrected body (only difference: the two
required keys) exercises the DELETE/GET the repro is about.

```
$ curl -s -X POST http://127.0.0.1:9191/v1/process -H 'Content-Type: application/json' -d '{"session_id":"repro-1","message":{"role":"user","content":"hello"},"identity":{"platform":"test","chat_id":"t"},"context":{}}'
{"detail":[{"type":"missing","loc":["body","context","config"],"msg":"Field required","input":{}},{"type":"missing","loc":["body","context","session_state"],"msg":"Field required","input":{}}]}

$ curl -s -X POST http://127.0.0.1:9191/v1/process -H 'Content-Type: application/json' -d '{"session_id":"repro-1","message":{"role":"user","content":"hello"},"identity":{"platform":"test","chat_id":"t"},"context":{"config":{},"session_state":{}}}'
{"decision":"text","decision_id":"f9f1a703-8b92-490d-996b-1e8ee876deca","history":[],"text":{"content":"Hello from minimal!","finished":true}}

$ curl -s -X DELETE http://127.0.0.1:9191/v1/sessions/repro-1
{"session_id":"repro-1","terminated":false}

$ curl -s http://127.0.0.1:9191/v1/sessions/repro-1
{"last_active":"","session_id":"repro-1","started_at":"2026-11-18T01:29:31.551104+00:00","status":"active","turn_count":1,"current_decision":null,"current_decision_type":null}
```

DELETE says `terminated:false` (not `true`); GET still returns the session with
live status `active`, not a fabricated `completed`. Server killed afterwards
(9191 released).

Override control (same protocol, TestClient in-process, from the R2 worker's
verification): a harness whose `on_session_terminate` forgets the session gets
`{"terminated": true}` and a later GET 404s — the documented override behaviour
is unchanged.

The battery accepts the honest claim: shim `test_5_14` passes a 200 DELETE
whose body says `terminated:false` ("honest no-teardown claim") and still fails
a pre-fix-shaped harness that answers `terminated:true` and stamps
`status:completed` (the no-op terminate).
