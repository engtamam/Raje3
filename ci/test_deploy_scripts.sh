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
