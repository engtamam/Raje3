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

# ── AND WHAT EACH WORKLOAD *ASKS FOR*, WHICH IS A DIFFERENT QUESTION (أ-1) ───────────────────
#
# Everything above reads `imageID` — what the kubelet RESOLVED — and that is right for «is the
# rollout that I shipped the thing that is running». It is blind to the failure that started this:
# the repository pinned `caddy:2.8-alpine@sha256:af32e973…` and the live Deployment carried
# `caddy:2.8-alpine` with NO digest. The running pod had resolved to the correct digest anyway,
# out of the node's image cache, so `imageID` matched and this script printed green.
#
# Nothing was wrong that day and everything was wrong the next: a naked tag is a promise its owner
# can move, and the next eviction, node or `imagePullPolicy` pull takes whatever the tag points at
# then. The check built to catch exactly this could not see it, because it was reading the answer
# instead of the question.
#
# So the SPEC is read too, and it is judged on its own terms: a spec with no digest is a failure
# even when today's pod happens to be correct. That is not pedantry — it is the difference between
# «right now» and «tomorrow morning», and this script exists for tomorrow morning.
spec="$("${SSH[@]}" "kubectl -n $NS get deploy,statefulset,daemonset --no-headers -o custom-columns=\
NAME:.metadata.name,IMG:.spec.template.spec.containers[0].image 2>/dev/null")" || {
  printf '%s  ✗ could not read the workload specs%s\n' "$C_R" "$C_N" >&2; exit 2; }

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

# ── AND WHETHER THE RUN CAN FINISH BEFORE ITS CALLER GIVES UP (ي-7) ──────────────────────────
#
# THE CRONJOB IS A `urlopen(..., timeout=300)`. The run it starts walks every registered target in
# turn, each with its own `BACKUP_TARGET_TIMEOUT_SECONDS`. Nobody has ever multiplied those two
# numbers together — and they are both written down, one in this repository and one on the cluster.
#
# What happens when the product of them exceeds 300 is the worst available outcome: the backup
# SUCCEEDS and is reported FAILED. The caller gives up, the Job exits non-zero, the alert fires,
# and somebody spends a morning on a backup that worked. Worse, the reverse reading is available
# too — «the backup is failing, it always fails, ignore it» is how a real failure gets missed.
#
# This is arithmetic, not a probe: it cannot start a run and it does not try. It multiplies what
# the repository declares by what the cluster registered and says whether the sum fits.
#
# AND IT IS A FAMILY, NOT ONE SERVICE — AND THIS SCRIPT NO LONGER KEEPS ITS OWN COPY OF THE LIST.
#
# It used to carry a hand-written table of the members. Then the gate found a fifth
# (notification-service's queue drain, 100 x 15s) and this comment still said «four», so the two
# halves of one finding disagreed about how big it was — a table transcribed by hand drifts the
# moment the thing it describes moves, which is the defect this whole section is about.
#
# So the declared half is printed by the gate that computes it —
# `ci/check_a_cron_can_finish_before_its_caller_gives_up.py`, run below — and this script keeps
# only the half the gate cannot know: the number of targets ACTUALLY registered on the cluster,
# which is a fact about a running fleet rather than a declaration.
#
# THE ERROR WORTH KEEPING WRITTEN DOWN, because the family is made of it: the first version of that
# table multiplied ONE batch by ONE timeout — `reminders 100 x 8 = 800s` — and never noticed the
# loop is NESTED, walking `for tenant in tenants[:TICK_MAX_TENANTS]` with the batch inside EACH
# tenant. Wrong by a factor of two hundred, and a batch size was lowered on the strength of it.
#
# NO REPOSITORY VALUE MAKES THEM FIT. Even one row per tenant is 200 x 8s = 1600s. The fix for
# every member is the same single escalation: the 300 in the platform chart. See #340.
# THE DECLARED HALF, PRINTED BY THE GATE THAT COMPUTES IT. Not summarised and not counted here:
# the membership of this family is derived from the values files, and any sentence about it kept
# in a second place goes stale the day a sixth member appears — which is exactly what happened to
# the table that used to sit above.
if command -v python3 >/dev/null 2>&1; then
  cron_out="$(python3 "$ROOT/ci/check_a_cron_can_finish_before_its_caller_gives_up.py" 2>&1)"
  cron_rc=$?
  printf '%s
' "$cron_out" | sed 's/^/  /'
  [ "$cron_rc" -eq 0 ] || bad=$((bad+1))
else
  # NOT A PASS. Without python3 the declared half is unread, and «unread» must never print
  # green — the same rule the rest of this script already lives by.
  printf '  %s✗ %-24s python3 missing — the declared half was NOT checked%s\n' \
    "$C_R" "cron windows" "$C_N"
  bad=$((bad+1))
fi

per_target="$(sed -n 's/^  BACKUP_TARGET_TIMEOUT_SECONDS: *"\([0-9]*\)".*/\1/p' \
  "$ROOT/deploy/services/backup-service.values.yaml" | head -1)"
caller_wait=300     # `platform/deploy/chart/templates/cronjob.yaml` — read-only, hence the escalation
if [ -n "$per_target" ] && [ -n "$targets" ] && [ "$targets" -gt 0 ] 2>/dev/null; then
  worst=$((targets * per_target))
  if [ "$worst" -gt "$caller_wait" ]; then
    printf '  %s✗ %-24s %d targets x %ds = %ds worst case, and the cron waits %ds%s\n' \
      "$C_R" "backup window" "$targets" "$per_target" "$worst" "$caller_wait" "$C_N"
    printf '%s       a run that SUCCEEDS is reported failed — and «it always fails» is how a real%s\n' \
      "$C_D" "$C_N"
    printf '%s       failure gets ignored. The 300s lives in the platform chart: escalate it.%s\n' \
      "$C_D" "$C_N"
    bad=$((bad+1))
  else
    printf '  %s✔ %-24s %d x %ds fits inside the cron'"'"'s %ds%s\n' \
      "$C_G" "backup window" "$targets" "$per_target" "$caller_wait" "$C_N"
  fi
else
  # NOT A PASS: without both numbers this said nothing, and saying nothing about whether the
  # backup can finish is the state this whole section exists to end.
  printf '  %s✗ %-24s could not be computed — the run window was NOT checked%s\n' \
    "$C_R" "backup window" "$C_N"
  bad=$((bad+1))
fi

# ── AND THE CONFIG THAT DRIVES THE CODE (أ-2) ────────────────────────────────────────────────
#
# EVERYTHING ABOVE COMPARES IMAGES. أ-2 was not an image: the corrected code was deployed and the
# configuration that drives it was not. `WHATSAPP_ONBOARDING_GRAPH_BASE` read v21.0 on the cluster
# while the repository said v26.0, and `WHATSAPP_GRAPH_BASE` was absent from the ConfigMap
# entirely. Every digest matched. Every pod was ready. This script printed green.
#
# What that costs is not an outage. A retired Graph version does not fail loudly — it stops
# returning a field. So a shop walks through Embedded Signup, Meta answers SUCCESSFULLY, the
# screen says «مربوط», and not one message is ever delivered. The failure is invisible from every
# angle except a customer who never hears from the shop again.
#
# So the env a values file DECLARES is compared with the ConfigMap the cluster HOLDS. Declared and
# missing is a failure; declared and different is a failure. A key the cluster holds and the
# repository does not is NOT reported here — the platform's own chart adds its defaults, and a
# gate that cried about every one of them is a gate nobody reads.
cfg_bad=0
cfg_seen=0
for f in "$ROOT"/deploy/services/*.values.yaml; do
  svc="$(basename "$f" .values.yaml)"
  # The `env:` block, to the next top-level key. Only fully-literal `KEY: "value"` lines are
  # compared: a templated value is not a claim about what the cluster should hold.
  want_env="$(awk '/^env:/{f=1;next} /^[a-zA-Z]/{f=0} f' "$f" \
    | sed -n 's/^  \([A-Z][A-Z0-9_]*\): *"\([^"]*\)".*/\1=\2/p')"
  [ -n "$want_env" ] || continue
  live_cm="$("${SSH[@]}" "kubectl -n $NS get cm $svc -o jsonpath='{.data}' 2>/dev/null")" || live_cm=""
  if [ -z "$live_cm" ]; then
    printf '  %s✗ %-24s no ConfigMap on the cluster — its settings were NOT checked%s\n' \
      "$C_R" "$svc" "$C_N"; cfg_bad=$((cfg_bad+1)); continue
  fi
  # SPLIT ON THE FIRST `=` BY HAND. `while IFS='=' read -r k v` looks equivalent and is not: `read`
  # strips trailing delimiters, so `EMAIL_VERIFICATION_URL=https://app.raje3.sa/verify?token=`
  # arrived with its final `=` removed — and the check then reported a difference between a value
  # and itself. A URL that ends in `=` is the normal shape for a token parameter, so this was not
  # an exotic case; it was the first one.
  while read -r line; do
    [ -n "$line" ] || continue
    k="${line%%=*}"; v="${line#*=}"
    [ -n "$k" ] || continue
    cfg_seen=$((cfg_seen+1))
    # ABSENT AND EMPTY ARE NOT THE SAME ANSWER, and reading them as one is how this check first
    # reported 37 differences of which nearly all were `EGRESS_ALLOWED_HOSTS: ""` declared here and
    # held as `""` on the cluster — agreeing perfectly. An extraction that returns the empty string
    # for «no such key» cannot tell a missing setting from a deliberately blank one, and a blank one
    # is a real value here: it means «no host is allowed», which is the safe end of that switch.
    #
    # So presence is tested first, on its own. This is the same defect this repository has fixed in
    # four screens and two gates — an empty read rendered as a fact — and it appeared here in the
    # check written to catch drift.
    if ! printf '%s' "$live_cm" | grep -q "\"$k\":"; then
      printf '  %s✗ %-24s %s is declared here and ABSENT from the cluster%s\n' \
        "$C_R" "$svc" "$k" "$C_N"; cfg_bad=$((cfg_bad+1)); continue
    fi
    got="$(printf '%s' "$live_cm" | sed -n "s/.*\"$k\":\"\([^\"]*\)\".*/\1/p")"
    if [ "$got" != "$v" ]; then
      printf '  %s✗ %-24s %s is %s on the cluster, %s here%s\n' \
        "$C_R" "$svc" "$k" "$got" "$v" "$C_N"; cfg_bad=$((cfg_bad+1))
    fi
  done <<< "$want_env"
done
if [ "$cfg_bad" -eq 0 ]; then
  printf '  %s✔ %-24s %d declared setting(s) match the cluster%s\n' \
    "$C_G" "config" "$cfg_seen" "$C_N"
fi

# ── AND WHAT THE CLUSTER HOLDS THAT NOBODY DEPLOYS (أ-4، أ-5) ────────────────────────────────
#
# EVERY CHECK ABOVE ASKS «is what the repository names actually running». None of them asks the
# other direction: what is running that the repository does NOT name. Drift has two directions and
# this script only ever looked one way.
#
# SECRETS FOR SERVICES THIS DEPLOYMENT NEVER INSTALLS. `mint-our-secrets.sh` rotates the six that
# are ours; anything else keeps its original material for as long as the namespace lives. Material
# nobody rotates and nobody can name is material nobody will revoke when it leaks.
#
# AND PODS THAT DIED AND WERE NEVER REAPED. A `Failed` pod is not inert: it keeps its record in the
# scheduler, and the edge demands `hostPort: 80/443` with `strategy: Recreate` — which terminates
# the live pod FIRST. If the scheduler still counts those ports against a corpse, the replacement
# sticks on «didn't have free ports» with nothing serving the domain until somebody logs in.
#
# The reason is printed because it is usually the finding: fifteen of the sixteen here say
# `OutOfcpu`, which is not litter — it is the node saying it admitted pods it could not run.
orphan_sec=0
dead_pods=0
cluster_sec="$("${SSH[@]}" "kubectl -n $NS get secrets --no-headers -o custom-columns=N:.metadata.name 2>/dev/null | grep -v '^sh.helm'")" || cluster_sec=""
cluster_wl="$("${SSH[@]}" "kubectl -n $NS get deploy,statefulset,daemonset --no-headers -o custom-columns=N:.metadata.name 2>/dev/null")" || cluster_wl=""
if [ -z "$cluster_sec" ] || [ -z "$cluster_wl" ]; then
  # NOT A PASS. Reading nothing is not the same as finding nothing, and this section exists
  # precisely to notice what nobody is looking for.
  printf '  %s✗ %-24s could not be read — orphans were NOT checked%s\n' "$C_R" "cluster extras" "$C_N"
  orphan_sec=$((orphan_sec+1))
else
  while read -r s; do
    [ -n "$s" ] || continue
    case "$s" in
      *-secrets) ;;
      *) continue ;;                     # ghcr, postgres-tls: not the per-service shape
    esac
    svc="${s%-secrets}"
    printf '%s\n' "$cluster_wl" | grep -qx ".*/\?$svc" && continue   # something runs it
    # AND NOTHING IN *OUR* deploy/ NAMES IT. `platform-secrets` runs no workload of its own and is
    # not an orphan: `bring-up.sh` puts the postgres password in it, so the repository knows
    # exactly what it is for. What is left after both tests are secrets minted for services the
    # PLATFORM catalogue ships and this deployment never installs — referenced only under
    # `platform/`, running nowhere, and skipped by `mint-our-secrets.sh`.
    #
    # Two tests rather than a skip list: a secret that becomes used, or a service that gets
    # installed, stops being reported without anybody editing this script.
    grep -rq "$s" "$ROOT/deploy" 2>/dev/null && continue
    printf '  %s✗ %-24s minted for a service this deployment never installs — and not rotated%s\n' \
      "$C_R" "$s" "$C_N"; orphan_sec=$((orphan_sec+1))
  done <<< "$cluster_sec"
fi
ghosts="$("${SSH[@]}" "kubectl -n $NS get pods --no-headers -o custom-columns=N:.metadata.name,P:.status.phase,R:.status.reason 2>/dev/null | grep -vE ' (Running|Succeeded|Pending) '")" || ghosts=""
if [ -n "$ghosts" ]; then
  dead_pods="$(printf '%s\n' "$ghosts" | grep -c .)"
  printf '  %s✗ %-24s %d pod(s) in a terminal state, still counted by the scheduler%s\n' \
    "$C_R" "dead pods" "$dead_pods" "$C_N"
  printf '%s\n' "$ghosts" | head -5 | while read -r n p r; do
    printf '%s       %s  %s %s%s\n' "$C_D" "$n" "$p" "$r" "$C_N"
  done
  [ "$dead_pods" -gt 5 ] && printf '%s       … and %d more%s\n' "$C_D" "$((dead_pods-5))" "$C_N"
fi
if [ "$orphan_sec" -eq 0 ] && [ "$dead_pods" -eq 0 ]; then
  printf '  %s✔ %-24s nothing on the cluster that the repository cannot name%s\n' \
    "$C_G" "cluster extras" "$C_N"
fi

# ── EVERY WORKLOAD SPEC NAMES A DIGEST (أ-1) ─────────────────────────────────────────────────
#
# Judged on the spec alone, and deliberately separate from the digest comparison above: this one
# does not care whether the running pod is correct. A naked tag whose pod happens to be right today
# is the exact state that printed green while the edge — the container every request in this
# product passes through — was one eviction from running whatever the tag pointed at.
#
# The whole namespace, not a list of names: a workload that appears without anybody adding it here
# is precisely the one nobody is checking.
naked=0
while read -r wl img; do
  [ -n "$wl" ] || continue
  case "$img" in
    *@sha256:*) : ;;
    ""|"<none>")
      # A workload whose image this read could not see is NOT a pass — it is a workload nobody
      # verified, and saying so is the whole doctrine of this script.
      printf '  %s✗ %-24s spec image unreadable — NOT checked%s\n' "$C_R" "${wl#*/}" "$C_N"
      naked=$((naked+1)) ;;
    *)
      printf '  %s✗ %-24s spec asks for %s — a TAG, not a digest%s\n' \
        "$C_R" "${wl#*/}" "$img" "$C_N"
      naked=$((naked+1)) ;;
  esac
done <<< "$spec"
if [ "$naked" -eq 0 ]; then
  printf '  %s✔ %-24s every workload spec names a digest%s\n' "$C_G" "spec pins" "$C_N"
fi

echo
if [ $((bad+missing+naked+cfg_bad+orphan_sec+dead_pods)) -eq 0 ]; then
  printf '%s  ✔ all %d services run the digest this repo pins, and every spec names one%s\n' \
    "$C_G" "$ok" "$C_N"; exit 0
fi
if [ "$cfg_bad" -gt 0 ]; then
  printf '%s  ✗ %d setting(s) differ from the repository — the code shipped, the config did not%s
'     "$C_R" "$cfg_bad" "$C_N"
  printf '%s     every image can match while the thing that drives them does not%s
' "$C_D" "$C_N"
fi
if [ $((orphan_sec+dead_pods)) -gt 0 ]; then
  printf '%s  ✗ the cluster holds %d secret(s) and %d dead pod(s) nobody deploys%s
'     "$C_R" "$orphan_sec" "$dead_pods" "$C_N"
  printf '%s     removing them changes a running cluster — that is a decision, not a cleanup%s
'     "$C_D" "$C_N"
fi
if [ "$naked" -gt 0 ]; then
  printf '%s  ✗ %d workload(s) ask for a moving tag — correct today, whatever the tag points at%s\n' \
    "$C_R" "$naked" "$C_N"
  printf '%s     the pod may still be right: this is about the next pull, not this one%s\n' \
    "$C_D" "$C_N"
fi
if [ $((bad+missing)) -gt 0 ]; then
  printf '%s  ✗ %d drifted, %d not running — the repo says one thing and the cluster does another%s\n' \
    "$C_R" "$bad" "$missing" "$C_N"
  printf '%s     ours: ./deploy/ship.sh <service>   ·   platform: the same command, same name%s\n' \
    "$C_D" "$C_N"
fi
exit 1
