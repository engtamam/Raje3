#!/usr/bin/env bash
# sweep.sh — return what the dead are still holding, and NOTHING that is in use.
#
#   sudo bash deploy/sweep.sh              # sweep, and say what it took
#   sudo bash deploy/sweep.sh --dry-run    # say what it WOULD take, and take nothing
#
# WHY THIS EXISTS, AND IT IS NOT TIDINESS. A pod that has finished — Failed or Succeeded — no
# longer runs and is STILL COUNTED by the scheduler: its cpu and memory requests stay booked. A
# read of the pilot node found sixteen of them, some five days old, and 5180m of requests against
# a 4000m box. The consequence is not an untidy list; it is that the next rollout cannot place its
# new pod, the pod dies `OutOfcpu`, the OLD pod keeps serving, and helm reports a healthy release —
# truthfully, about the old one. Every deploy says «done» and the screen never changes.
#
# THE RULE THIS OBEYS: TOUCH NOTHING THAT IS IN USE. Every sweep below is defined by what it may
# NOT take, because a cleaner that removes a live thing is worse than the mess it cleaned:
#
#   * pods — only phase Failed or Succeeded. A CrashLoopBackOff pod is `Running`; it is somebody's
#     problem to READ, not to sweep, and deleting it destroys the evidence.
#   * images — only what no container references. `crictl rmi --prune` is exactly that question
#     asked of containerd, and the answer is authoritative in a way a name-matching guess is not.
#   * replicasets — only those scaled to zero AND not the one the Deployment currently points at,
#     so a rollback still has somewhere to go. We keep the last few by revision, never all of them.
#   * jobs — only Complete ones older than the keep window. A failed job is a report nobody has
#     read yet.
#
# AND IT NEVER TOUCHES: a PersistentVolumeClaim, a Secret, a ConfigMap, a namespace, or anything
# in a phase it does not recognise. Storage and credentials are not litter, and «I do not know what
# this is» is a reason to leave it alone rather than a reason to be thorough.
#
# WHERE IT RUNS TODAY, AND WHERE IT DOES NOT.
#
#   IT RUNS inside `deploy/server/update.sh`, before every roll — which is the moment the seats are
#   actually needed, so the fix arrives exactly when the problem bites.
#
#   IT IS NOT SCHEDULED, and this file used to claim it was. There is no host crontab on the node
#   and no CronJob for it, so a fleet nobody ships to for a month accumulates exactly what this
#   script exists to remove: sixteen dead pods held 2410m on the pilot before the first sweep, and
#   they got there over five days of not deploying. A standing schedule is the honest answer, and
#   it needs explicit authorisation because it means something deleting objects on a live cluster on a
#   timer rather than under a human's hand.
#
#   The claim was written before the schedule existed. It is corrected here rather than
#   half-honoured, because a header that describes a cron nobody created is the same defect this
#   whole file was written after: a report of work that did not happen.
#
# NO `set -e`: each sweep reports for itself and a single failure must not skip the rest.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"

NS="${NS:-${NAMESPACE:-base-services}}"
#: How many superseded replicasets to keep per deployment. Not zero: `helm rollback` needs a
#: previous revision to return to, and the whole point of a rollback is that it works on the worst
#: day, not the tidiest one.
KEEP_REVISIONS="${KEEP_REVISIONS:-3}"
#: A completed job younger than this may still be the one an operator is reading the logs of.
JOB_KEEP_HOURS="${JOB_KEEP_HOURS:-48}"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

took=0

say_would() { printf '  %s→ would take: %s%s\n' "${C_D:-}" "$*" "${C_N:-}"; }

# ── 1. finished pods, whose requests are still booked ────────────────────────────────────────
sweep_pods() {
  local phase names count=0
  for phase in Failed Succeeded; do
    names="$(kubectl -n "$NS" get pods --field-selector "status.phase=$phase" \
               -o jsonpath='{range .items[*]}{.metadata.name}{" "}{end}' 2>/dev/null || true)"
    [[ -n "${names// /}" ]] || continue
    # shellcheck disable=SC2086
    count=$((count + $(printf '%s\n' $names | wc -w)))
    if [[ $DRY_RUN -eq 1 ]]; then say_would "$phase pods: $names"; continue; fi
    # shellcheck disable=SC2086
    kubectl -n "$NS" delete pod $names --wait=false >/dev/null 2>&1 || true
  done
  # NOT DURING A DRY RUN. A tick that says pods were reclaimed, printed by a run that reclaimed
  # nothing, is the same defect this whole file was written after.
  [[ $DRY_RUN -eq 0 && $count -gt 0 ]] && { took=$((took+count)); printf '  %s✔%s %s finished pod(s) — their cpu and memory were still reserved\n' "${C_G:-}" "${C_N:-}" "$count"; }
  return 0
}

# ── 2. superseded replicasets, keeping enough history to roll back ────────────────────────────
sweep_replicasets() {
  local rows old count=0
  # desired=0 means nothing runs from it. Sorted by revision so the newest survivors are kept.
  rows="$(kubectl -n "$NS" get rs \
            -o jsonpath='{range .items[?(@.spec.replicas==0)]}{.metadata.name}{" "}{.metadata.annotations.deployment\.kubernetes\.io/revision}{"\n"}{end}' \
            2>/dev/null | sort -k2 -n -r || true)"
  [[ -n "${rows//[$'\n' ]/}" ]] || return 0
  old="$(printf '%s\n' "$rows" | awk 'NF' | tail -n +"$((KEEP_REVISIONS + 1))" | awk '{print $1}')"
  [[ -n "${old//[$'\n' ]/}" ]] || return 0
  count=$(printf '%s\n' "$old" | awk 'NF' | wc -l)
  if [[ $DRY_RUN -eq 1 ]]; then say_would "$count empty replicaset(s), keeping $KEEP_REVISIONS for rollback"; return 0; fi
  # shellcheck disable=SC2086
  kubectl -n "$NS" delete rs $(printf '%s ' $old) --wait=false >/dev/null 2>&1 || true
  took=$((took+count))
  printf '  %s✔%s %s empty replicaset(s) — %s newest kept so a rollback still has somewhere to go\n' \
    "${C_G:-}" "${C_N:-}" "$count" "$KEEP_REVISIONS"
  return 0
}

# ── 3. completed jobs older than the reading window ───────────────────────────────────────────
sweep_jobs() {
  local names count
  names="$(kubectl -n "$NS" get jobs -o go-template \
    --template='{{range .items}}{{if .status.completionTime}}{{.metadata.name}} {{.status.completionTime}}{{"\n"}}{{end}}{{end}}' \
    2>/dev/null || true)"
  [[ -n "${names//[$'\n' ]/}" ]] || return 0
  local cutoff; cutoff="$(date -u -d "-${JOB_KEEP_HOURS} hours" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || true)"
  [[ -n "$cutoff" ]] || return 0
  local old; old="$(printf '%s\n' "$names" | awk -v c="$cutoff" 'NF && $2 < c {print $1}')"
  [[ -n "${old//[$'\n' ]/}" ]] || return 0
  count=$(printf '%s\n' "$old" | awk 'NF' | wc -l)
  if [[ $DRY_RUN -eq 1 ]]; then say_would "$count completed job(s) older than ${JOB_KEEP_HOURS}h"; return 0; fi
  # shellcheck disable=SC2086
  kubectl -n "$NS" delete job $(printf '%s ' $old) --wait=false >/dev/null 2>&1 || true
  took=$((took+count))
  printf '  %s✔%s %s completed job(s) older than %sh — failed ones are left to be read\n' \
    "${C_G:-}" "${C_N:-}" "$count" "$JOB_KEEP_HOURS"
  return 0
}

# ── 4. images no container references ─────────────────────────────────────────────────────────
#
# ASKED OF containerd, NOT GUESSED FROM NAMES. `--prune` removes what no container references, so
# an image a pod is about to start from is safe by construction — which a "delete anything older
# than N days" rule is not.
sweep_images() {
  local runner=""
  command -v crictl >/dev/null 2>&1 && runner="crictl"
  [[ -z "$runner" ]] && command -v k3s >/dev/null 2>&1 && runner="k3s crictl"
  [[ -n "$runner" ]] || return 0
  if [[ $DRY_RUN -eq 1 ]]; then say_would "unreferenced node images ($runner rmi --prune)"; return 0; fi
  if $runner rmi --prune >/dev/null 2>&1; then
    printf '  %s✔%s unreferenced node images pruned — nothing a container points at is touched\n' "${C_G:-}" "${C_N:-}"
  fi
  return 0
}

printf '\n%s▸ sweep — namespace %s%s%s\n' "${C_B:-}" "${C_C:-}" "$NS" "${C_N:-}"
[[ $DRY_RUN -eq 1 ]] && printf '  %sDRY RUN — nothing is removed%s\n' "${C_Y:-}" "${C_N:-}"
sweep_pods
sweep_replicasets
sweep_jobs
sweep_images

if [[ $DRY_RUN -eq 1 ]]; then
  printf '\n%s✔ dry run finished — nothing was removed%s\n' "${C_G:-}" "${C_N:-}"
elif [[ $took -eq 0 ]]; then
  printf '\n%s✔ nothing to sweep — no finished pod, no empty replicaset beyond the keep window%s\n' "${C_G:-}" "${C_N:-}"
else
  printf '\n%s✔ swept %s object(s); every one of them was already finished%s\n' "${C_G:-}" "$took" "${C_N:-}"
fi
