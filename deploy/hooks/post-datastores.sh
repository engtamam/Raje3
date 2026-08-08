#!/usr/bin/env bash
# ==================================================================================================
#  post-datastores.sh — raise postgres's connection ceiling to fit the fleet we actually run.
# --------------------------------------------------------------------------------------------------
#  OURS, applied AFTER upstream's datastores manifest. platform/ is read-only, so this patches the
#  running StatefulSet rather than editing their file.
#
#  WHY IT EXISTS — measured, not guessed:
#
#  Every service creates its postgres pool with `asyncpg.create_pool(dsn)` and no arguments. The
#  asyncpg defaults are min_size=10, max_size=10, and no setting in any service's config.py changes
#  this — there is no pool knob at all.
#
#  MEASURED, and the mechanism matters more than the number. The pool is built LAZILY, on the first
#  query, and then fills to min_size=10 and stays there for the process lifetime. On the recovered
#  cluster, pg_stat_activity by database:
#
#     wallet 10 · analytics 10 · identity 10 · onboarding 10 · authz 10   (used since restart)
#     audit 2 · connector 1 · compliance 1                               (not touched yet)
#
#  So the ceiling is consumed GRADUALLY, as each service is first used — not at startup. That makes
#  it a time bomb rather than a boot failure: the cluster looks healthy for hours, every readyz
#  green, and then deadlocks on an ordinary request to an ordinary service, because that one
#  happened to cross the line. It hides from smoke tests, and it arrives sooner the more of the
#  platform a customer actually uses.
#
#  Ten connections is the price of having been used ONCE, not the price of being busy. Demand is
#  therefore 10 x (services that have ever served a request), trending to 10 x (all of them).
#  Upstream's manifest passes no args to postgres, so it runs on the stock max_connections of 100.
#  Ten services fill it. We run twenty-one.
#
#  The failure is not a slow query — it is a DEADLOCK on rollout. The chart uses maxUnavailable: 0
#  and maxSurge: 1 (right, in isolation): the new pod must be Ready before the old one is retired.
#  But the new pod cannot get its ten connections while the old pod still holds its ten, so readyz
#  reports `datastore: down`, so it never becomes Ready, so the old pod is never retired. Both sides
#  wait forever. Observed: ten deployments restarted together, every new pod still 0/1 fifteen
#  minutes later, and postgres refusing even psql with "sorry, too many clients already". Restarting
#  postgres did NOT fix it — the services simply reconnected and refilled it, which is the proof
#  that this is a permanent ceiling and not a transient spike.
#
#  Reported upstream: the pool needs to be configurable and lazy (min_size=1 alone breaks the
#  deadlock), readyz should distinguish "postgres is down" from "the pool is exhausted", and a
#  preflight should compare services x pool_min against max_connections. Until that lands, this is
#  the operator-side half of the answer and it is legitimate on its own terms: a platform of this
#  size does not belong on a stock 100-connection postgres.
#
#  THE NUMBERS, and why these and not larger:
#    max_connections=300   21 services x 10 = 210 steady, plus surge during a rollout, plus a slot
#                          for psql when something is wrong. Not 400: every backend costs real
#                          memory, and a ceiling you cannot afford to reach is a worse lie than a
#                          low one.
#    memory limit 2Gi      up from 1Gi. At ~5MB per backend, 300 connections is ~1.5GB before
#                          shared_buffers. Raising the ceiling without raising this trades a
#                          connection error for an OOM kill, which is strictly worse: the error is
#                          legible and the kill is not.
#    shared_buffers=256MB  25% of the limit, the conventional starting point.
#
#  A POOLER IS THE REAL ANSWER AT SCALE. pgbouncer in transaction mode is what lets many services
#  with generous pools share a small number of backend connections, and it is what we will need
#  before this platform carries serious load. This raises a ceiling; it does not remove one.
# ==================================================================================================
set -uo pipefail
NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

info(){ echo -e "\e[36m  ▸ $*\e[0m"; }
ok(){   echo -e "\e[32m  ✔ $*\e[0m"; }

MAX_CONN="${MAX_CONN:-300}"

current=$(kubectl -n "$NS" get statefulset postgres \
          -o jsonpath='{.spec.template.spec.containers[0].args}' 2>/dev/null)
if [[ "$current" == *"max_connections=$MAX_CONN"* ]]; then
  ok "postgres already allows $MAX_CONN connections"
  exit 0
fi

info "raising postgres max_connections to $MAX_CONN (stock 100 cannot hold this fleet)"
kubectl -n "$NS" patch statefulset postgres --type=json -p "$(cat <<JSON
[
  {"op":"add","path":"/spec/template/spec/containers/0/args",
   "value":["postgres","-c","max_connections=$MAX_CONN","-c","shared_buffers=256MB"]},
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory",
   "value":"2Gi"}
]
JSON
)" >/dev/null || { echo "  patch failed"; exit 1; }

# A StatefulSet does not restart its pod on a template change the way a Deployment does when the
# change is applied this way, so ask explicitly and wait — a script that patches and returns leaves
# the operator believing a setting is live when the old process is still running.
kubectl -n "$NS" rollout restart statefulset postgres >/dev/null 2>&1
kubectl -n "$NS" rollout status statefulset postgres --timeout=300s >/dev/null 2>&1 \
  && ok "postgres restarted on max_connections=$MAX_CONN" \
  || echo "  postgres did not become ready in time — check: kubectl -n $NS describe pod postgres-0"
