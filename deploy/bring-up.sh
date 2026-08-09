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
#    3. pool preflight   refuse the install if the pools cannot fit before any of them is opened
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

# ── 1b ────────────────────────────────────────────────────────────────────────────────────────
# ENCRYPT THE SECRETS BEFORE ANY EXIST. This runs before the datastores and before gen-secrets,
# and the order is the entire point: `secrets-encrypt enable` only covers what is written AFTER
# it, so doing this first means nothing is ever written in the clear — and `reencrypt` becomes a
# repair rather than the thing we depend on.
#
# WITHOUT IT, EVERY SECRET IN THE PLATFORM SITS IN etcd AS base64, which is an encoding anybody
# reverses in one command. What is in there: the postgres password for every database, the token
# that authenticates every internal call, the key that opens every backup, the private key that
# mints a session for any tenant with any capability — and PII_SALT.
#
# PII_SALT IS THE ONE THAT CANNOT BE UNDONE. Every service but `operations` holds pseudonyms
# instead of people; the salt turns all of them back into phone numbers. It is a FROZEN identifier
# (config/product.identifiers.lock.json) — rotating it after a leak would orphan every immutable
# record we have, so the only defence is that it was never readable.
#
# k3s installs WITHOUT this, and platform/deploy/server/provision-server.sh does not mention it —
# escalated. Until it is theirs, it is ours, and it belongs in the install rather than in a runbook
# somebody follows on a good day.
step "secrets at rest"
if ! command -v k3s >/dev/null 2>&1; then
  warn "no k3s on this host — skipping (managed cluster? then encryption is the provider's setting)"
elif sudo k3s secrets-encrypt status 2>/dev/null | grep -qi "Encryption Status.*Enabled"; then
  ok "already enabled"
else
  sudo k3s secrets-encrypt enable >/dev/null 2>&1 || warn "could not enable — run it by hand"
  # AND REWRITE WHAT ALREADY EXISTS. On a fresh host there is nothing; on a cluster that has been
  # serving, everything already in etcd stays in the clear until this runs — while the status line
  # says Enabled either way, which is exactly the shape of a control that looks applied and is not.
  sudo k3s secrets-encrypt reencrypt >/dev/null 2>&1 || true
  if sudo k3s secrets-encrypt status 2>/dev/null | grep -qi "Encryption Status.*Enabled"; then
    ok "secrets are encrypted at rest"
  else
    warn "STILL NOT ENABLED — every secret is base64 in etcd. Fix before this host holds data:"
    warn "  sudo k3s secrets-encrypt enable && sudo k3s secrets-encrypt reencrypt"
  fi
fi

# ── 2 ─────────────────────────────────────────────────────────────────────────────────────────
step "datastores"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl apply -f "$ROOT/platform/deploy/k3s/platform/datastores.yaml" >/dev/null
kubectl -n "$NS" rollout status statefulset/postgres --timeout=300s >/dev/null
ok "postgres and redis are up"

# ── 3 ─────────────────────────────────────────────────────────────────────────────────────────
# Upstream's, and it is a REFUSAL, not a report. It computes services x DATASTORE_POOL_MIN against
# postgres's max_connections and fails the install when the guaranteed floor cannot fit — because
# a floor that does not fit is not a risk, it is a certain deadlock, and discovering it here beats
# discovering it during an upgrade at 2am.
#
# We used to patch max_connections to 300 here. That is gone: it existed to work around an
# unconfigurable pool that filled to ten per service and never released, and v0.13.0 fixed the pool
# itself (min 1, max 5, lazy, with idle connections returned). The arithmetic now reads
# floor 19, peak 95 against a stock ceiling of 100 — so the patch would be a divergence from
# upstream's defaults with no reason left behind it, costing an extra gigabyte of postgres memory
# on a node that does not have one to spare.
#
# If we ever scale a service past one replica the peak crosses the ceiling, and THIS STEP is what
# will say so, at install, in one line. The signal to raise it again is automatic; it is not
# something anyone has to remember.
step "database pool arithmetic"
VALUES_DIR="$ROOT/deploy/services" bash "$ROOT/platform/deploy/server/preflight-db-pool.sh"

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
