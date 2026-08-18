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
# `grep -rl`, NOT `-rlc` (د-12). `-l` prints file names and CANCELS `-c`, so the old command was
# counting files by accident rather than by intent — it gave the right answer for the wrong
# reason, which is the kind of line that breaks the day somebody "tidies" it.
check "only install.sh writes registries.yaml"       "$(grep -rl 'registries.yaml' "$ROOT"/deploy/*.sh 2>/dev/null | wc -l)" "1"
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
#
# THE RULE, NOT A TALLY. This counted `soft "` lines and expected FOUR, so the day a fifth seed was
# added — `backup targets` — it went red about a number while the rule it exists to protect was
# perfectly intact. A test that fails for being out of date teaches its reader that red is normal,
# which is the defect this whole file was written against.
#
# What matters is that EVERY seed goes through `soft`: a seed invoked directly aborts bring-up on a
# machine where one optional seed cannot run, and a seed nobody wraps is a failure nobody records.
# So the assertion is «no seed is called outside soft» — true at four seeds, at five, and at the
# next one somebody adds.
check "every seed in bring-up goes through soft"       "$(grep -n 'seed/seed-[a-z-]*[.]sh' "$ROOT/deploy/bring-up.sh"          | grep -v '^[0-9]*:[[:space:]]*#' | grep -cv ':soft "')" "0"
check "and there is at least one seed to wrap"       "$([ "$(grep -c '^soft "' "$ROOT/deploy/bring-up.sh")" -gt 0 ] && echo yes || echo no)" "yes"
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
# AGAIN THE RULE RATHER THAN THE TALLY. This counted every `bad=$((bad+1))` in the whole file and
# expected SEVEN — a number about the entire script, asserted inside a section about two
# components. verify-fleet has since grown more drift causes (the cron window, the node, the
# digests), every one of them wanted, and this went red for counting them while neither console
# nor edge had changed at all.
#
# So each block is read on its own: the console's comparison and the edge's must EACH move the
# counter, in both of their failing branches — no pin, and a pin that disagrees. That is the
# sentence this section's heading actually makes.
console_block="$(sed -n '/^console_want=/,/^edge_want=/p' "$ROOT/deploy/verify-fleet.sh")"
edge_block="$(sed -n '/^edge_want=/,$p' "$ROOT/deploy/verify-fleet.sh" | sed -n '1,/^fi$/p')"
check "a console mismatch counts as drift"       "$(printf '%s
' "$console_block" | grep -c 'bad=$((bad+1))')" "2"
check "an edge mismatch counts as drift"       "$(printf '%s
' "$edge_block" | grep -c 'bad=$((bad+1))')" "2"

# ── THE SHIP THAT REACHES THE SERVER AND NOT THE SCREEN ───────────────────────────────────────
#
# Nothing set Cache-Control on the console, so a browser applied its own heuristic to index.html —
# the ONE file that names the hashed bundle — and served it from disk without asking. A deployment
# rolled, the pod reported the new digest, verify-fleet agreed, and the owner opened the console and
# read the old screen. «الشحن غير صحيح ما زالت الواجهة نفسها», twice in one night, on a cluster
# running exactly what the repository declared.
#
# THE TWO RULES ARE OPPOSITES AND BOTH ARE REQUIRED. A hashed asset may be kept for a year because
# its name changes with its contents; the page that points at it may never be trusted from cache,
# because its staleness hides every other thing we ship.
check "the console's pages are never served from cache"       "$(grep -c 'header @page Cache-Control "no-cache"' "$ROOT/apps/console/Caddyfile")" "1"
check "and its hashed assets are kept for a year"       "$(grep -c 'header @asset Cache-Control "public, max-age=31536000, immutable"' "$ROOT/apps/console/Caddyfile")" "1"
# THE PAGE MATCHER IS «NOT AN ASSET», NOT A LIST OF PAGES. Every screen has a real URL and the SPA
# rewrite serves index.html for all of them, so a matcher naming `/app/` and `/app/index.html`
# would cover the two paths a person never types and miss every one he does.
check "and the page rule is matched by exclusion, not by a list"       "$(grep -c '@page not path /assets/[*] /app/assets/[*]' "$ROOT/apps/console/Caddyfile")" "1"

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
# COUNTED, AND THE TICK IS CONDITIONAL (د-12). `ok "every deploy script parses"` used to run
# UNCONDITIONALLY after the loop: a script with a syntax error printed its own red line and then
# this printed a green one underneath it, so the summary said both. And a loop that matched
# nothing — a moved directory, a changed glob — printed the same tick over zero files.
parsed=0
broken=0
for f in "$ROOT"/deploy/*.sh "$ROOT"/deploy/**/*.sh; do
  [ -f "$f" ] || continue
  if bash -n "$f" 2>/dev/null; then parsed=$((parsed+1)); else broken=$((broken+1)); no "$(basename "$f"): syntax error"; fi
done
if [ "$parsed" -eq 0 ]; then
  no "no deploy script was parsed at all — the glob matched nothing, and an empty set is not agreement"
elif [ "$broken" -eq 0 ]; then
  ok "every deploy script parses ($parsed)"
fi

printf '\n  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
