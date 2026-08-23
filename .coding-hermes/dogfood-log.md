# Dogfood Log — h3-sdk-python

Real-use field tests of this SDK, run by the coding-hermes-dogfood loop.

---

## 2026-08-03 — ✅ PROMISING-BUT-ROUGH (value real, install path broken)

**Verdict:** 🟡 PROMISING-BUT-ROUGH — the protocol engine is excellent (43/43 battery
with a consumer harness), but a real user cannot install the package today.

**Promise statement:** "A Python developer can `pip install h3-harness-sdk`, subclass
`BaseHarness` + `create_router()`, and ship an H3-compliant harness that passes the
43-test `h3-test` battery."

**Reality:** Install is broken twice over — package absent from PyPI (DF-002) AND the
built wheel omits `__init__.py` (DF-001) so `from h3_harness import BaseHarness` fails
on any non-editable install. The shipped langchain example also crashes (DF-003). Once
installed editable, the SDK itself is excellent: a from-scratch consumer harness
(TodoBrain, exercising tool_call/llm_call/text/end + sessions) passed the official
43/43 `h3-test` battery and the full Hermes loop worked flawlessly over HTTP.

**Top 3 findings:**
1. P0 — wheel missing `__init__.py`; root cause: `.gitignore` `_*.py` pattern applied
   by hatchling to wheel file selection; fix `/_*.py` verified. (DF-001)
2. P0 — not on PyPI; documented install command dead. (DF-002)
3. P1 — langchain_agent.py example crashes (LLMMessage vs dict). (DF-003)

**Time-to-first-success:** ~20 min (editable install + import + server up). With the
documented path: FAILED (never succeeds).

**Friction count:** 8 (PyPI fail, wheel/import fail, langchain example fail ×2 bugs,
3 undocumented battery conventions, SessionResponse empty timestamps).

**Evidence:** `/tmp/dogfood-h3-sdk/` (consumer project, TodoBrain v3, battery JSONs).
Full report: `docs/dogfood/2026-08-03-integration.md`, `docs/dogfood/diagnostics.md`.

---

## 2026-08-13 — 🟡 PROMISING-BUT-ROUGH (core promise holds; published wheel stale)

**Verdict:** 🟡 PROMISING-BUT-ROUGH — install works, full loop works, 44/44 battery
from a from-scratch harness, but the PyPI artifact users actually install is 2-3
weeks behind repo HEAD: four board-✅ fixes are live-missing on 0.1.2.

**Promise statement:** "A Python developer can `pip install h3-harness-sdk`
(PyPI 0.1.2), subclass `BaseHarness`, mount `create_router()` on FastAPI, run
uvicorn, and ship an H3-compliant harness that passes the 44-test h3-test battery."

**Reality:** Holds end-to-end — fresh-venv PyPI install OK (0.1.2), ConvertBrain
(from-scratch tool-calling harness: process→llm_call→tool_call→text→end) passed
44/44 h3-test exit 0, MockHermes loop PASS, README quickstart + testbed snippets
runnable verbatim. BUT the published wheel is stale: GAP-019 (DELETE unknown
session 404), GAP-025 (uptime epoch), GAP-029 (health version), MockHermes
`models=` kwarg are all fixed in repo and MISSING on PyPI 0.1.2 (GAP-032).
README convention #1 (echo history "in every Decision") is impossible in
on_result (ResultRequest has no context — GAP-033). Handler exceptions are
masked as HTTP 200 end/error (GAP-034).

**Top 3 findings:**
1. P1 — PyPI 0.1.2 wheel stale vs repo HEAD; 4 shipped fixes live-missing;
   verbatim README quickstart shows epoch uptime on the published package. (GAP-032)
2. P2 — "Echo context.history in every Decision" impossible in on_result;
   doc-following user crashes on first /v1/result. (GAP-033)
3. P2 — Handler exceptions silently masked as HTTP 200 end/error. (GAP-034)

**Time-to-first-success:** ~2 min (pip install 30s + import + uvicorn up). Full
loop incl. battery: ~15 min.

**Friction count:** 5 (ResultRequest no-context crash [GAP-033], 200-masked
exceptions ×2 [GAP-034], tool_calls-list handling undocumented, MockHermes
models kwarg TypeError on 0.1.2 [GAP-032d], DELETE-unknown 200 vs cancel/GET 404
[GAP-032a]).

**Evidence:** `/tmp/dogfood-h3sdk-0813/` (consumer project: convert_brain.py,
drive_loop.py, battery JSON). Full report:
`docs/dogfood/2026-08-13-integration.md`, `docs/dogfood/diagnostics.md` §6.

---

## 2026-08-23 — 🟡 PROMISING-BUT-ROUGH (core promise holds on the released artifact; wheel content-stale)

**Verdict:** 🟡 PROMISING-BUT-ROUGH — the full promise now HOLDS on the published
package (fresh-venv PyPI 0.1.3: install, verbatim quickstart, verbatim testbed,
from-scratch tool-calling harness, 44/44 battery), but the published 0.1.3 wheel
is **content-stale vs repo HEAD**: GAP-035's session-status pass-through is
missing from the wheel (uploaded 08-13T19:18-0500; commit 1098bf1 landed
08-13T19:21-0500 — 3 minutes later, never re-published). Same disease GAP-032
diagnosed, one level deeper: the release-readiness CI gate compares version
numbers only, so same-version content drift sails through green.

**Promise statement:** "A Python developer can `pip install h3-harness-sdk`
(PyPI), subclass `BaseHarness`, mount `create_router()` on FastAPI, run uvicorn,
and ship an H3-compliant harness that passes the 44-test h3-test battery."

**Reality:** Holds end-to-end — install OK (0.1.3, 2s), verbatim README
quickstart runs (health version=0.1.3, uptime sane, DELETE/GET/cancel unknown →
404, streaming finished=false, ISO session timestamps), verbatim Testbed snippet
exit 0, TaskBrain (from-scratch task-manager harness: process→tool_call→result
→text→end + llm_call path + tool_calls list handling) passed **44/44 h3-test
exit 0** (0.26s). BUT: (1) session status never reaches "completed" on the wire
— installed wheel hardcodes `SessionStatus.ACTIVE` (GAP-043); (2) DELETE
/v1/sessions/{id} says terminated:true yet the session stays fully retrievable
(base on_session_terminate no-op; quickstart/echo never override — GAP-044);
(3) the battery is blind to session-status emission, so 44/44 green-lights the
stale wheel (GAP-045).

**Top 3 findings:**
1. P1 — Published 0.1.3 wheel content-stale: GAP-035 status pass-through
   missing; release gate compares versions not content. (GAP-043)
2. P2 — DELETE terminates nothing: session survives termination for every
   quickstart/echo user. (GAP-044)
3. P3 — Battery has no session-status assertion; 44/44 passes against a wheel
   that can never emit COMPLETED. (GAP-045)

**Time-to-first-success:** ~2 min (pip install 30s + import + uvicorn up).
Full loop incl. battery: ~15 min.

**Friction count:** 4 (wheel-missing GAP-035 — had to diff wheel vs repo source
to explain status:"active"; DELETE-then-GET 200 surprise; had to read protocol.py
for Decision/ToolCall field names [no field docs in README, docs/api exists but
not linked inline]; shim still not on PyPI — documented fallback works).

**Evidence:** `/tmp/dogfood-h3sdk-0823/` (consumer project: taskbrain.py,
drive_loop.py, quickstart_harness.py, testbed_snippet.py, uvicorn logs).
Full report: `docs/dogfood/2026-08-23-integration.md`,
`docs/dogfood/diagnostics.md` §7. Board: GAP-043..045 written (JSONL + mirror),
foreman NOT woken (cooldown 21600 is an operator pin in ~/.hermes/fleet.toml L242;
next natural tick picks the tasks up).
