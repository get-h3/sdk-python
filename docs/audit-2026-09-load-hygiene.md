# H3 Python SDK — test-suite load-hygiene audit (2026-09-20, GAP-067)

> **Historical (2026-09-20):** point-in-time record — the counts and timings
> below were correct when written and are **not live status**. The canonical
> suite/battery counts this repo enforces live in `scripts/test-count.txt`.

Per board row GAP-067. Motivation: on 2026-09-19 the `task-router` project
burned a whole host with a 40-at-once interpreter stampede and 66 seed builds
per run. This row generalises that spawn-stampede class to this repo and asks
one question: **does this suite spawn processes per assertion, in a loop, or
parametrised over many inputs?**

**Verdict: NO-CHANGE.** The suite contains no per-assertion, in-loop or
unbounded process spawn. Every spawn is once per session or once per test.
Peak concurrency for the whole suite is 4 processes (pytest plus three
short-lived ones). No test was deleted, weakened, or given a skip-gate.

## Method

Load claims here are measured, not asserted. Three instruments:

1. **Exact spawn census** — a throwaway pytest plugin (`-p`, kept outside the
   repo) that wraps `subprocess.Popen`, `os.fork` and `os.system` and attributes
   every call to the node id that was running. This turns "how many processes"
   into an exact integer instead of an estimate.
2. **Spawn origin** — a `sys.addaudithook` listener on the `subprocess.Popen`
   audit event, which records the triggering Python call stack. Used to
   attribute the one session-scoped spawn that no test owns.
3. **Wall clock, CPU and load** — `/usr/bin/time -v` (user/sys CPU for the whole
   process tree, plus peak RSS) around the pytest process, with `/proc/loadavg`
   and a descendant walk of the pytest process tree sampled during the run.

Instrument 1 is observation-only: it patches the spawn primitives and counts
them, and it strips its own scratch dir from `PYTHONPATH` in
`pytest_configure` so child processes see a clean environment (see *Environment
caveats* — an inherited scratch dir on `PYTHONPATH` inflates a child pytest's
import scan roughly 20x and would have corrupted every timing comparison).

## Construct inventory

Every process-spawn, thread/process-pool and unbounded-loop construct in
`tests/`, with its per-run multiplicity classification.

| Site | Construct | Multiplicity | Class |
|---|---|---|---|
| `tests/test_count_guard.py:72` (`run_guard`) | `subprocess.run(["sh", scripts/check-test-count.sh])` | 1 per caller test | once-per-test — acceptable |
| `tests/test_count_guard.py:124` | `subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"])` | 1 per test | once-per-test — acceptable |
| `tests/test_generate_protocol.py:83` (`_ruff_normalize`) | `subprocess.run(ruff check --fix)` | 1 per call | once-per-test (see below) |
| `tests/test_generate_protocol.py:83` (`_ruff_normalize`) | `subprocess.run(ruff format)` | 1 per call | once-per-test (see below) |
| `tests/test_generate_protocol.py:179` | `subprocess.run(scripts/generate-protocol.py)` | 1 per test | once-per-test — acceptable |
| `tests/test_generate_protocol.py:216` | `subprocess.run(scripts/generate-protocol.py)` | 1 per test | once-per-test — acceptable |
| `tests/test_harness.py:239` | `time.sleep(1)` | 1 per test | one-second uptime tick; not a spawn |
| `tests/test_quickstart.py:84,100,112,124,135` | `@pytest.mark.parametrize("harness", ...)` | 2 cases x 5 defs | in-process data param., no spawn |
| `tests/test_harness.py:582` | `@pytest.mark.parametrize("reported", ...)` | 2 cases | in-process data param., no spawn |
| `tests/test_count_guard.py:91` | `for i in range(suite)` | builds scratch source text | in-memory string build, no spawn |

Searched for and **absent** from `tests/`: `Popen` (direct), `os.fork`,
`os.system`, `os.spawn*`, `multiprocessing`, `ProcessPool`, `ThreadPool`,
`concurrent.futures`, `asyncio.create_subprocess*`, `pty`, pytest-xdist,
`while True`, and any server/uvicorn startup. `tests/` has no `conftest.py`.
The only `import subprocess` sites are the two files above.

### Exact spawn census (whole suite, one run)

```
TOTAL_SPAWNS=33 across 25 attributed sites
   5  test_generate_protocol.py::test_standalone_clone_generates_from_vendored_copy  [python gen x1, ruff x4]
   4  test_generate_protocol.py::test_vendored_schemas_regenerate_the_committed_protocol  [ruff x4]
   2  test_count_guard.py::test_guard_requires_a_banner_on_dated_records  [sh guard x2]
   1  x 21 other test_count_guard.py cases  [sh guard x1 each, expiring/short-circuit branches]
   1  test_generate_protocol.py::test_cli_error_path_prints_candidates_and_writes_nothing  [python gen x1]
   1  test_count_guard.py::test_canonical_counts_agree_with_the_battery_and_the_suite  [python -m pytest x1]
   1  <session>  [file -b x1]
```

33 spawns for 194 tests, i.e. **0.17 spawns per test**. The maximum any single
test performs is five (`test_standalone_clone_generates_from_vendored_copy`:
one generator run plus four ruff calls from two `_ruff_normalize` calls).
Nothing is looped: no spawn sits inside a `for`, a comprehension, or a
parametrised expansion over many inputs.

The one spawn no test owns is `file -b`, called once per **session** at startup
by third-party code — `pytest_benchmark/utils.py::get_machine_id` →
`platform.architecture()` → `platform._syscmd_file`. Audit-hook stack trace
confirmed the origin. Session-scoped and unavoidable without touching
dependencies; harmless.

### Why `_ruff_normalize` is not the offender

`_ruff_normalize` (2 spawns per call) is the largest per-test spawn multiplier:
its two callers invoke it four times total, producing 8 of the 33 spawns. It is
still **once-per-test**, not per-assertion, and the two caller tests are the
only tests that need a ruff-normalised artifact. A plausible fix would cache one
shared normalized artifact per session, saving ~6 spawns; measured against a
suite that spends ~11s wall clock and ~0.35s in those two tests, that is not a
host-load problem worth a behaviour change, and de-duplicating generation would
reduce the number of distinct artifacts actually verified against the committed
`protocol.py`. It is left alone deliberately. (The vendored-copy regeneration
tests assert byte-for-byte reproducibility against the committed file; keeping
each call independently exercised preserves that evidence.)

## Measured before/after

"No change" makes the before and after identical by construction, so the
deliverable is the **repeated baseline** (three clean-env runs, same tree, same
commit `d259dd1`) plus the peak-concurrency sample.

Host: 16 CPUs. Ambient load was **not** zero — this box was already running the
fleet at load1 ~7-12 — so absolute wall clock varies and loadavg is a weak
instrument. CPU time (whole process tree) is the comparable metric.

| Run | Wall | CPU (user+sys) | pytest self-report | load1 min→max | peak RSS |
|---|---|---|---|---|---|
| baseline (first) | 14.98s | — | 14.03s | 6.88 → 7.15 | — |
| run1 | 11.67s | 10.99s | 11.12s | 7.79 → 8.48 | 66 MB |
| run2 | 11.68s | 10.80s | 10.95s | 7.79 → 8.21 | 66 MB |
| run3 (`--durations=15`) | 12.71s | 12.06s | 12.14s | 7.72 → 7.87 | 66 MB |
| peak-concurrency sample | 12.38s | — | 11.76s | 10.62 → 11.19 | — |

- **Wall clock:** 10.95s–14.03s as pytest reports it; mean ~12.3s.
- **Load contribution:** `load1` moved by **+0.1 to +0.6** during a run, from an
  ambient 6.9–10.6 baseline. The suite does not move the host.
- **CPU:** ~11s of CPU spread over 16 cores across ~12s wall — under one core
  busy on average.
- **Peak concurrency:** a descendant walk of the pytest process tree sampled
  every 0.2s for the whole run shows a peak of **3 descendants, i.e. 4
  processes counting pytest itself**. Compare the generalised offender class
  (40 interpreters at once): this is not that shape, and cannot become it — the
  suite is single-process and synchronous.

Durations confirm every slow entry is a subprocess test at ~0.35–1.3s; nothing
accumulates.

## Verdict

**NO-CHANGE.** The measurements support it directly: 33 spawns for 194 tests,
maximum 5 per test, none inside a loop or iteration, peak concurrency 4, and a
load1 delta of +0.1–0.6 over ambient. There is no worst offender to bound, and
inventing one would mean restructuring correct, load-irrelevant tests.

## Findings that are real but out of this row's scope

1. **`ruff format --check .` fails at base, on a committed file, with a clean
   tree** — `docs/dogfood/2026-09-19-integration.md`, an unmodified dated
   record. This is not caused by GAP-067 (no file was edited), and it is not
   repaired here on purpose: the repo treats `docs/dogfood/YYYY-MM-DD-*` as
   point-in-time records that are "never rewritten"
   (`scripts/check-test-count.sh`), and the repo's own lint entry points are
   scoped to `src/ tests/` (`Makefile: make lint` → `ruff check src/ tests/`),
   with no format step in CI. Scoped to the code the project actually gates,
   `ruff check src/ tests/` and `ruff format --check src/ tests/` are both
   clean. Reported for a separate decision, not silently reformatted.
2. **One second of the suite's wall clock is a fixed `time.sleep(1)`**
   (`tests/test_harness.py:239`) asserting a monotonic uptime tick. It is a
   deliberate real-observation, not load, and removing it would weaken the
   assertion; left as is.

## Environment caveats (so these numbers stay honest)

- The brief stated the project venv would be present at `.venv`; in this
  worktree it was **absent**, so one was created inside the worktree and
  installed from the committed `uv.lock` resolution (pytest 9.1.1, ruff 0.16.8 —
  matching the lock). `.venv/` is git-ignored and no repo file was affected.
- Ambient fleet load on this host was 6.9–12 load1 throughout, so absolute wall
  clock readings are noisy by roughly ±20% between runs; the CPU-time and
  spawn-count figures do not have that weakness.
- An inherited scratch dir on `PYTHONPATH` inflates a child pytest's import
  scan sharply (measured: `--collect-only` 0.33s → 6.66s, the guard script
  1.80s → 10.42s) on this NFS-heavy home. The census plugin inherits
  `PYTHONPATH` from *its own* host dir only, and strips it for children; runs
  used for timing comparisons were therefore executed with a clean environment.

## Reproduction

```bash
# exact spawn census (plugin lives outside the repo)
PYTHONPATH=/tmp .venv/bin/pytest -q -p gap067_spawn_counter

# wall clock + CPU for the whole tree + sampled loadavg
/usr/bin/time -v .venv/bin/pytest -q

# acceptance
.venv/bin/pytest -q
sh scripts/check-test-count.sh
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```
