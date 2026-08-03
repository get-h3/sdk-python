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
