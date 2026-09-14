#!/usr/bin/env bash
# ==================================================================================================
#  patch-datastore-probes.sh — let postgres finish crash recovery before we kill it.
# --------------------------------------------------------------------------------------------------
#  WHAT HAPPENED, ON OUR OWN CLUSTER, AND IT TOOK THE WHOLE PRODUCT DOWN.
#
#  The node went NotReady (a laptop that sleeps is a node that stops), postgres came back from an
#  unclean shutdown, and PostgreSQL did what it must: it fsynced the entire data directory before
#  accepting a connection. On this disk that takes minutes — the log counts it out in ten-second
#  steps, «syncing data directory (fsync), elapsed time: 80.00 s».
#
#  The platform's liveness probe allows sixty. So at second sixty Kubernetes sent a fast shutdown to
#  a database that was 70% through its recovery, and the next attempt started the same recovery from
#  the beginning — again, and again, eight restarts deep. NOTHING WAS WRONG WITH THE DATA. The
#  timeout was the fault, and it presented as CrashLoopBackOff, which reads like corruption and
#  invites exactly the wrong response: delete the volume and restore a backup.
#
#  AND EVERY SERVICE WENT 0/1 BEHIND IT — twenty-two pods, the gateway included, all reporting
#  themselves unready and all of them correct to do so. One probe's failureThreshold was the entire
#  outage.
#
#  WHY A PATCH AND NOT AN EDIT. `platform/deploy/k3s/platform/datastores.yaml` is base-services',
#  and base-services is read-only to us (a fork we cannot merge is a fork we maintain for ever). So
#  this is applied AFTER their manifest, from a script that lives with our deploy — and it is
#  ESCALATED upstream, because a startup probe belongs in the manifest that declares the database.
#
#  IDEMPOTENT. Applying it twice changes nothing; a `kubectl patch` with the same body is a no-op.
#
#  Usage:  sudo bash deploy/patch-datastore-probes.sh
# ==================================================================================================
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
NS="${NS:-base-services}"

C_G=$'\e[32m'; C_R=$'\e[31m'; C_D=$'\e[2m'; C_N=$'\e[0m'

kubectl -n "$NS" get statefulset postgres >/dev/null 2>&1 || {
  echo "${C_R}✖ no postgres statefulset in $NS${C_N}"; exit 2; }

# A STARTUP PROBE IS THE RIGHT INSTRUMENT, and its absence is the actual gap. Liveness answers "is
# it wedged"; startup answers "has it finished coming up" — and while a startup probe is running,
# liveness is not consulted at all. 60 × 10s = ten minutes of recovery allowed, after which the
# liveness rules resume unchanged at their normal sensitivity.
#
# TEN MINUTES IS NOT A GUESS: the observed fsync pass was past 80 seconds and still walking the
# directory when it was killed, on a database this small. A ceiling that only just fits is a
# ceiling that fails the first time the data grows.
# SAME PATCH, ONE MORE FIELD FIXED — found live, 2026-09-14, on a from-scratch install: the
# upstream manifest's readiness AND liveness probes ALSO hardcode `-U postgres`, and no role by
# that literal name is ever created (`gen-secrets.py` provisions `POSTGRES_USER`, defaulting to
# `base_services` — the same name the container's own `POSTGRES_USER` env already uses). Every
# probe tick (5s readiness, 10s liveness) logged `FATAL: role "postgres" does not exist` into
# postgres's own log, forever, on every install — harmless (`pg_isready` only proves the server
# accepts a connection; the role lookup failing does not fail the check itself), but a constant,
# misleading flood in the one log an operator reads first when something looks wrong. `$(VAR)`
# is expanded from the container's own env by the kubelet exactly like any other exec-probe
# command arg — no new value to provision, just reading the one already there.
read -r -d '' PATCH <<'JSON'
{"spec":{"template":{"spec":{"containers":[{
  "name":"postgres",
  "startupProbe":{
    "exec":{"command":["pg_isready","-U","$(POSTGRES_USER)"]},
    "initialDelaySeconds":10,"periodSeconds":10,"timeoutSeconds":5,
    "failureThreshold":60,"successThreshold":1},
  "readinessProbe":{
    "exec":{"command":["pg_isready","-U","$(POSTGRES_USER)"]},
    "periodSeconds":5},
  "livenessProbe":{
    "exec":{"command":["pg_isready","-U","$(POSTGRES_USER)"]},
    "periodSeconds":10}
}]}}}}
JSON

if kubectl -n "$NS" patch statefulset postgres --type=strategic -p "$PATCH" >/dev/null; then
  echo "${C_G}✔ postgres may now take up to ten minutes to recover before liveness applies${C_N}"
  echo "  ${C_D}(escalated: this belongs in base-services' datastores.yaml)${C_N}"
else
  echo "${C_R}✖ patch failed${C_N}"; exit 1
fi

# The pod only picks the probe up on its next start — so a pod that is ALREADY WEDGED is restarted
# now, and a healthy one is left alone.
#
# THE DIFFERENCE MATTERS BECAUSE THIS RUNS AT INSTALL TOO. Bouncing a database that has just come
# up cleanly, to apply a probe that only changes what happens during a recovery, is a restart with
# no reason — and on a fresh install it lands in the middle of the seeding that follows.
READY="$(kubectl -n "$NS" get pod postgres-0           -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null || echo "")"
if [ "$READY" = "true" ]; then
  echo "  ${C_D}postgres is healthy — the probe applies on its next restart${C_N}"
else
  kubectl -n "$NS" delete pod postgres-0 --wait=false >/dev/null 2>&1 || true
  echo "  ${C_D}postgres-0 was not ready — restarting it with the new probe${C_N}"
fi
