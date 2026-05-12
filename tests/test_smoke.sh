#!/usr/bin/env bash
# tests/test_smoke.sh — basic sanity tests for macli.
#
# Runs read-only commands and verifies they produce well-formed --json
# envelopes. Skips anything destructive (wx send, x post, dark-mode flip).
# Assumes macli is on PATH or run with MACLI=./macli.
#
# Usage:
#   ./tests/test_smoke.sh
#   MACLI=./macli ./tests/test_smoke.sh
#   FAIL_FAST=1 ./tests/test_smoke.sh

set -uo pipefail

MACLI="${MACLI:-macli}"
FAIL_FAST="${FAIL_FAST:-0}"

pass=0
fail=0
skip=0
failed_names=()

if ! command -v jq >/dev/null 2>&1; then
    echo "jq is required (brew install jq)" >&2
    exit 2
fi

if ! command -v "$MACLI" >/dev/null 2>&1 && [[ ! -x "$MACLI" ]]; then
    echo "macli not found at: $MACLI" >&2
    exit 2
fi

ok()   { pass=$((pass+1)); printf "  \033[32m✓\033[0m %s\n" "$1"; }
bad()  { fail=$((fail+1)); failed_names+=("$1"); printf "  \033[31m✗\033[0m %s\n     %s\n" "$1" "$2"; [[ $FAIL_FAST == 1 ]] && exit 1; }
skipt(){ skip=$((skip+1)); printf "  \033[33m–\033[0m %s  (%s)\n" "$1" "$2"; }

# expect_ok <name> <command...> — runs command, parses stdout as JSON envelope,
# asserts .ok == true
expect_ok() {
    local name="$1"; shift
    local out
    out="$("$@" 2>/dev/null)" || { bad "$name" "exit non-zero"; return; }
    local got_ok
    got_ok="$(jq -r '.ok // "missing"' <<<"$out" 2>/dev/null)"
    if [[ "$got_ok" == "true" ]]; then
        ok "$name"
    else
        bad "$name" ".ok=$got_ok  stdout=$(head -c 200 <<<"$out")"
    fi
}

# expect_jq <name> <jq_expr> <command...> — runs command, evaluates jq expr,
# asserts result is the literal string "true"
expect_jq() {
    local name="$1" expr="$2"; shift 2
    local out
    out="$("$@" 2>/dev/null)" || { bad "$name" "exit non-zero"; return; }
    local got
    got="$(jq -e "$expr" <<<"$out" 2>/dev/null)" && ok "$name" || \
        bad "$name" "jq '$expr' failed  stdout=$(head -c 200 <<<"$out")"
}

# expect_err_code <name> <expected_code> <command...> — runs command, asserts
# .ok=false and .error.code matches
expect_err_code() {
    local name="$1" expected="$2"; shift 2
    local out
    out="$("$@" 2>/dev/null)"
    local code
    code="$(jq -r '.error.code // "missing"' <<<"$out" 2>/dev/null)"
    if [[ "$code" == "$expected" ]]; then
        ok "$name"
    else
        bad "$name" "expected error.code=$expected, got=$code"
    fi
}

echo "[macli smoke tests] target: $MACLI"
echo ""

# ---- basic ---------------------------------------------------------------
echo "basic"
ver="$("$MACLI" --version 2>/dev/null)"
[[ -n "$ver" ]] && ok "macli --version → $ver" || bad "macli --version" "empty output"
"$MACLI" help >/dev/null 2>&1 && ok "macli help" || bad "macli help" "non-zero exit"

# ---- doctor --------------------------------------------------------------
echo ""
echo "doctor"
expect_ok       "doctor --json"        "$MACLI" doctor --json
expect_jq       "doctor: 5 vendors"    '.data.vendors | length == 5' "$MACLI" doctor --json
expect_jq       "doctor: kb_count>400" '.data.kb_count > 400'        "$MACLI" doctor --json

# ---- mac -----------------------------------------------------------------
echo ""
echo "mac"
expect_ok       "mac volume --json"      "$MACLI" mac volume --json
expect_jq       "mac volume is number"   '.data.volume | type == "number"'  "$MACLI" mac volume --json
expect_ok       "mac kb-list --json"     "$MACLI" mac kb-list --json
expect_jq       "mac kb-list count>400"  '.data.count > 400'        "$MACLI" mac kb-list --json
expect_jq       "mac script returns 42"  '.data.stdout | contains("42")'  "$MACLI" mac script 'return 42' --json
expect_ok       "mac kb-search safari"   "$MACLI" mac kb-search "safari pdf" --max 3 --json
expect_jq       "kb-search has results"  '.data.count > 0'  "$MACLI" mac kb-search "safari" --max 5 --json
expect_err_code "mac kb missing-id"      "not_found"        "$MACLI" mac kb __nonexistent_script__ --json
expect_err_code "mac kb-search no-args"  "invalid_args"     "$MACLI" mac kb-search --json

# ---- x (cookie-dependent ones skipped if no cookies) ---------------------
echo ""
echo "x"
if "$MACLI" x cookies-save --check-age --json >/dev/null 2>&1; then
    expect_ok   "x cookies-save --check-age --json"  "$MACLI" x cookies-save --check-age --json
    expect_jq   "cookies status is one of fresh/aging/stale/expired" \
                '.data.status | test("fresh|aging|stale|expired|missing")' \
                "$MACLI" x cookies-save --check-age --json
else
    skipt "x cookies-save --check-age" "no cookies file"
fi

# ---- wx (destructive — skipped; just verify usage errors are well-formed) -
echo ""
echo "wx"
expect_err_code "wx send no-args"  "invalid_args"  "$MACLI" wx send --json
expect_err_code "wx read no-args"  "invalid_args"  "$MACLI" wx read --json

# ---- summary -------------------------------------------------------------
echo ""
echo "---"
echo "passed: $pass   failed: $fail   skipped: $skip"
if [[ $fail -gt 0 ]]; then
    echo ""
    echo "FAILED:"
    for n in "${failed_names[@]}"; do echo "  - $n"; done
    exit 1
fi
exit 0
