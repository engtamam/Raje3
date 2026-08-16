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

# ── ل-5 · registries.yaml has two authors and neither may erase the other ─────────────────────
. "$ROOT/deploy/lib/registries.sh"

install_writes(){          # what deploy/install.sh puts in the file
  registries_entry "$1" configs '"ghcr.io"' <<YAML
  "ghcr.io":
    auth:
      username: "x"
      password: "$2"
YAML
}
registry_writes(){         # what deploy/registry.sh puts in the file
  registries_entry "$1" mirrors '"127.0.0.1:5055"' <<'YAML'
  "127.0.0.1:5055":
    endpoint:
      - "http://127.0.0.1:5055"
YAML
  registries_entry "$1" configs '"127.0.0.1:5055"' <<'YAML'
  "127.0.0.1:5055":
    tls:
      insecure_skip_verify: true
YAML
}

F="$TMP/a.yaml"; : > "$F"
install_writes "$F" SECRET; registry_writes "$F"
check "install then registry: the ghcr credential survives" \
      "$(grep -c 'SECRET' "$F")" "1"
check "install then registry: the local mirror is there" \
      "$(grep -c '127.0.0.1:5055' "$F")" "3"

F="$TMP/b.yaml"; : > "$F"
registry_writes "$F"; install_writes "$F" SECRET
check "registry then install: the local mirror survives" \
      "$(grep -c '127.0.0.1:5055' "$F")" "3"
check "registry then install: the credential is there" "$(grep -c 'SECRET' "$F")" "1"

# A ROTATED TOKEN REPLACES THE OLD ONE. Appending a second `"ghcr.io":` block leaves the stale
# password first in the file, which is the one a YAML reader keeps — a rotation that silently does
# nothing, discovered whenever the old token is finally revoked.
install_writes "$F" ROTATED
check "a re-run replaces the entry rather than appending one" "$(grep -c 'ghcr.io' "$F")" "1"
check "the new password is the one in the file" "$(grep -c 'ROTATED' "$F")" "1"
check "the old password is gone" "$(grep -c 'SECRET' "$F")" "0"
check "the file is still one section each" "$(grep -c '^configs:' "$F")" "1"

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
check "ship.sh puts the tracked pin back after the upload" \
      "$(grep -c 'sed -i "s|\$new_ref|\$old_ref|"' "$ROOT/deploy/ship.sh")" "2"

# ── every deploy script still parses ──────────────────────────────────────────────────────────
for f in "$ROOT"/deploy/*.sh "$ROOT"/deploy/**/*.sh; do
  [ -f "$f" ] || continue
  if bash -n "$f" 2>/dev/null; then :; else no "$(basename "$f"): syntax error"; fi
done
ok "every deploy script parses"

printf '\n  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
