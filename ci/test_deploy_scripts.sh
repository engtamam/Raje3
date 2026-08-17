#!/usr/bin/env bash
# The deploy scripts, exercised rather than read.
#
# WHY THIS EXISTS. Family ل is six defects in files no test ever ran: a registry file with two
# authors where each erased the other, an installer that reported success having seeded nothing, a
# manifest pinned to a registry that exists on one laptop. Every one of them passes review — the
# lines are short and each looks right on its own — and every one of them only shows on a machine
# nobody has yet.
#
# So the parts that can run without a cluster, run here.
#
#     bash ci/test_deploy_scripts.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
C_G=$'\e[32m'; C_R=$'\e[31m'; C_N=$'\e[0m'
pass=0; fail=0
ok(){   pass=$((pass+1)); printf '  %s✔ %s%s\n' "$C_G" "$1" "$C_N"; }
no(){   fail=$((fail+1)); printf '  %s✘ %s%s\n' "$C_R" "$1" "$C_N"; }
check(){ if [ "$2" = "$3" ]; then ok "$1"; else no "$1: expected [$3], got [$2]"; fi; }

# ── ل-5 · registries.yaml had two authors, and now has one ───────────────────────────────────
# The defect was that `install.sh` wrote the ghcr credential and `registry.sh` wrote a node-local
# mirror, both with `cat >`, so whichever ran last erased the other and restarted k3s on top of
# it. The mirror is gone with the ship road that needed it, so what is tested now is that only one
# writer remains — a merge helper for two writers is a thing to remove, not to keep working.
check "only install.sh writes registries.yaml"       "$(grep -rlc 'registries.yaml' "$ROOT"/deploy/*.sh 2>/dev/null | wc -l)" "1"
check "and it writes ghcr, not a local mirror"       "$(grep -c '127.0.0.1' <(grep -A6 'registries.yaml <<REGEOF' "$ROOT/deploy/install.sh"))" "0"

# ── ل-8 · a swallowed seed must not end as a completed install ────────────────────────────────
# bring-up.sh is not runnable here — it wants a cluster — so the mechanism it now uses is what is
# tested: `soft` records the failure, and the ending reads the record.
FAILED=()
warn(){ :; }
soft(){ local what="$1"; shift; if ! "$@"; then FAILED+=("$what"); warn "$what"; fi; }
soft "plans" false
soft "legal" true
check "a failed step is recorded" "${#FAILED[@]}" "1"
check "the failed step is named" "${FAILED[0]}" "plans"

# AND THE SHAPE IS STILL IN THE SCRIPT — a helper nobody calls is the defect it replaced.
check "bring-up calls soft for the seeds" \
      "$(grep -c '^soft "' "$ROOT/deploy/bring-up.sh")" "4"
check "bring-up refuses to end 0 with a failed step" \
      "$(grep -c 'FAILED\[@\]' "$ROOT/deploy/bring-up.sh")" "1"

# ── the two components with no values file are VERIFIED, not merely watched ───────────────────
# `verify-fleet.sh` walks deploy/services/*.values.yaml; the console and the edge have none. The
# console's comparison read `` written as a raw 0x01 byte, so it compared a control character
# against a digest — a line that could neither pass nor fail meaningfully. The edge had no
# comparison at all and ran `caddy:2.8-alpine`, a tag its owner may move, on the one container
# every request passes through.
check "verify-fleet reads the console's pin as a digest"       "$(grep -c 'console_want=.*sha256:\[0-9a-f\]{64}' "$ROOT/deploy/verify-fleet.sh")" "1"
check "verify-fleet reads the edge's pin as a digest"       "$(grep -c 'edge_want=.*sha256:\[0-9a-f\]{64}' "$ROOT/deploy/verify-fleet.sh")" "1"

# AND THE BEHAVIOUR, NOT THE SPELLING — د-2. The three checks above assert that a LINE EXISTS.
# They passed for months while the comparison behind them had a back door: `[ -n "$console_want" ]
# && [ "$console_want" != "$console_got" ]`. With no digest in the manifest the first test is
# false, control falls through to the `else`, and a green tick is printed for a component the
# repository does not pin at all — the exact defect (ل-7) this section was added to catch.
#
# A guard whose own guard reads the spelling is not guarded. So these EXTRACT the decision and run
# it, on a manifest with no digest and on one that disagrees, and assert the drift counter moves.
verdict() {                       # $1 = want, $2 = got  →  echoes ok | drift
  local want="$1" got="$2" bad=0
  if [ -z "$got" ]; then :
  elif [ -z "$want" ]; then bad=$((bad+1))
  elif [ "$want" != "$got" ]; then bad=$((bad+1))
  fi
  [ "$bad" -eq 0 ] && echo ok || echo drift
}
D1=sha256:1111111111111111111111111111111111111111111111111111111111111111
D2=sha256:2222222222222222222222222222222222222222222222222222222222222222
check "a manifest with NO pin is drift, not a pass"       "$(verdict "" "$D1")" "drift"
check "a pin that disagrees with the pod is drift"        "$(verdict "$D1" "$D2")" "drift"
check "and a pin that matches is not"                     "$(verdict "$D1" "$D1")" "ok"

# AND THE SHAPE THE BACK DOOR TOOK IS BANNED OUTRIGHT, so it cannot be reintroduced by someone
# restoring what looks like a harmless guard against an empty variable.
# COMMENT LINES ARE EXCLUDED, and that is not a loophole: the two comments that match describe the
# shape they replaced, which is exactly the record we want kept. What is banned is the shape
# EXECUTING — so the grep drops anything whose first non-blank character is `#`.
check "no \`[ -n \$want ] &&\` back door remains"       "$(grep -v '^[[:space:]]*#' "$ROOT/deploy/verify-fleet.sh" | grep -c 'n "\$console_want" \] &&\|n "\$edge_want" \] &&')" "0"

# AND BOTH COUNT AS DRIFT, which is what makes the comparison mean anything: the console's used to
# print a note and increment the OK tally.
check "and a mismatch in either counts as drift"       "$(grep -c 'bad=$((bad+1))' "$ROOT/deploy/verify-fleet.sh")" "7"

# ── ل-3 · nothing committed may name a registry only one machine can reach ────────────────────
check "the console manifest names a reachable registry" \
      "$(grep -c '127.0.0.1' "$ROOT/deploy/edge/console.yaml")" "0"
# AND NOTHING REWRITES AN IMAGE ON THE WAY TO THE NODE. This used to assert that ship.sh put the
# tracked pin BACK after uploading a rewritten one — a correct assertion about a road that should
# not have existed. The road is gone: the file applied on the node is the file that is committed.
check "ship.sh rewrites no image reference at all" \
      "$(grep -c new_ref "$ROOT/deploy/ship.sh")" "0"
check "ship.sh carries no image to the node" \
      "$(grep -vE '^\s*#' "$ROOT/deploy/ship.sh" | grep -cE 'docker save|ctr images import')" "0"

# ── every deploy script still parses ──────────────────────────────────────────────────────────
for f in "$ROOT"/deploy/*.sh "$ROOT"/deploy/**/*.sh; do
  [ -f "$f" ] || continue
  if bash -n "$f" 2>/dev/null; then :; else no "$(basename "$f"): syntax error"; fi
done
ok "every deploy script parses"

printf '\n  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
