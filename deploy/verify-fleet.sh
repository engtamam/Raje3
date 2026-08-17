#!/usr/bin/env bash
# ==================================================================================================
#  verify-fleet.sh — is the cluster running what THIS REPO pins? Every service, ours and theirs.
# --------------------------------------------------------------------------------------------------
#  WHY IT EXISTS, AND IT COST US TWO PLATFORM RELEASES. `repin-platform.sh` rewrites the digests and
#  `git commit` makes that look done. Nothing between those two facts and the cluster ever ran: the
#  submodule moved to v0.16.7, every values file said so, the tree was clean — and identity, billing
#  and notification went on serving v0.16.4 for weeks. It surfaced only when a route added in
#  v0.16.7 was asked for by hand and answered 404, and the feature built on it had been quietly
#  dead in production the whole time.
#
#  THE SERVER'S OWN verify-pinned.sh CANNOT SEE THIS. It compares the values files ON THE SERVER,
#  and a ship syncs only the file it shipped — so the server holds a handful and reports on a
#  handful. The pins that matter live here, in the repo, which is the only place that knows the
#  whole fleet.
#
#  READS THE POD, NOT THE DEPLOYMENT. A Deployment's image is what somebody asked for; the pod's
#  `imageID` is what the kubelet actually resolved and is running. They disagree exactly when it
#  matters — a rollout that never completed, an ImagePullBackOff behind a healthy-looking spec.
#
#  Usage:  bash deploy/verify-fleet.sh            # exits non-zero on any drift
# ==================================================================================================
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
NS="${NS:-base-services}"
# THE FLEET IS READ OVER SSH, ALWAYS: this compares what is RUNNING against what the repo pins,
# and doing that from the box being checked is how a drifted node certifies itself. cluster.sh
# above already read target.env — this only insists on the half of it that ssh needs.
: "${REMOTE:?REMOTE is required — set it in deploy/target.env}"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 -p "${PORT:-22}" "$REMOTE")

C_G=$'\e[32m'; C_R=$'\e[31m'; C_Y=$'\e[33m'; C_D=$'\e[2m'; C_N=$'\e[0m'

# ONE ROUND TRIP, NOT ONE PER SERVICE. Eighteen ssh handshakes over this link is a minute of
# waiting for an answer the cluster can give in a single sentence.
live="$("${SSH[@]}" "kubectl -n $NS get pods --no-headers -o custom-columns=\
NAME:.metadata.name,IMG:.status.containerStatuses[0].imageID,READY:.status.containerStatuses[0].ready 2>/dev/null")" || {
  printf '%s  ✗ could not reach the cluster%s\n' "$C_R" "$C_N" >&2; exit 2; }

ok=0; bad=0; missing=0
for f in "$ROOT"/deploy/services/*.values.yaml; do
  svc="$(basename "$f" .values.yaml)"
  want="$(sed -n 's/^  digest: *"\([^"]*\)".*/\1/p' "$f" | head -1)"
  [ -n "$want" ] || continue                     # a values file with no pin is not a claim
  # The running pod for this service: the name is `<svc>-<replicaset hash>-<pod hash>`, and the
  # anchored match is what stops `campaigns` from matching a pod of `campaigns-worker`.
  got="$(printf '%s\n' "$live" | awk -v s="^$svc-[0-9a-f]" '$1 ~ s && $3=="true" {print $2; exit}')"
  got="${got##*@}"
  if [ -z "$got" ]; then
    printf '  %s✗ %-24s no ready pod%s\n' "$C_R" "$svc" "$C_N"; missing=$((missing+1))
  elif [ "$want" != "$got" ]; then
    printf '  %s✗ %-24s running %s… pinned %s…%s\n' "$C_R" "$svc" "${got:0:19}" "${want:0:19}" "$C_N"
    bad=$((bad+1))
  else
    printf '  %s✔ %-24s%s\n' "$C_G" "$svc" "$C_N"; ok=$((ok+1))
  fi
done

# ── AND THE TWO THINGS THE CUSTOMER ACTUALLY SEES (ل-7) ──────────────────────────────────────
#
# The loop above walks `deploy/services/*.values.yaml`. Neither the console nor the edge has a
# values file — the console is a static bundle behind a raw manifest, the edge is Caddy holding a
# rendered config — so this check, which exists because «the repository says one thing and the
# cluster does another», was blind to the only two components a shop owner ever looks at. The
# console serves every screen and the edge routes the domain at it: if either is not running, the
# fleet is green and the product is a blank page.
#
# The console's pin lives in its manifest rather than a values file, so it is read from there and
# compared the same way — imageID, never the spec (a `ctr images tag` reference is a NAME, and
# nothing verifies the content behind it).
console_want="$(grep -oE 'sha256:[0-9a-f]{64}' "$ROOT/deploy/edge/console.yaml" | head -1)"
console_got="$(printf '%s
' "$live" | awk '$1 ~ /^console-[0-9a-f]/ && $3=="true" {print $2; exit}')"
console_got="${console_got##*@}"
if [ -z "$console_got" ]; then
  printf '  %s✗ %-24s no ready pod — every screen in the product is a blank page%s
'          "$C_R" "console" "$C_N"; missing=$((missing+1))
elif [ -z "$console_want" ]; then
  # NO PIN IS A FAILURE, NOT A PASS. This used to read `[ -n "$console_want" ] && ...`, so a
  # manifest whose digest the grep could not find fell through to the `else` and printed
  # a green tick. Put the console back on a moving TAG — which is the exact defect this
  # script was extended to catch — and the check congratulated it.
  printf '  %s✗ %-24s the repository pins NO digest — nothing here can be verified%s
' "$C_R" "console" "$C_N"
  bad=$((bad+1))
elif [ "$console_want" != "$console_got" ]; then
  # A HARD FAILURE NOW, AND IT USED TO BE A NOTE. `ship.sh console` once pinned a node-local
  # registry on the server while the repository kept the published reference, so the two names
  # differed BY DESIGN and this line could not tell that apart from real drift. That road is gone:
  # the file applied on the node is the file that is committed, so a difference here is a console
  # running something the repository does not name — which is exactly what this script is for.
  printf '  %s✗ %-24s running %s… repository pins %s…%s
'          "$C_R" "console" "${console_got:0:19}" "${console_want:0:19}" "$C_N"
  bad=$((bad+1))
else
  printf '  %s✔ %-24s%s
' "$C_G" "console" "$C_N"; ok=$((ok+1))
fi

# THE EDGE HAS A PIN NOW, AND THAT IS WHY THIS COMPARES ONE. It used to say «no pin to compare»
# — true at the time, and the reason the edge was the last image in the fleet nobody verified. It
# ran `caddy:2.8-alpine`, a tag whose owner may move it whenever they like, on the one container
# every request in this product passes through. A moved tag would have arrived at the next restart
# and been invisible here.
edge_want="$(grep -oE 'sha256:[0-9a-f]{64}' "$ROOT/deploy/edge/deployment.yaml" | head -1)"
edge_got="$(printf '%s
' "$live" | awk '$1 ~ /^edge-[0-9a-f]/ && $3=="true" {print $2; exit}')"
edge_got="${edge_got##*@}"
if [ -z "$edge_got" ]; then
  printf '  %s✗ %-24s no ready pod — the domain answers nothing%s
' "$C_R" "edge" "$C_N"
  missing=$((missing+1))
elif [ -z "$edge_want" ]; then
  # NO PIN IS A FAILURE, NOT A PASS. This used to read `[ -n "$edge_want" ] && ...`, so a
  # manifest whose digest the grep could not find fell through to the `else` and printed
  # a green tick. Put the edge back on a moving TAG — which is the exact defect this
  # script was extended to catch — and the check congratulated it.
  printf '  %s✗ %-24s the repository pins NO digest — nothing here can be verified%s
' "$C_R" "edge" "$C_N"
  bad=$((bad+1))
elif [ "$edge_want" != "$edge_got" ]; then
  printf '  %s✗ %-24s running %s… repository pins %s…%s
'          "$C_R" "edge" "${edge_got:0:19}" "${edge_want:0:19}" "$C_N"
  bad=$((bad+1))
else
  printf '  %s✔ %-24s%s
' "$C_G" "edge" "$C_N"; ok=$((ok+1))
fi

# ── AND WHETHER ANYTHING IS ACTUALLY BEING BACKED UP ─────────────────────────────────────────
#
# A digest check answers «the right code is running». It does not answer «our data survives the
# node», and for a long time the answer to that was no while everything here printed green:
# backup-service was deployed with a bucket and a shared BACKUP_KEK, and its TARGET LIST — runtime
# rows, created by no script — was empty. It ran on schedule and reported success on zero targets.
#
# So the count is asserted here, where somebody looks after every deploy. Zero targets is a fleet
# with no backups, and that must never read as green.
# READ THROUGH THE INTERNAL ROUTE backup-service ACTUALLY SERVES — `GET /internal/backup/targets`,
# with the token the pod already holds in its own environment. Inventing a nicer-looking endpoint
# here would have produced a check that reports «could not be read» for ever, which is the same
# silent pass in a different costume.
targets="$("${SSH[@]}" "kubectl -n $NS exec deploy/backup-service -- sh -c '
python - <<EOF 2>/dev/null
import json, os, urllib.request
req = urllib.request.Request(\"http://localhost:8000/internal/backup/targets\",
                             headers={\"X-Internal-Token\": os.environ[\"INTERNAL_SERVICE_TOKEN\"]})
print(len(json.loads(urllib.request.urlopen(req, timeout=10).read() or b\"{}\").get(\"targets\", [])))
EOF
'" 2>/dev/null)"
# A WHOLE LINE THAT IS A NUMBER, NOT «the digits found anywhere in the output». This used to be
# `tr -dc '0-9'`, which strips everything except digits — so `HTTP 503` became `503`, and an error
# message became a healthy-looking target count. The one check standing between us and «nothing is
# being backed up» could be talked out of failing by any error that happened to contain a digit.
targets="$(printf '%s\n' "$targets" | grep -xE '[0-9]+' | tail -1)"

if [ -z "$targets" ]; then
  printf '  %s✗ backup targets: could not be read — a fleet whose backups are unverifiable is not verified%s
'     "$C_R" "$C_N"
  bad=$((bad+1))
elif [ "$targets" = "0" ]; then
  printf '  %s✗ backup targets: NONE registered — nothing in this fleet is being backed up%s
'     "$C_R" "$C_N"
  printf '%s     ./deploy/seed/seed-backup-targets.sh%s
' "$C_D" "$C_N"
  bad=$((bad+1))
else
  printf '  %s✔ %-24s %s registered%s
' "$C_G" "backup targets" "$targets" "$C_N"
fi

echo
if [ $((bad+missing)) -eq 0 ]; then
  printf '%s  ✔ all %d services run the digest this repo pins%s\n' "$C_G" "$ok" "$C_N"; exit 0
fi
printf '%s  ✗ %d drifted, %d not running — the repo says one thing and the cluster does another%s\n' \
  "$C_R" "$bad" "$missing" "$C_N"
printf '%s     ours: ./deploy/ship.sh <service>   ·   platform: the same command, same name%s\n' \
  "$C_D" "$C_N"
exit 1
