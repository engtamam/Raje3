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
#    1. cluster        k3s itself, encrypted at rest, before anything says the word kubectl
#    2. datastores     postgres and redis must exist before a secret can name a DSN, and the
#                      network preflight runs after them, because it measures a CNI that
#                      does not exist until the bootstrap installs it
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

# ── 0b ────────────────────────────────────────────────────────────────────────────────────────
# THE CLUSTER, BEFORE ANYTHING THAT SPEAKS TO ONE. Every step below — the preflight, the object
# store credential, upstream's own bootstrap — begins by calling kubectl. On a machine that has
# been installed before, that is free. On a virgin host it is the whole install failing in its
# first ten seconds with `kubectl: command not found`, which reads like a broken bundle and is
# nothing but an order-of-operations mistake. Upstream's bootstrap installs k3s too — but its
# main() runs `need kubectl` FIRST, so it dies on the same host for the same reason.
#
# AND WE INSTALL IT WITH --secrets-encryption, which is the reason this is ours rather than a call
# to theirs. That flag belongs to the k3s SERVER at start time: a cluster brought up without it
# cannot be talked into it later, `secrets-encrypt enable` returns success while the status stays
# Disabled, and every secret we then write — the postgres password, the token behind every
# internal call, the session-signing key, PII_SALT — sits in etcd as base64 for the life of the
# machine. PII_SALT is frozen by product identifiers; if it leaks it cannot be rotated, only
# regretted. The one moment this is fixable is the moment below, and it lasts one command.
#
# The other flags mirror theirs exactly (flannel off, Calico brings the policy CNI, no traefik) —
# drift here would give us a cluster their bootstrap then tries to correct.
step "cluster"
if command -v k3s >/dev/null 2>&1; then
  ok "k3s already installed — left as it is"
else
  command -v curl >/dev/null 2>&1 || { echo "  curl is required to install k3s" >&2; exit 1; }
  echo "  installing k3s (Calico CNI, traefik off, secrets encrypted at rest)"
  curl -sfL https://get.k3s.io | INSTALL_K3S_CHANNEL="${K3S_CHANNEL:-stable}" sh -s - \
    --flannel-backend=none --disable-network-policy --disable traefik \
    --write-kubeconfig-mode 644 --secrets-encryption \
    || { echo "  k3s install failed" >&2; exit 1; }
  ok "k3s installed"
fi
command -v kubectl >/dev/null 2>&1 || ln -sf /usr/local/bin/k3s /usr/local/bin/kubectl
export PATH="/usr/local/bin:$PATH"
# READY, NOT MERELY INSTALLED. The API server answers seconds after the installer returns, and a
# kubectl that runs one second too early fails in a way that looks like a permission problem.
for _ in $(seq 1 60); do kubectl get --raw=/readyz >/dev/null 2>&1 && break; sleep 2; done
kubectl get --raw=/readyz >/dev/null 2>&1 || { echo "  the API server never became ready" >&2; exit 1; }
ok "API server answering"

# AND HELM, WHICH NOTHING ELSE ON THIS PATH INSTALLS. update.sh refuses without it and points at
# `provision-server.sh` — a script for provisioning a bare host, which is not what a bundle install
# runs. So the refusal arrived twenty minutes in, after the datastores, the secrets and the keypair
# were all already on disk: the longest possible walk to a missing 40MB binary. Same source as
# upstream's own install_helm, so the two cannot drift.
if command -v helm >/dev/null 2>&1; then
  ok "helm present ($(helm version --short 2>/dev/null || echo '?'))"
else
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash >/dev/null 2>&1 \
    || { echo "  helm install failed — nothing below can deploy a chart" >&2; exit 1; }
  ok "helm installed ($(helm version --short 2>/dev/null || echo '?'))"
fi

# THE REGISTRY CREDENTIAL, HERE, because this is the first moment a cluster exists and the last
# moment before anything pulls. Our images are private: without it every pod sits in
# ImagePullBackOff, a failure that reads like a broken cluster and is a missing password.
if [[ -n "${GHCR_TOKEN:-}" ]]; then
  kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  kubectl -n "$NS" create secret docker-registry ghcr \
    --docker-server=ghcr.io --docker-username="${GHCR_USER:-x}" --docker-password="$GHCR_TOKEN" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null && ok "ghcr credential in place"
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
# THEIRS, CALLED — NOT REBUILT. And this file spent an afternoon learning why.
#
# `platform/deploy/k3s/bootstrap.sh` installs k3s with flannel off, Calico, metrics-server, the
# namespace with the label the chart's policies select on, THE POSTGRES TLS CERT, the datastore
# manifests pinned to the namespace, and the optional object store. We had reimplemented the
# middle of that list and silently dropped the rest — every one of which was invisible on a
# machine that had been installed before:
#
#   * the datastores landed in `default`, because their manifest declares no namespace and our
#     apply had no -n. Every service then looked for postgres.base-services.svc;
#   * `postgres-tls` was never minted, so the pod sat in ContainerCreating for ever and the only
#     place that said so was `describe pod`;
#   * the object store was never installed at all — ours is not the optional case, our values say
#     OBJECTSTORE_DRIVER=s3 — so backup-service answered `"object_store":"down"` for ever.
#
# THE RULE THIS ENCODES: call upstream's step or own it deliberately. What we do NOT do is write a
# second copy that starts equal and drifts, because the copy is always the one missing the fix.
#
# WHAT STAYS OURS, BELOW: the things base-services cannot know — our values, our seeds, the rs256
# keypair we chose over their shared secret, the audit chain key our driver choice requires, and a
# network preflight that does not depend on an attach this host cannot hold.

# THE OBJECT STORE'S CREDENTIAL, MINTED BEFORE THE BOOTSTRAP THAT LOOKS FOR IT.
# Their bootstrap applies the store only when OBJECTSTORE_ENABLED is set AND the secret exists —
# it refuses loudly otherwise, which is right: an object store with an example key in it is worse
# than none. One credential, generated here, used by the store and by every service that talks to
# it (the second half of that is below, after gen-secrets has created the service secrets).
step "object store credential"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
if kubectl -n "$NS" get secret objectstore-secrets >/dev/null 2>&1; then
  ok "already present — reused, never rotated (rotating orphans every object already written)"
else
  OSDIR="$(mktemp -d)"
  cat > "$OSDIR/s3.json" <<JSON
{
  "identities": [
    {
      "name": "base-services",
      "credentials": [{ "accessKey": "$(openssl rand -hex 16)", "secretKey": "$(openssl rand -base64 32 | tr -d '
')" }],
      "actions": ["Read", "Write", "List", "Tagging", "Admin"]
    }
  ]
}
JSON
  kubectl -n "$NS" create secret generic objectstore-secrets --from-file=s3.json="$OSDIR/s3.json" >/dev/null
  rm -rf "$OSDIR"
  ok "credential minted"
fi

step "bootstrap (k3s · calico · metrics · datastores · tls · object store)"
NAMESPACE="$NS" OBJECTSTORE_ENABLED=1 bash "$ROOT/platform/deploy/k3s/bootstrap.sh"   || { echo "  bootstrap failed — nothing after this point can work" >&2; exit 1; }

# AND THE PROBE THAT LETS POSTGRES SURVIVE ITS FIRST UNCLEAN SHUTDOWN. Applied after their
# manifest, every time, because a re-applied statefulset carries their probe again. The failure it
# prevents does not appear on a fresh database — it appears the first time the node dies with the
# database running, and then it is a CrashLoopBackOff that looks exactly like corruption. It took
# this whole fleet to 0/1 for half an hour.
bash "$HERE/patch-datastore-probes.sh" || warn "postgres probe patch failed — a crash recovery may loop"

# ── 2c ────────────────────────────────────────────────────────────────────────────────────────
# THE NETWORK PROOF, AFTER THE CNI THAT MAKES IT MEANINGFUL — and this order was learned on a
# fresh machine. It used to run first, which was fine on every host that had been installed
# before: Calico was already there. On a virgin box the node is NotReady, no pod gets an address
# at all, and the check reports «the server pod never became ready» — a sentence that reads as a
# broken cluster and means the CNI has not been installed yet. It cannot run earlier: what it
# measures IS the policy CNI, which upstream's bootstrap installs in the step above.
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

# ── 4a ────────────────────────────────────────────────────────────────────────────────────────
# AND ONLY NOW CAN POSTGRES START, which is why the wait moved here from the datastores step.
#
# Its StatefulSet reads the postgres password out of `platform-secrets` — a secret this script
# mints two steps later than it applied the manifest. So the old order waited five minutes for a
# pod that could not possibly start, timed out, and carried on: `CreateContainerConfigError:
# secret "platform-secrets" not found`, visible only in `describe pod`, while the install printed
# a bare «timed out waiting for the condition» and moved to the next step.
#
# It was invisible on any machine that had been installed before, because the secret was already
# there — the same shape as the namespace fault above, and the reason a fresh-machine test is the
# only honest test of an installer.
step "postgres"
kubectl -n "$NS" rollout status statefulset/postgres --timeout=600s >/dev/null   || { echo "  postgres did not become ready — see: kubectl -n $NS describe pod postgres-0" >&2; exit 1; }
ok "postgres and redis are up"

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

# ── 4b3 ───────────────────────────────────────────────────────────────────────────────────────
# THE SAME OBJECT-STORE KEY INTO EVERY SERVICE THAT TALKS TO THE STORE.
#
# The store's identity file was written before the bootstrap (which refuses to install the store
# without it); the services that use it only got their secrets a moment ago, from gen-secrets. So
# the second half happens here, reading the credential back out of the store's own secret — ONE
# source, so the copies cannot disagree. Three hand-copied values produce a 403 that reads like a
# bug in the uploader.
#
# WHICH SERVICES, read off the values files rather than listed here: a service that starts using
# the store tomorrow is covered by declaring the driver, not by editing this loop.
step "object store credential — shared out"
S3JSON="$(kubectl -n "$NS" get secret objectstore-secrets -o jsonpath="{.data.s3\.json}" | base64 -d)"
OS_ACCESS="$(printf %s "$S3JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["identities"][0]["credentials"][0]["accessKey"])')"
OS_SECRET="$(printf %s "$S3JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["identities"][0]["credentials"][0]["secretKey"])')"
A_B64="$(printf %s "$OS_ACCESS" | base64 -w0)"
S_B64="$(printf %s "$OS_SECRET" | base64 -w0)"
shared=0
for f in "$ROOT"/deploy/services/*.values.yaml; do
  grep -q 'OBJECTSTORE_DRIVER: *"s3"' "$f" || continue
  svc="$(basename "$f" .values.yaml)"
  kubectl -n "$NS" get secret "${svc}-secrets" >/dev/null 2>&1 || continue
  kubectl -n "$NS" patch secret "${svc}-secrets" --type=merge     -p "{\"data\":{\"OBJECTSTORE_ACCESS_KEY\":\"$A_B64\",\"OBJECTSTORE_SECRET_KEY\":\"$S_B64\"}}" >/dev/null
  shared=$((shared+1))
done
ok "object store credential shared with $shared service(s)"

# ── 4c ────────────────────────────────────────────────────────────────────────────────────────
# THE AUDIT CHAIN'S KEY — ours for the same reason the keypair is.
#
# Upstream's schema declares no INTEGRITY_HMAC_KEY, because their default integrity driver needs
# none. We set `INTEGRITY_DRIVER: hmac-chain` in audit-service's values on purpose: every audit
# row is chained to the one before it under a key, so a row cannot be altered or removed later
# without the chain saying so — which is the difference between a log and evidence.
#
# Choosing it made the key ours to provide, and nothing did. On a fresh install audit-service
# refuses to start at all — «INTEGRITY_HMAC_KEY must be set (>= 16 chars)» — and since every
# write-ahead audit in this product is fail-closed, a fleet without it is a fleet where the
# dangerous actions refuse. It was invisible on this cluster because the key was put there by
# hand months ago.
#
# IDEMPOTENT, AND NEVER ROTATED. A new key breaks the chain at the row it changes, and a broken
# chain cannot be told from a tampered one — which destroys the only property it has.
step "audit chain key"
if kubectl -n "$NS" get secret audit-service-secrets      -o jsonpath='{.data.INTEGRITY_HMAC_KEY}' 2>/dev/null | grep -q .; then
  ok "already present — reused, never rotated (a new key breaks the chain)"
else
  HMAC_B64="$(openssl rand -base64 48 | tr -d '
' | base64 -w0)"
  kubectl -n "$NS" patch secret audit-service-secrets --type=merge     -p "{\"data\":{\"INTEGRITY_HMAC_KEY\":\"$HMAC_B64\"}}" >/dev/null
  ok "audit chain key minted"
fi

# ── 4d ────────────────────────────────────────────────────────────────────────────────────────
# AUTHZ_INTERNAL_TOKEN — A KEY UPSTREAM'S SCHEMA DOES NOT KNOW, FOR A CHOICE ONLY WE MADE.
# We set IDENTITY_CAPS_SOURCE=authz, so identity asks authz what a role means instead of guessing,
# and that call goes to /internal/authz/effective — which authz guards with INTERNAL_SERVICE_TOKEN.
# Two different values and every login 401s; no value at all and identity refuses to BOOT, which is
# the better failure and the one that met us here: CrashLoopBackOff on a fleet that was otherwise
# healthy, with the reason legible only in the logs.
#
# gen-secrets.py has no AUTHZ_INTERNAL_TOKEN in its schema — it cannot, the key exists because of a
# configuration decision of ours. So it is the SAME shared token, copied here rather than generated:
# a fresh random value would be a second secret that must match a first one, which is the exact
# shape of the bug this copy prevents. On the old cluster this was a kubectl patch somebody ran by
# hand, and it survived every reinstall by being invisible.
step "authz internal token"
IST="$(kubectl -n "$NS" get secret identity-service-secrets -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null || true)"
CUR="$(kubectl -n "$NS" get secret identity-service-secrets -o jsonpath='{.data.AUTHZ_INTERNAL_TOKEN}'   2>/dev/null || true)"
if [[ -z "$IST" ]]; then
  warn "INTERNAL_SERVICE_TOKEN not in identity-service-secrets — cannot derive AUTHZ_INTERNAL_TOKEN"
elif [[ "$IST" == "$CUR" ]]; then
  ok "already matches the shared internal token"
else
  kubectl -n "$NS" patch secret identity-service-secrets --type=merge \
    -p "{\"data\":{\"AUTHZ_INTERNAL_TOKEN\":\"$IST\"}}" >/dev/null
  ok "identity may now ask authz what a role means"
fi

# ── 5 & 6 ─────────────────────────────────────────────────────────────────────────────────────
step "databases and buckets"
bash "$HERE/hooks/pre-deploy.sh"

# ── 6b ────────────────────────────────────────────────────────────────────────────────────────
# AND THE SIX SECRETS UPSTREAM'S GENERATOR CANNOT KNOW ABOUT — it builds its schema by reading the
# config of every service under ITS tree, and ours are in this repository. After the databases,
# because each of ours names one.
step "our services' secrets"
bash "$HERE/mint-our-secrets.sh"

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
# THE BACKUP TARGETS — runtime data, and nothing was creating it.
#
# The fleet came up green with backup-service deployed, a bucket, and BACKUP_KEK shared everywhere,
# and NOTHING was backed up: targets are rows, no script wrote any, and the scheduler reported
# success against an empty list. The day postgres is lost, operations — the only holder of
# customers' phone numbers in the clear — has no archive, and the first sign of it is the restore.
bash "$HERE/seed/seed-backup-targets.sh" || echo "  (backup targets: see above)"

# AND THE SEED THAT LIVES INSIDE THE SERVICE, WHICH DEPENDS ON AN ORDER NOTHING GUARANTEES.
# operations seeds its sectors and its 78 templates on the first boot that finds an empty table.
# On this install it booted before its database existed — the databases were being created in
# another step — so it found nothing to seed and never looked again. Everything then reported
# success: the pod was ready, the endpoint answered 200, and it answered `{"sectors":[]}`.
#
# The owner met it at the only place it shows: «نوع النشاط» on the sign-up form, empty, with a red
# line under it. So we ask the service what it has, and if the answer is nothing we restart it once
# — a boot with a database behind it seeds in under a second.
if kubectl -n "$NS" get deploy operations >/dev/null 2>&1; then
  SECTORS="$(kubectl -n "$NS" exec deploy/operations -- python -c "
import urllib.request, json
print(len(json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/signup/sectors'))['sectors']))
" 2>/dev/null || echo 0)"
  if [ "${SECTORS:-0}" -gt 0 ]; then
    ok "sectors present ($SECTORS)"
  else
    echo "  no sectors — restarting operations so it seeds against a database that now exists"
    kubectl -n "$NS" rollout restart deploy/operations >/dev/null
    kubectl -n "$NS" rollout status deploy/operations --timeout=180s >/dev/null 2>&1 || true
    SECTORS="$(kubectl -n "$NS" exec deploy/operations -- python -c "
import urllib.request, json
print(len(json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/signup/sectors'))['sectors']))
" 2>/dev/null || echo 0)"
    [ "${SECTORS:-0}" -gt 0 ] && ok "sectors seeded ($SECTORS)"       || warn "still no sectors — the sign-up form will show an empty «نوع النشاط»"
  fi
fi

# ── 9 ─────────────────────────────────────────────────────────────────────────────────────────
# THE EDGE, WHICH NOTHING USED TO APPLY. Every service could be healthy, every secret minted, every
# database provisioned — and the domain answered nothing, because the one component that owns port
# 443 was a file somebody remembered to run by hand. A from-nothing install found it in the only
# way it could: by finishing successfully and serving no one.
#
# THE CADDYFILE IS RENDERED, NEVER WRITTEN. base-services turns edge.json into Caddy config with a
# pure function, validating every value first — a hostname that does not parse stops the install
# instead of becoming a site block. Our hostname and TLS flag are stamped in from what the
# installer asked, so the certificate, the routed host and the URLs the console calls are one
# answer given once.
step "edge"
EDGE_SRC="$HERE/edge/edge.json"
if [[ ! -f "$EDGE_SRC" ]]; then
  warn "no deploy/edge/edge.json — the domain will answer nothing"
else
  EDGE_TMP="$(mktemp -d)"
  # DOMAIN decides TLS: a name in public DNS gets a real certificate, and a box without one must
  # not ask Let's Encrypt for `localhost` — five failed attempts is a week-long rate limit.
  python3 - "$EDGE_SRC" "$EDGE_TMP/edge.json" "${DOMAIN:-}" "${ACME_EMAIL:-}" <<'PYEOF'
import json, sys
src, dst, domain, email = sys.argv[1:5]
cfg = json.load(open(src, encoding='utf-8'))
if domain:
    cfg['domain'] = domain
    cfg['tls'] = True
    if email:
        cfg['acme_email'] = email
json.dump(cfg, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
PYEOF
  # JUDGED BY THE FILE, NOT BY THE EXIT CODE — and that is upstream's bug, not a shortcut of ours.
  # render.py writes the Caddyfile and THEN prints a line that calls relative_to() on the output
  # path against its own root; give it an EDGE_OUT anywhere else and the print raises, after the
  # render has already succeeded. Escalated. Meanwhile the artefact is the truth: a non-empty
  # Caddyfile means the config was accepted and validated, and an empty one means it was not.
  EDGE_CONFIG="$EDGE_TMP/edge.json" EDGE_OUT="$EDGE_TMP/Caddyfile"     python3 "$ROOT/platform/tools/edge/render.py" >"$EDGE_TMP/render.out" 2>&1 || true
  if [[ -s "$EDGE_TMP/Caddyfile" ]]; then
    kubectl -n "$NS" create configmap edge-caddyfile --from-file=Caddyfile="$EDGE_TMP/Caddyfile"       --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    # THE CONSOLE FIRST — the edge's catch-all route names it, and a Caddy that cannot resolve an
    # upstream at start refuses to load the config rather than serving the rest.
    kubectl apply -n "$NS" -f "$HERE/edge/console.yaml" >/dev/null
    kubectl apply -n "$NS" -f "$HERE/edge/deployment.yaml" >/dev/null
    # A CHANGED CONFIGMAP DOES NOT RESTART A POD. Caddy reads its file at start, so without this the
    # rendered routes sit in the cluster while the edge keeps serving the previous ones.
    kubectl -n "$NS" rollout restart deployment/edge >/dev/null 2>&1 || true
    ok "edge serving ${DOMAIN:-localhost}${DOMAIN:+ over TLS}"
  else
    warn "edge config rejected — the domain will answer nothing:"
    sed 's/^/      /' "$EDGE_TMP/render.out" | tail -6
  fi
  rm -rf "$EDGE_TMP"
fi

# ── verify ────────────────────────────────────────────────────────────────────────────────────
# The rollout reports what helm told it. This reads what the cluster is RUNNING, which is the only
# claim worth making at the end of an install.
step "verify"
bash "$HERE/verify-pinned.sh"
