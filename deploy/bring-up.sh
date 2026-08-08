#!/usr/bin/env bash
# ==================================================================================================
#  bring-up.sh — a fresh host to a running Raje3, in the right order, with nothing typed by hand.
# --------------------------------------------------------------------------------------------------
#  This exists because every step below was, at some point, done by hand — and every hand-done step
#  produced a defect that took longer to find than the step took to perform:
#
#    * a service secret cloned from a neighbour, which is how connector-service nearly inherited
#      another service's database DSN;
#    * BACKUP_KEK copied onto sixteen services one kubectl patch at a time, after every one of them
#      answered a bare 503 that named no cause;
#    * three databases added to the provisioning list only after the service had already been
#      deployed and failed on its first write.
#
#  Upstream's gen-secrets.py would have prevented the first two on its own: BACKUP_KEK is declared
#  `shared` in their schema and appears in twenty-one services, so it is written byte-identically
#  everywhere at install time. We simply never called it. That is the lesson this file encodes —
#  the tooling existed and we reached past it.
#
#  ORDER IS THE POINT. Each step needs the one before it:
#    1. preflight      refuse a host that cannot run this before touching it
#    2. datastores     postgres and redis must exist before a secret can name a DSN
#    3. post-datastores  raise the connection ceiling BEFORE services start filling it
#    4. secrets        minted once, shared values byte-identical across every service
#    5. databases      one per service; a service without one starts, passes /healthz, then fails
#                      on its first write
#    6. buckets        separate for files and backups, so a restore cannot overwrite its source
#    7. services       health-gated, one at a time, by upstream's update.sh
#
#  Idempotent throughout: run it again on a live cluster and it changes nothing it does not need to.
#
#  Usage:  sudo bash deploy/bring-up.sh
# ==================================================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_N=$'\e[0m'
step(){ echo -e "\n${C_C}━━━ $* ━━━${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ! $*${C_N}"; }

# ── 1 ─────────────────────────────────────────────────────────────────────────────────────────
step "preflight"
if [[ -x "$ROOT/platform/deploy/k3s/preflight.sh" ]]; then
  bash "$ROOT/platform/deploy/k3s/preflight.sh"
else
  warn "no preflight in the submodule — skipping (check it out: git -C platform sparse-checkout disable)"
fi

# ── 2 ─────────────────────────────────────────────────────────────────────────────────────────
step "datastores"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl apply -f "$ROOT/platform/deploy/k3s/platform/datastores.yaml" >/dev/null
kubectl -n "$NS" rollout status statefulset/postgres --timeout=300s >/dev/null
ok "postgres and redis are up"

# ── 3 ─────────────────────────────────────────────────────────────────────────────────────────
# BEFORE the services, deliberately. Raising the ceiling after they have filled it means a restart
# of the whole fleet to benefit from it — which is the rollout that cannot complete while the
# ceiling is full. Order is the difference between a setting and an outage.
step "connection ceiling"
bash "$HERE/hooks/post-datastores.sh"

# ── 4 ─────────────────────────────────────────────────────────────────────────────────────────
# THEIRS, called rather than reimplemented. It mints the shared values once — INTERNAL_SERVICE_TOKEN,
# PII_SALT, SECRETS_KEK, BACKUP_KEK, the postgres password — and writes them byte-identically into
# every secret that references them. Two different PII_SALTs would pseudonymise the same person two
# different ways, which is a data-integrity fault, not a cosmetic one.
#
# It preserves values that already exist, so re-running it never rotates a live secret out from
# under a running pod.
step "secrets"
python3 "$ROOT/platform/deploy/server/gen-secrets.py"
ok "secrets minted (shared values identical across services)"

# ── 5 & 6 ─────────────────────────────────────────────────────────────────────────────────────
step "databases and buckets"
bash "$HERE/hooks/pre-deploy.sh"

# ── 7 ─────────────────────────────────────────────────────────────────────────────────────────
# Upstream's, health-gated, ONE SERVICE AT A TIME. Not a loop of our own: a hand-written parallel
# restart is what exhausted the connection pool and deadlocked this cluster once already. The
# sequential gate is the feature, not the slow part.
step "services"
PRODUCT_NAME=raje3 CHART="$ROOT/platform/deploy/chart" VALUES_DIR="$ROOT/deploy/services" \
  bash "$ROOT/platform/deploy/server/update.sh"

# ── verify ────────────────────────────────────────────────────────────────────────────────────
# The rollout reports what helm told it. This reads what the cluster is RUNNING, which is the only
# claim worth making at the end of an install.
step "verify"
bash "$HERE/verify-pinned.sh"
