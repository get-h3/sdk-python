#!/bin/sh
# refresh-vendored-schemas.sh — refresh the vendored protocol schema mirror
# and regenerate its drift manifest (GAP-059).
#
# The vendored mirror tests/schemas/v1/ is the schema source of record for a
# standalone clone (no sibling protocol checkout present) and the fallback
# corpus for scripts/generate-protocol.py. tests/schemas/manifest.json maps
# every vendored filename to its sha256, and the mirror test in
# tests/test_schema_validation.py FAILS (never skips) when a file is missing,
# extra, or byte-different from the manifest entry — a stale mirror must not
# re-ship silently.
#
# Run this whenever the protocol schema set changes, and commit the mirror,
# the manifest, and any count prose together.
#
# Usage:
#   scripts/refresh-vendored-schemas.sh [SOURCE_SCHEMAS_V1_DIR]
#
# SOURCE_SCHEMAS_V1_DIR defaults to the sibling dev checkout
# <repo>/../protocol/schemas/v1.
#
# Exit codes: 0 = mirror + manifest refreshed and verified byte-identical to
# the source; 1 = the mirror does not match the source (nothing else written);
# 2 = the source directory is missing/empty (nothing written).

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SRC=${1:-$ROOT/../protocol/schemas/v1}
DST=$ROOT/tests/schemas/v1
MANIFEST=$ROOT/tests/schemas/manifest.json

if [ ! -d "$SRC" ]; then
    echo "FAIL: source schema directory not found: $SRC" >&2
    echo "      Pass it explicitly: scripts/refresh-vendored-schemas.sh /path/to/schemas/v1" >&2
    exit 2
fi

FIRST_SRC=$(ls "$SRC"/*.json 2>/dev/null | head -n 1 || true)
if [ -z "$FIRST_SRC" ]; then
    echo "FAIL: no *.json schemas in $SRC" >&2
    exit 2
fi

# Sorted, locale-independent iteration for both the copy and the manifest.
LC_ALL=C
export LC_ALL

mkdir -p "$DST"

# 1. Copy: every source schema overwrites its mirror counterpart (the source
#    tree is truth).
for src_file in "$SRC"/*.json; do
    cp -- "$src_file" "$DST/$(basename -- "$src_file")"
done
echo "refresh-vendored-schemas: copied $(ls "$DST"/*.json | wc -l | tr -d ' ') schemas from $SRC"

# 2. Verify: the mirror must be byte-identical to the source in BOTH
#    directions, so a file the source dropped cannot linger in the mirror.
if ! diff -r "$DST" "$SRC" >/dev/null 2>&1; then
    echo "FAIL: the mirror does not match the source after the copy:" >&2
    diff -r "$DST" "$SRC" >&2 || true
    echo "      A vendored file the source no longer has must be deleted by hand:" >&2
    echo "      the mirror holds exactly the source's *.json — nothing else." >&2
    exit 1
fi

# 3. Regenerate the drift manifest: filename -> sha256, one entry per line,
#    sorted. No comment keys: the manifest's KEY SET *is* the mirror's file
#    set, which is what the mirror test compares against.
{
    printf '{\n'
    first=1
    for schema in "$DST"/*.json; do
        name=$(basename -- "$schema")
        sum=$(sha256sum -- "$schema" | cut -d' ' -f1)
        if [ "$first" -eq 1 ]; then
            first=0
        else
            printf ',\n'
        fi
        printf '  "%s": "%s"' "$name" "$sum"
    done
    printf '\n}\n'
} > "$MANIFEST"

echo "refresh-vendored-schemas: wrote $MANIFEST ($(grep -c ':' "$MANIFEST" | tr -d ' ') entries)"
echo "refresh-vendored-schemas: PASS — mirror verified against $SRC, manifest regenerated"
exit 0
