#!/bin/sh
# check-test-count.sh — the Python SDK polices its OWN count prose (H3-GAP-087).
#
# Why this exists: the compliance battery in get-h3/shim is the single source of
# truth for how many compliance tests exist, and this repo's pytest suite has a
# count of its own — but nothing in THIS repo checked the prose around either.
# The stale-count class re-offended here repeatedly (44/44 in CONTRIBUTING long
# after the battery reached 46, "128 tests" in CONTRIBUTING while README said
# 157, CI gates that pinned "45/45" while every test passed) because the only
# sweep lived in the umbrella repo, where an SDK-only doc edit is never seen.
# This repo owns its truth now.
#
# Canonical inputs — scripts/test-count.txt:
#   battery=46   the get-h3/shim compliance battery (`h3-test`): every "N/N
#                compliant" / "N tests, 6 categories" claim in this repo is
#                about this number.
#   suite=157    this repo's own pytest suite, as counted by
#                `python -m pytest --collect-only -q`.
#
# Checks:
#   a. canonical parse       — scripts/test-count.txt must exist and hold exactly
#                              one `battery=` and one `suite=` bare number, else
#                              exit 2 (guard misconfigured).
#   b. suite parity          — the LIVE pytest collection count must equal
#                              `suite=`, else exit 1. pytest is the only honest
#                              source here: static `def test_` counting misses
#                              parametrized expansions (5 defs -> 10 tests in
#                              tests/test_quickstart.py), so a static fallback
#                              would silently lie. Not runnable → exit 2.
#   c. battery parity        — when a sibling shim checkout is present its
#                              scripts/test-count.txt must agree with `battery=`,
#                              else exit 1 (the battery moved and this repo's
#                              prose is now stale). No sibling checkout → NOTE
#                              and continue: this repo must not depend on one.
#   d. retired-literal sweep — no tracked current-state surface may still
#                              advertise a RETIRED battery count (43/44/45 in
#                              count-shaped forms, plus any "N/44"-style fraction
#                              against a retired total).
#   e. canonical-claim sweep — a living doc that states a suite size
#                              ("<NNN> tests") or a whole-suite total
#                              ("<NN>/<NN>", 40+) must state the canonical
#                              number. This catches a stale suite literal
#                              ("128 tests") that was never a battery count.
#   f. dated-report banner   — a dated record (docs/dogfood/YYYY-MM-DD-*,
#                              docs/audit-YYYY-MM-*) that quotes a retired count
#                              must open with a point-in-time banner
#                              "> **Historical (YYYY-MM-DD):** ...", which is
#                              what makes its exemption unambiguous to a reader.
#
# Historical exemptions (deliberate, narrow):
#   * CHANGELOG.md, e2e-output/, dist/, .coding-hermes/, .gitreins/, .vfs/ —
#     release/board/state records, never rewritten.
#   * dated reports (docs/dogfood/YYYY-MM-DD-*, docs/audit/…-YYYY-MM*) — carry
#     the count that was true when written; check (f) requires them to say so.
#   * any single line carrying the inline marker `count-ok-historical` — an
#     era-correct number quoted inside an otherwise-living document.
#   * any file whose head (first 25 lines) carries the same point-in-time
#     banner — a document that declares itself a historical record.
#
# Exit codes: 0 = pass, 1 = drift, 2 = guard misconfigured (missing/bad inputs).
# Dependencies: POSIX sh + coreutils (git, grep, sed, awk, wc) + pytest (for the
# live suite count only). No network.
#
# Overrides (used by tests/test_count_guard.py to drive every branch
# hermetically): H3_SDK_COUNT_FILE, H3_SDK_SCAN_ROOT, H3_SDK_SHIM_COUNT_FILE,
# H3_SDK_PYTHON.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=${H3_SDK_SCAN_ROOT:-$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)}

# ---- (a) canonical counts --------------------------------------------------
CANON_FILE=${H3_SDK_COUNT_FILE:-$SCRIPT_DIR/test-count.txt}
if [ ! -f "$CANON_FILE" ]; then
    echo "FAIL: canonical count file missing: $CANON_FILE" >&2
    echo "      Fix: create it with the two lines 'battery=<N>' and 'suite=<N>'." >&2
    exit 2
fi

canon_value() {
    # $1 = key. Prints the value only when the file holds EXACTLY one such line.
    n=$(grep -c -E "^$1=[0-9][0-9]*\$" "$CANON_FILE" 2>/dev/null || true)
    if [ "$n" != "1" ]; then
        return 1
    fi
    sed -n "s/^$1=\([0-9][0-9]*\)\$/\1/p" "$CANON_FILE" | head -n 1
}

if ! BATTERY=$(canon_value battery); then
    echo "FAIL: $CANON_FILE must contain exactly one 'battery=<number>' line" >&2
    echo "      (the get-h3/shim compliance battery count)." >&2
    exit 2
fi
if ! SUITE=$(canon_value suite); then
    echo "FAIL: $CANON_FILE must contain exactly one 'suite=<number>' line" >&2
    echo "      (this repo's own pytest suite count)." >&2
    exit 2
fi

# ---- (b) suite parity: canonical vs the repo's real suite source -----------
PYTHON_BIN=${H3_SDK_PYTHON:-}
if [ -z "$PYTHON_BIN" ]; then
    if [ -x "$ROOT/.venv/bin/python" ]; then
        PYTHON_BIN=$ROOT/.venv/bin/python
    elif [ -x "$ROOT/.venv/bin/python3" ]; then
        PYTHON_BIN=$ROOT/.venv/bin/python3
    else
        PYTHON_BIN=python3
    fi
fi
if [ ! -x "$PYTHON_BIN" ] && ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "FAIL: cannot run the suite collector — '$PYTHON_BIN' is not executable" >&2
    echo "      Fix: make install (or set H3_SDK_PYTHON to a python with pytest)." >&2
    exit 2
fi

COLLECT=$( cd "$ROOT" && "$PYTHON_BIN" -m pytest --collect-only -q 2>/dev/null || true )
LINE=$(printf '%s\n' "$COLLECT" | grep -E '^[0-9]+ tests? collected' | tail -n 1 || true)
if [ -z "$LINE" ]; then
    echo "FAIL: could not derive the pytest suite count" >&2
    echo "      (ran: $PYTHON_BIN -m pytest --collect-only -q in $ROOT)" >&2
    echo "      Fix: make install, so pytest is importable for this interpreter." >&2
    exit 2
fi
COUNT=$(printf '%s\n' "$LINE" | sed -n 's/^\([0-9][0-9]*\) tests\? collected.*$/\1/p')
case "$COUNT" in
    '' | *[!0-9]*)
        echo "FAIL: could not parse the pytest collection count from: $LINE" >&2
        exit 2
        ;;
esac
printf '%s\n' "$LINE" | grep -q 'error' && \
    echo "check-test-count: NOTE — pytest reported errors during collection ($LINE)"

if [ "$COUNT" != "$SUITE" ]; then
    echo "FAIL: suite drift — pytest collects $COUNT tests" >&2
    echo "      but $CANON_FILE says suite=$SUITE." >&2
    echo "      Fix: decide which is truth, then update scripts/test-count.txt AND" >&2
    echo "      every prose line that states a suite size." >&2
    exit 1
fi
echo "check-test-count: suite agrees ($COUNT tests via pytest --collect-only)"

# ---- (c) battery parity against the sibling shim's canonical count --------
SHIM_CANON=${H3_SDK_SHIM_COUNT_FILE:-$ROOT/../shim/scripts/test-count.txt}
if [ -f "$SHIM_CANON" ]; then
    SHIM_BATTERY=$(tr -d ' \t\r\n' < "$SHIM_CANON")
    case "$SHIM_BATTERY" in
        '' | *[!0-9]*)
            echo "FAIL: $SHIM_CANON is not a bare number: '$SHIM_BATTERY'" >&2
            echo "      Fix: point H3_SDK_SHIM_COUNT_FILE at the shim's canonical" >&2
            echo "      count file, or unset it to skip battery parity." >&2
            exit 2
            ;;
    esac
    if [ "$SHIM_BATTERY" != "$BATTERY" ]; then
        echo "FAIL: battery drift — this repo pins battery=$BATTERY" >&2
        echo "      but the shim's canonical battery count is $SHIM_BATTERY." >&2
        echo "      Fix: the battery moved. Update scripts/test-count.txt to" >&2
        echo "      battery=$SHIM_BATTERY and sweep every prose count the guard names." >&2
        exit 1
    fi
    echo "check-test-count: battery agrees with the shim ($BATTERY tests)"
else
    echo "check-test-count: NOTE — no shim canonical count at $SHIM_CANON;"
    echo "                  battery parity skipped (local canonical battery=$BATTERY)."
fi

# ---- (d)+(e) sweeps over tracked current-state surfaces --------------------
# Retired battery totals only — never a bare number, which would also match
# ports, dates and durations.
RETIRED='4[345]-tests?|4[345] tests?|4[345] compliance|4[345] passed|4[345]-test |out of 4[345]|[0-9]+/4[345]|4[345]/[0-9]+'

BANNER_PATTERN='^[[:space:]]*>[[:space:]]*\*\*Historical \([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\):'

is_scanned() {
    case "$1" in
        *.md | *.py | *.toml | *.ini | *.yml | *.yaml | *.cfg) return 0 ;;
        Makefile | */Makefile) return 0 ;;
        *) return 1 ;;
    esac
}

is_excluded() {
    case "$1" in
        CHANGELOG.md) return 0 ;;
        e2e-output/* | dist/*) return 0 ;;
        .coding-hermes/* | .gitreins/* | .vfs/* | .benchmarks/*) return 0 ;;
        docs/dogfood/[0-9][0-9][0-9][0-9]-*) return 0 ;;
        docs/audit-[0-9][0-9][0-9][0-9]-*) return 0 ;;
        *) return 1 ;;
    esac
}

has_banner() {
    head -n 25 "$1" 2>/dev/null | grep -q -E -- "$BANNER_PATTERN"
}

if cd "$ROOT" && git rev-parse --git-dir >/dev/null 2>&1; then
    FILES=$(cd "$ROOT" && git ls-files)
else
    FILES=$(cd "$ROOT" && find . -type f | sed 's|^\./||')
fi

# The scans below word-split the file list, so a path with whitespace would be
# scanned as fragments. Fail loudly instead of scanning the wrong thing.
SPACED=$(printf '%s\n' "$FILES" | grep ' ' || true)
if [ -n "$SPACED" ]; then
    echo "FAIL: whitespace in a tracked path breaks this scan: '$SPACED'" >&2
    exit 2
fi

HITS=0
for f in $FILES; do
    if ! is_scanned "$f"; then continue; fi
    if is_excluded "$f"; then continue; fi
    if [ ! -f "$ROOT/$f" ]; then continue; fi
    if has_banner "$ROOT/$f"; then continue; fi

    # AGENTS.md is a protected agent-instruction file: the H3 fleet forbids
    # headless edits to it (agent-instruction-file write guard), so a stale
    # literal there cannot be swept from a worker session. It is REPORTED on
    # every run instead of being silently skipped — H3-GAP-086 tracks the
    # edit through an approved channel.
    if [ "$f" = "AGENTS.md" ]; then
        PROT=$(grep -n -I -E -- "$RETIRED" "$ROOT/$f" 2>/dev/null | grep -v 'count-ok-historical' || true)
        if [ -n "$PROT" ]; then
            printf '%s\n' "$PROT" | while IFS= read -r hit; do
                echo "check-test-count: NOTE — AGENTS.md (protected, not swept) still" >&2
                echo "                  quotes a retired count: $hit" >&2
                echo "                  pending an approved H3-GAP-086 channel edit" >&2
            done
        fi
        continue
    fi

    OUT=$(grep -n -I -E -- "$RETIRED" "$ROOT/$f" 2>/dev/null || true)
    if [ -n "$OUT" ]; then
        OUT=$(printf '%s\n' "$OUT" | grep -v 'count-ok-historical' || true)
    fi
    SEEN=""
    if [ -n "$OUT" ]; then
        SEEN=$(printf '%s\n' "$OUT" | sed -n 's/^\([0-9][0-9]*\):.*/\1/p' | tr '\n' ' ')
        printf '%s\n' "$OUT" | while IFS= read -r hit; do
            printf '%s:%s\n' "$f" "$hit"
        done
        N=$(printf '%s\n' "$OUT" | wc -l | tr -d ' ')
        HITS=$((HITS + N))
    fi

    # Lines the retired sweep already reported are not reported twice, so the
    # hit total stays an honest count of offending lines.
    CLAIMS=$(awk -v cs="$SUITE" -v cb="$BATTERY" -v seen="$SEEN" '
        function in_seen(ln, i) {
            for (i = 1; i <= n_seen; i++) if (sa[i] + 0 == ln) return 1
            return 0
        }
        BEGIN { n_seen = split(seen, sa, " ") }
        /count-ok-historical/ { next }
        {
            line = $0
            while (match(line, /[0-9][0-9][0-9][- ]tests?/)) {
                n = substr(line, RSTART, RLENGTH) + 0
                if (n != cs && !in_seen(NR)) printf "%d: suite claim %d tests != %d: %s\n", NR, n, cs, $0
                line = substr(line, RSTART + RLENGTH)
            }
            line = $0
            countable = (tolower($0) ~ /tests?|battery|compliance|pytest|vitest|checks?|suite|passed/)
            while (match(line, /[0-9]+\/[0-9]+/)) {
                tok = substr(line, RSTART, RLENGTH)
                split(tok, parts, "/")
                b = parts[2] + 0
                if (countable && b >= 40 && b != cb && b != cs && !in_seen(NR))
                    printf "%d: total claim %s is not a canonical total (%d/%d): %s\n", NR, tok, cb, cs, $0
                line = substr(line, RSTART + RLENGTH)
            }
        }' "$ROOT/$f")
    if [ -n "$CLAIMS" ]; then
        printf '%s\n' "$CLAIMS" | while IFS= read -r hit; do
            printf '%s:%s\n' "$f" "$hit"
        done
        N=$(printf '%s\n' "$CLAIMS" | wc -l | tr -d ' ')
        HITS=$((HITS + N))
    fi
done

if [ "$HITS" -ne 0 ]; then
    echo "FAIL: $HITS stale count literal(s) above." >&2
    echo "      The battery ships $BATTERY tests and this suite ships $SUITE." >&2
    echo "      Fix: replace each hit with the current number, state the count" >&2
    echo "      count-agnostically, or — for genuinely era-correct narration —" >&2
    echo "      mark the line with the inline marker count-ok-historical." >&2
    exit 1
fi
echo "check-test-count: no stale count literals in current-state surfaces"

# ---- (f) dated records must carry a point-in-time banner -------------------
UNBANNERED=0
for f in $FILES; do
    case "$f" in
        docs/dogfood/[0-9][0-9][0-9][0-9]-* | docs/audit-[0-9][0-9][0-9][0-9]-*) ;;
        *) continue ;;
    esac
    if [ ! -f "$ROOT/$f" ]; then continue; fi
    if ! grep -q -I -E -- "$RETIRED" "$ROOT/$f" 2>/dev/null; then continue; fi
    if has_banner "$ROOT/$f"; then continue; fi
    echo "FAIL: $f quotes a retired count with no point-in-time banner." >&2
    UNBANNERED=$((UNBANNERED + 1))
done
if [ "$UNBANNERED" -ne 0 ]; then
    echo "      Fix: add one line directly under the first heading:" >&2
    echo "        > **Historical (YYYY-MM-DD):** point-in-time record — the counts" >&2
    echo "        > below were correct when written and are not live status." >&2
    exit 1
fi

# ---- (g) PASS summary ------------------------------------------------------
echo "check-test-count: PASS — canonical battery=$BATTERY, suite=$SUITE; current-state prose agrees"
exit 0
