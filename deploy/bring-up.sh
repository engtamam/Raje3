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
#  Usage:  sudo bash deploy/bring-up.sh            # install or reconcile — safe on a live cluster
#          sudo bash deploy/bring-up.sh --wipe     # DESTROY EVERYTHING FIRST, then install
#
#  --wipe DELETES THE PRODUCT'S DATA: every tenant, every customer, every visit, every invoice, and
#  the secrets that decrypt the backups. It exists so that "does our install work from nothing" can
#  be ANSWERED rather than believed — an install script that is only ever run on a machine it has
#  already run on is a script nobody has tested.
#
#  AND IT WIPES THE HOST DIRECTORY, NOT ONLY THE PVC. Deleting a k3s local-path claim leaves the
#  directory behind, so a "fresh" postgres reuses stale data, skips first-time init, and never
#  creates the database — leaving every service 0/1 on a datastore that answers but has no schema.
#  That is the trap this flag is written around.
# ==================================================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
NS="${NS:-base-services}"
STORAGE="${STORAGE:-/var/lib/rancher/k3s/storage}"
WIPE=0
for a in "$@"; do case "$a" in
  --wipe) WIPE=1;;
  -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
  *) echo "unknown flag: $a" >&2; exit 2;;
esac; done
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_N=$'\e[0m'
step(){ echo -e "\n${C_C}━━━ $* ━━━${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ! $*${C_N}"; }

# ── 0 ─────────────────────────────────────────────────────────────────────────────────────────
# NOTHING, ON PURPOSE, unless --wipe. The default path must stay safe to run against production.
if [[ $WIPE -eq 1 ]]; then
  step "wipe"
  echo "  deleting namespace $NS, its volumes, and their host directories"
  # helm releases first: a namespace deleted out from under helm leaves its release metadata
  # behind, and the next install refuses with "cannot re-use a name that is still in use".
  helm list -n "$NS" -q 2>/dev/null | xargs -r -n1 helm uninstall -n "$NS" >/dev/null 2>&1 || true
  kubectl delete namespace "$NS" --wait=true --timeout=180s >/dev/null 2>&1 || true
  # AND THE DIRECTORIES. A PVC's local-path directory outlives the claim, and a postgres that finds
  # a populated data dir does not initialise — which is the failure this whole flag exists to make
  # impossible to reproduce by accident.
  rm -rf "$STORAGE"/pvc-* 2>/dev/null || true
  ok "namespace, volumes and host directories are gone"
fi

# ── 1 ─────────────────────────────────────────────────────────────────────────────────────────
step "preflight"
# OURS FIRST, AND IT IS NOT A DUPLICATE. Upstream's proves the same property by reading its answer
# over an interactive attach; on this host that attach fails under load and the check then reports
# "the cluster's networking is broken" — while the same probe run by hand prints REACHABLE. A
# security gate that can fail for a reason unrelated to what it measures is a gate people learn to
# skip, and then the day enforcement is really off nobody finds out. Ours reads the result from pod
# logs, which need no session.
bash "$HERE/preflight-netpol.sh" || exit 1

# THEIRS STILL RUNS, for the checks ours does not make — metrics-server and namespace labels — and
# its network verdict is no longer the thing that stops the install, because we have just proven
# that property ourselves, twice, in both directions.
if [[ -x "$ROOT/platform/deploy/k3s/preflight.sh" ]]; then
  bash "$ROOT/platform/deploy/k3s/preflight.sh"     || warn "upstream preflight reported a failure — network policy was already proven above; check the rest"
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
    # AND THE REMEDY IS AT INSTALL TIME, NOT HERE. `secrets-encrypt enable` reports success on
    # this host and the status stays Disabled — the switch belongs to the k3s SERVER, and a
    # cluster started without `--secrets-encryption` cannot be talked into it afterwards. Printing
    # the runtime command was worse than printing nothing: somebody runs it, sees no error, and
    # believes the secrets are encrypted.
    warn "STILL NOT ENABLED — every secret is base64 in etcd, and this cannot be fixed at runtime."
    warn "  the k3s server must be STARTED with --secrets-encryption (INSTALL_K3S_EXEC),"
    warn "  then: sudo k3s secrets-encrypt reencrypt --force"
    warn "  a cluster already holding customer data needs that restart planned, not improvised."
  fi
fi

# ── 2 ─────────────────────────────────────────────────────────────────────────────────────────
step "datastores"
# A NAMESPACE THAT IS STILL TERMINATING ACCEPTS NOTHING, and refuses with "object is being
# deleted" — which the old `>/dev/null` swallowed, so the install carried on and failed one line
# later on `statefulset postgres not found`, an error naming the symptom and not the cause. It
# cost twenty minutes to read the second time. Wait for it, then apply LOUDLY.
for _ in $(seq 1 60); do
  phase="$(kubectl get namespace "$NS" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")"
  [[ "$phase" == "Terminating" ]] || break
  sleep 5
done
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# THE TLS CERT POSTGRES MOUNTS, MINTED BEFORE THE STATEFULSET THAT MOUNTS IT.
#
# Without it the pod sits in ContainerCreating for ever — «MountVolume.SetUp failed for volume
# "tls": secret "postgres-tls" not found» — and the only place that says so is `describe pod`. The
# rollout above just times out. It is upstream's function, in their bootstrap, and our install
# never called it: on this cluster the secret already existed from an older install, so the gap was
# invisible until the machine was truly empty.
#
# IDEMPOTENT AND STICKY: an existing secret is left alone, so a re-run neither rotates the cert nor
# bounces the database for no reason.
if ! kubectl -n "$NS" get secret postgres-tls >/dev/null 2>&1; then
  command -v openssl >/dev/null 2>&1 || { echo "  openssl is required to mint the postgres TLS cert" >&2; exit 1; }
  TLSDIR="$(mktemp -d)"
  # SANs COVER THE IN-CLUSTER NAMES, so the same cert still works if a later deployment tightens
  # from `require` to `verify-full` — no re-mint, and no CA to run.
  openssl req -new -x509 -nodes -days 3650 -subj "/CN=postgres"     -addext "subjectAltName=DNS:postgres,DNS:postgres.${NS}.svc,DNS:postgres.${NS}.svc.cluster.local"     -keyout "$TLSDIR/tls.key" -out "$TLSDIR/tls.crt" >/dev/null 2>&1     || { echo "  openssl could not mint the postgres TLS cert" >&2; exit 1; }
  kubectl -n "$NS" create secret tls postgres-tls --cert="$TLSDIR/tls.crt" --key="$TLSDIR/tls.key" >/dev/null
  rm -rf "$TLSDIR"
  ok "postgres TLS cert minted"
fi

# NOT SILENCED. An apply that fails here leaves every following step failing for reasons that read
# like unrelated faults; the one line it prints is the whole diagnosis.
# `-n "$NS"` IS THE WHOLE LINE, and its absence was invisible for as long as an older install
# existed. The manifest declares no namespace of its own, so a bare apply writes postgres and redis
# into `default` — while every service, every secret and the rollout check that follows all look in
# `base-services`. On a cluster that had been installed before, the resources were already in the
# right place and `apply` reported "unchanged" about the wrong ones; the fault only surfaced on a
# genuinely empty machine, which is exactly the case an install script exists for.
if ! kubectl apply -n "$NS" -f "$ROOT/platform/deploy/k3s/platform/datastores.yaml"; then
  echo "  the datastore manifest did not apply — nothing after this step can work" >&2
  exit 1
fi
kubectl -n "$NS" rollout status statefulset/postgres --timeout=300s >/dev/null
ok "postgres and redis are up"

# AND THE PROBE THAT LETS IT SURVIVE ITS FIRST UNCLEAN SHUTDOWN.
#
# Applied here, at install, because the failure it prevents does not appear on a fresh database —
# it appears the first time the node dies with the database running, weeks later, and then it is a
# CrashLoopBackOff that looks exactly like corruption. On this cluster it took the whole fleet to
# 0/1 for half an hour: postgres was fsyncing a recovered data directory, the liveness probe
# allowed sixty seconds for a pass that needed minutes, and each kill restarted the recovery from
# the beginning. Eight times.
#
# It patches upstream's statefulset rather than editing their manifest — theirs is read-only to us
# — and it is idempotent, so a re-run of this script changes nothing.
bash "$HERE/patch-datastore-probes.sh" || warn "postgres probe patch failed — a crash recovery may loop"

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

# ── 4b ────────────────────────────────────────────────────────────────────────────────────────
# THE RS256 KEYPAIR, WHICH UPSTREAM'S SCHEMA DOES NOT KNOW ABOUT.
#
# secrets.schema.json declares TOKEN_HS256_SECRET and nothing else about tokens: it assumes a
# shared symmetric secret. We run rs256 on purpose — identity SIGNS and every other service only
# VERIFIES, so one compromised service cannot mint a session for any tenant. That choice makes the
# keypair ours to provision, and until now nothing did: the keys on the live cluster were put there
# by hand, which meant a fresh install had a fleet configured for rs256 and no keys to use.
#
# AND IDENTITY NEEDS BOTH HALVES. It is easy to read "identity signs" and give it only the private
# key, and that is exactly what happened — /auth/refresh must VERIFY the refresh token it is handed
# before it mints anything, so with no public key its verifier stayed at the `null` deny-by-default
# driver and EVERY renewal returned 401. Sign-in still worked (it checks a password, not a token),
# /readyz stayed green, and the only symptom was an owner thrown back to the login screen every 15
# minutes — the access TTL — while holding a refresh token good for 31 days.
#
# Idempotent: an existing keypair is reused, never rotated. Rotating it would invalidate every live
# session and refresh token on the platform at once.
step "token keypair (rs256)"
KEYDIR="$(mktemp -d)"; trap 'rm -rf "$KEYDIR"' EXIT
if kubectl -n "$NS" get secret identity-service-secrets \
     -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | grep -q .; then
  kubectl -n "$NS" get secret identity-service-secrets \
    -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' | base64 -d > "$KEYDIR/private.pem"
  ok "keypair already present — reused, never rotated"
else
  openssl genrsa -out "$KEYDIR/private.pem" 2048 2>/dev/null
  ok "keypair minted"
fi
openssl rsa -in "$KEYDIR/private.pem" -pubout -out "$KEYDIR/public.pem" 2>/dev/null
PRIV_B64="$(base64 -w0 < "$KEYDIR/private.pem")"
PUB_B64="$(base64 -w0 < "$KEYDIR/public.pem")"

# Identity holds both. Everyone else holds only the public half — and WHO those are is read off the
# values files rather than listed here, so a service added tomorrow is covered by declaring its own
# verifier, not by remembering to edit this loop.
kubectl -n "$NS" patch secret identity-service-secrets --type=merge \
  -p "{\"data\":{\"TOKEN_PRIVATE_KEY\":\"$PRIV_B64\",\"TOKEN_PUBLIC_KEY\":\"$PUB_B64\"}}" >/dev/null
ok "identity-service: private + public"

verifiers=0
for f in "$HERE"/services/*.values.yaml; do
  grep -q 'TOKEN_VERIFIER_DRIVER: *"rs256"' "$f" || continue
  svc="$(basename "$f" .values.yaml)"
  [[ "$svc" == "identity-service" ]] && continue
  kubectl -n "$NS" get secret "${svc}-secrets" >/dev/null 2>&1 || continue
  kubectl -n "$NS" patch secret "${svc}-secrets" --type=merge \
    -p "{\"data\":{\"TOKEN_PUBLIC_KEY\":\"$PUB_B64\"}}" >/dev/null
  verifiers=$((verifiers + 1))
done
ok "public key distributed to $verifiers verifying service(s)"

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

# ── 8 ─────────────────────────────────────────────────────────────────────────────────────────
# THE INSTALL ENDED HERE, AND THE CLUSTER WAS EMPTY. Every service ran, every probe was green, and
# the product had no roles, no price list, no legal library and no sector definitions — because
# nothing in this script had ever applied a single seed. The gap was invisible in exactly the way
# this file's own verify step was built to catch elsewhere: a truthful report about the wrong
# thing. A shop signing up on a fresh install would have got a login it could do nothing with.
#
# ORDER MATTERS AND IS NOT ALPHABETICAL:
#   roles first  — everything after this needs a capability to exist before it can be granted;
#   plans next   — the subscribe path reads a plan's trial before it will take money;
#   legal last   — it gates a signup, so it must be publishable before the first one happens.
#
# EACH ONE IS IDEMPOTENT AND SAYS SO. Re-running the install must not overwrite an operator's
# edits: seeders create what is missing and leave what exists, which is why they are safe here
# rather than dangerous.
#
# TEMPLATES ARE ABSENT ON PURPOSE. The WhatsApp library is submitted PER ESTABLISHMENT at the
# moment its account connects (§6.6.1) — a platform-wide push would be a submission to nobody's
# account. seed-templates.sh takes --tenant for that reason.
step "seed"
bash "$HERE/seed/seed-roles.sh"  || echo "  (roles: see above)"
bash "$HERE/seed/seed-plans.sh"  || echo "  (plans: see above)"
bash "$HERE/seed/seed-legal.sh"  || echo "  (legal: see above)"

# ── verify ────────────────────────────────────────────────────────────────────────────────────
# The rollout reports what helm told it. This reads what the cluster is RUNNING, which is the only
# claim worth making at the end of an install.
step "verify"
bash "$HERE/verify-pinned.sh"
