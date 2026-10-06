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

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_N=$'\e[0m'
step(){ echo -e "\n${C_C}━━━ $* ━━━${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ! $*${C_N}"; }

# ── WHAT DID NOT HAPPEN, CARRIED TO THE END ───────────────────────────────────────────────────
#
# Every seed step used to end `|| echo "  (…: see above)"`. `echo` in a subshell raises nothing,
# and this script had no flag to raise: the run printed a footnote and finished on the same
# «verify» line as a perfect install. Without seed-plans nothing can be sold, without seed-legal
# no company can register, and without seed-backup-targets the scheduler reports success against
# an empty list — so the first sign of the missing backup is the restore that finds nothing.
#
# `soft` runs a step that MAY fail, records that it did, and names it again at the end. The step
# still does not abort the install — a missing seed is worth continuing past — but nobody is told
# the install completed when part of it did not.
FAILED=()
soft(){
  local what="$1"; shift
  if ! "$@"; then
    FAILED+=("$what")
    warn "$what: failed — see above"
  fi
}

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

# THE SEAM COMES AFTER k3s, NOT BEFORE IT. Every other script asks cluster.sh where the cluster
# is; this one is what makes there be an answer, so it asks only once k3s has written its
# kubeconfig. Sourcing at the top would have this script refuse to install a cluster on the
# grounds that no cluster is installed.
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
export PATH="/usr/local/bin:$PATH"
# READY, NOT MERELY INSTALLED. The API server answers seconds after the installer returns, and a
# kubectl that runs one second too early fails in a way that looks like a permission problem.
for _ in $(seq 1 60); do kubectl get --raw=/readyz >/dev/null 2>&1 && break; sleep 2; done
kubectl get --raw=/readyz >/dev/null 2>&1 || { echo "  the API server never became ready" >&2; exit 1; }
ok "API server answering"

# ── 1a ────────────────────────────────────────────────────────────────────────────────────────
# AFTER THE API ANSWERS, NOT BEFORE. Wiping is a conversation with a cluster: on a virgin host
# there is nothing to delete, and on an existing one every command below would otherwise be
# aimed at an API server nobody has confirmed is up — and each is `|| true`, so it would have
# reported a successful wipe of a namespace it never reached.
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

# ── 2b ────────────────────────────────────────────────────────────────────────────────────────
# EVERY MANIFEST UNDER deploy/k3s/, APPLIED HERE, ALWAYS — not a step anyone remembers to run by
# hand after a fresh install. THIS WAS THE ACTUAL BUG, three separate times in one night: the
# translation-model PVC+Job, secrets-admin's own ServiceAccount/Role/RoleBinding, and the
# datastore NetworkPolicy all lived in this directory as "apply this yourself" files with nothing
# in the install path that ever did — each one silently missing after the SAME fresh reinstall
# (secrets-admin's pod simply never existed; operations sat Pending on a PVC that was never
# created; then, once the netpol WAS applied by hand, a bug in it — fixed the same night, see the
# file's own note — took the whole fleet's postgres connectivity down because nothing had ever
# exercised that exact file on a real bring-up before). Looping every *.yaml here, every time,
# turns "a human has to remember and re-run four separate tool calls after every reinstall" into
# "the install script already did it" — the gap cannot reopen because there is no longer a manual
# step to forget.
#
# edge.yaml IS THE ONE DELIBERATE EXCEPTION — confirmed stale: `deploy/edge/console.yaml` and
# `deploy/edge/deployment.yaml` are what step "edge" below actually applies (a different
# directory, from before the deploy/edge/ split), and this file would create a second, dueling
# `edge` Service/Deployment/NetworkPolicy from a superseded definition if it were ever applied.
step "our own k3s manifests (deploy/k3s/*.yaml)"
for f in "$ROOT"/deploy/k3s/*.yaml; do
  name="$(basename "$f")"
  [ "$name" = "edge.yaml" ] && { warn "skipping $name — superseded by deploy/edge/, see this step's own note"; continue; }
  kubectl apply -f "$f" >/dev/null && ok "applied $name" || warn "failed to apply $name — check it by hand"
done

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

# OUR OWN first-party services (services/* at the repo root — affiliate-service, operations,
# campaigns, bookings, loyalty, insights, portal, reminders) live outside the platform submodule,
# so the call above never sees them; it only scans platform/services. deploy/gen-secrets.py is a
# close mirror of it scoped to our own services/ tree, and it REUSES the shared values just minted
# above rather than minting its own — see its own module docstring for why a second, independent
# PII_SALT would be a real data-integrity bug, not a style choice. Without this step, every one of
# our own services needed its k3s secret created by hand the first time it went live; this closes
# that gap for good, on any server, on a first install.
step "secrets (first-party)"
python3 "$ROOT/deploy/gen-secrets.py"
ok "first-party secrets minted (reused shared values, no drift from the platform's own)"

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
  # WAS "rs256" — this fleet's services all declare their driver as "jwks" now (checked directly
  # against every deploy/services/*.values.yaml: zero files say rs256/rsa256, twenty-six say
  # jwks). Whatever service historically used "rs256" was renamed at some point and this pattern
  # never followed, so this loop has matched NOTHING on any install since — see the second loop's
  # own note, below, for how that surfaced.
  grep -q 'TOKEN_VERIFIER_DRIVER: *"jwks"' "$f" || continue
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

# -- 4b4 ---------------------------------------------------------------------------------------
# THE PUBLIC ADDRESS, INTO EVERY SERVICE THAT COMPOSES ONE.
#
# WHAT WAS WRONG FOR FIVE DAYS. reminders' values carry `PUBLIC_BASE_URL: ""` under a comment
# saying it is left empty until an install fills it. No install filled it. The installer asked for
# the domain, rendered it into the edge, and printed `https://<DOMAIN>/p/...` on the way out --
# and the one service that turns that path into a tappable address never received it.
#
# `core/links.py` then refused to compose, correctly, and every message carrying a link died at
# RENDER: before the send log, before any screen. The customer's stop and grant screens were live
# and answering the whole time. The address was known by everyone except the process that needed it.
#
# SELECTED BY THE DECLARATION, not by a list. A service that starts composing links tomorrow is
# covered by declaring the key, the same way the verifier and object-store loops above work.
#
# AND EMPTY DOMAIN STAYS EMPTY. A local box has no public name, and a guess would send a pilot's
# customers to somebody else's domain while delivery still reported success.
step "public address -- shared out"
if [ -n "${DOMAIN:-}" ]; then
  PUBLIC_BASE="https://${DOMAIN}"
  addressed=0
  for f in "$ROOT"/deploy/services/*.values.yaml; do
    # SELECTED BY THE KEY, NOT BY ITS BEING EMPTY. It used to require `""`, and that made the
    # repository's own value a decision this installer had to respect: once a values file carried
    # `https://ra-je3.com`, an install for a DIFFERENT domain skipped it silently and the new
    # cluster composed links pointing at somebody else's site. The installer was asked for the
    # domain; it is the authority. So it overwrites whatever the file happens to hold.
    grep -qE '^[[:space:]]*PUBLIC_BASE_URL:[[:space:]]*' "$f" || continue
    svc="$(basename "$f" .values.yaml)"
    kubectl -n "$NS" get cm "$svc" >/dev/null 2>&1 || continue
    kubectl -n "$NS" patch cm "$svc" --type=merge \
      -p "{\"data\":{\"PUBLIC_BASE_URL\":\"$PUBLIC_BASE\"}}" >/dev/null
    kubectl -n "$NS" rollout restart deploy "$svc" >/dev/null 2>&1 || true
    addressed=$((addressed + 1))
  done
  ok "public address $PUBLIC_BASE given to $addressed service(s)"
else
  # NOT A WARNING TO SCROLL PAST. Without a domain the marketing path cannot run at all, and the
  # operator should learn that here rather than from a campaign that sends nothing.
  warn "no DOMAIN: PUBLIC_BASE_URL stays empty, so no message carrying a link can be composed --
       service messages are unaffected, marketing cannot be sent"
fi

# ── 4b2 ───────────────────────────────────────────────────────────────────────────────────────
# THE ARCHIVE'S OWN BUCKET — same shape as PUBLIC_BASE_URL just above, one step up: install.sh is
# the one that REFUSES an unset bucket (a machine already carrying another machine's bucket name
# must never be silently accepted), so by the time this step runs OSS_BUCKET is either a real
# answer or the installer explicitly said REUSE_ARCHIVE_BUCKET=1. This step only ever WRITES —
# an empty OSS_BUCKET here means bring-up.sh was invoked directly, outside install.sh's gate, and
# the values file's own bucket is left exactly as it is, same as DOMAIN above.
step "archive bucket -- shared out"
if [ -n "${OSS_BUCKET:-}" ] && [ -n "${OSS_ENDPOINT:-}" ]; then
  # THE REGION IS DERIVED, NEVER ASKED TWICE. OSS names its region in the endpoint's own host
  # (`oss-me-central-1.aliyuncs.com` -> `me-central-1`) — a second prompt for the same fact is a
  # second place it can be told two different answers.
  OSS_REGION="$(printf '%s' "$OSS_ENDPOINT" | sed -E 's#^https?://oss-([a-z0-9-]+)\.aliyuncs\.com/?$#\1#')"
  [ "$OSS_REGION" != "$OSS_ENDPOINT" ] || OSS_REGION="us-east-1"   # not an Alibaba OSS host — a
                                                                    # generic S3-compatible fallback
  f="$ROOT/deploy/services/backup-service.values.yaml"
  if grep -qE '^[[:space:]]*OBJECTSTORE_BUCKET:[[:space:]]*' "$f"; then
    kubectl -n "$NS" get cm backup-service >/dev/null 2>&1 && {
      kubectl -n "$NS" patch cm backup-service --type=merge -p "$(cat <<PATCHEOF
{"data":{"OBJECTSTORE_BUCKET":"$OSS_BUCKET","OBJECTSTORE_ENDPOINT_URL":"$OSS_ENDPOINT","OBJECTSTORE_REGION":"$OSS_REGION"}}
PATCHEOF
)" >/dev/null
      kubectl -n "$NS" rollout restart deploy backup-service >/dev/null 2>&1 || true
      ok "archive bucket $OSS_BUCKET given to backup-service"
    } || warn "backup-service not deployed yet -- the bucket answer is in the values file for its first rollout"
  fi
else
  warn "no OSS_BUCKET given to bring-up.sh directly: backup-service keeps whatever bucket
       deploy/services/backup-service.values.yaml already names -- correct only if this really is
       the same machine that bucket belongs to"
fi

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

# ── 4e ────────────────────────────────────────────────────────────────────────────────────────
# WHATSAPP_BOOKING_PROVIDER_TOKEN — THE SAME SHAPE AS AUTHZ_INTERNAL_TOKEN JUST ABOVE, ONE
# STEP DOWN. notification-service's booking-Flow adapter (adapters/booking/http.py) sends this
# value as X-Internal-Token when it calls OUR whatsapp-assistant
# (/internal/whatsapp-flow/booking) — a config key upstream's schema cannot know about, for a
# peer relationship only WE created. Copied here rather than generated, for the identical reason
# the comment above gives: a fresh random value would be a second secret that must match a first
# one it never will.
step "whatsapp booking provider token"
NIST="$(kubectl -n "$NS" get secret notification-service-secrets -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null || true)"
NCUR="$(kubectl -n "$NS" get secret notification-service-secrets -o jsonpath='{.data.WHATSAPP_BOOKING_PROVIDER_TOKEN}' 2>/dev/null || true)"
if [[ -z "$NIST" ]]; then
  warn "INTERNAL_SERVICE_TOKEN not in notification-service-secrets — cannot derive WHATSAPP_BOOKING_PROVIDER_TOKEN"
elif [[ "$NIST" == "$NCUR" ]]; then
  ok "already matches the shared internal token"
else
  kubectl -n "$NS" patch secret notification-service-secrets --type=merge \
    -p "{\"data\":{\"WHATSAPP_BOOKING_PROVIDER_TOKEN\":\"$NIST\"}}" >/dev/null
  ok "notification-service may now call whatsapp-assistant's booking Flow endpoint"
fi

# ── 4f ────────────────────────────────────────────────────────────────────────────────────────
# WHATSAPP_RENEWAL_PROVIDER_TOKEN — THE SAME SHAPE AS 4e JUST ABOVE, for the subscription-renewal
# Flow: notification-service's LoyaltyEngine(name="subscription_renewal") sends this as
# X-Internal-Token when it calls OUR operations service (/internal/whatsapp/renewal-provider).
step "whatsapp renewal provider token"
NIST="$(kubectl -n "$NS" get secret notification-service-secrets -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null || true)"
NCUR="$(kubectl -n "$NS" get secret notification-service-secrets -o jsonpath='{.data.WHATSAPP_RENEWAL_PROVIDER_TOKEN}' 2>/dev/null || true)"
if [[ -z "$NIST" ]]; then
  warn "INTERNAL_SERVICE_TOKEN not in notification-service-secrets — cannot derive WHATSAPP_RENEWAL_PROVIDER_TOKEN"
elif [[ "$NIST" == "$NCUR" ]]; then
  ok "already matches the shared internal token"
else
  kubectl -n "$NS" patch secret notification-service-secrets --type=merge \
    -p "{\"data\":{\"WHATSAPP_RENEWAL_PROVIDER_TOKEN\":\"$NIST\"}}" >/dev/null
  ok "notification-service may now call operations' subscription-renewal Flow endpoint"
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

# ── 6c ────────────────────────────────────────────────────────────────────────────────────────
# THE SAME GAP, ONE MORE TIME — assistant-kb-shop is a ConfigMap deploy/kb/sync-shop-kb.sh builds
# from deploy/kb/shop/*.json, and assistant-service's own values file mounts it via extraVolumes.
# Not a deploy/k3s/*.yaml file (step 2b above never touched it), so it had its own silent gap:
# found live on THIS install, assistant-service's pod stuck forever on
# `MountVolume.SetUp failed ... configmap "assistant-kb-shop" not found` — the exact same "a human
# has to remember to run one more script after every reinstall" shape, just in a different
# directory. Before "services" (next step), because that step is what actually creates the pod
# that mounts it.
step "assistant-service knowledge base"
bash "$ROOT/deploy/kb/sync-shop-kb.sh" || warn "KB sync failed — assistant-service will stay stuck on a missing ConfigMap until this is re-run"

# ── 7 ─────────────────────────────────────────────────────────────────────────────────────────
# Upstream's, health-gated, ONE SERVICE AT A TIME. Not a loop of our own: a hand-written parallel
# restart is what exhausted the connection pool and deadlocked this cluster once already. The
# sequential gate is the feature, not the slow part.
step "services"
PRODUCT_NAME=raje3 CHART="$ROOT/platform/deploy/chart" VALUES_DIR="$ROOT/deploy/services" \
  bash "$ROOT/platform/deploy/server/update.sh"

# THE PUBLIC KEY, DISTRIBUTED A SECOND TIME, NOW THAT THE SECRETS IT TARGETS ACTUALLY EXIST.
#
# THE BUG THIS CLOSES, FOUND BY HAND ON A FROM-NOTHING INSTALL. Step 4's own distribution loop
# (`kubectl -n "$NS" get secret "${svc}-secrets" >/dev/null 2>&1 || continue`) runs BEFORE this
# step — before `update.sh` has created a single service's secret, on a cluster with none of them
# yet. Every verifier's secret lookup silently `continue`s, the loop reports "public key
# distributed to 0 verifying service(s)" — read as a fact, not a warning — and every service that
# needs TOKEN_VERIFIER_DRIVER: "jwks" (authz-service first among them, since seed-roles.sh mints
# its own self-signed token against it) comes up with no public key to verify against. The
# symptom was a real, reproducible 401 on the very first seed step of every from-nothing install,
# with three retries and a "seed attempt N failed" burned on each one before the whole seed phase
# gave up — nothing about the message named a missing key.
#
# $PUB_B64 IS STILL THE SAME VALUE — same variable, same scope, this is one script top to bottom —
# so this is not a re-derivation, only a second application now that the targets exist. An
# already-correct secret gets the identical bytes patched onto it again: idempotent, and cheaper
# than working out which services are new since the first pass.
verifiers=0
for f in "$HERE"/services/*.values.yaml; do
  grep -q 'TOKEN_VERIFIER_DRIVER: *"jwks"' "$f" || continue
  svc="$(basename "$f" .values.yaml)"
  [[ "$svc" == "identity-service" ]] && continue
  kubectl -n "$NS" get secret "${svc}-secrets" >/dev/null 2>&1 || continue
  kubectl -n "$NS" patch secret "${svc}-secrets" --type=merge \
    -p "{\"data\":{\"TOKEN_PUBLIC_KEY\":\"$PUB_B64\"}}" >/dev/null
  # A PATCHED SECRET DOES NOT REACH AN ALREADY-RUNNING POD — env vars are set once, at container
  # start, from whatever the secret held THEN; a Kubernetes Secret update never re-injects into a
  # live process. Every one of these pods just started this same step (the rollout right above),
  # holding whatever TOKEN_PUBLIC_KEY existed (usually none, on a from-nothing install) — so
  # without this restart the patch above is correct and inert, verifying nothing until whatever
  # NEXT restarts the pod for an unrelated reason.
  kubectl -n "$NS" rollout restart "deployment/$svc" >/dev/null 2>&1 || true
  kubectl -n "$NS" rollout status "deployment/$svc" --timeout=90s >/dev/null 2>&1 || true
  verifiers=$((verifiers + 1))
done
ok "public key re-distributed to $verifiers verifying service(s), now that their secrets exist"

# ── 7b ────────────────────────────────────────────────────────────────────────────────────────
# THE WEAKER DATABASE ROLES FOR THE TWO HUMAN-SEARCHABLE-BY-PHONE ROUTES (operations' `GET
# /customers/by-phone`, affiliate-service's `POST /apply`) — see each hook's own header for the
# full reasoning. NOT REQUIRED FOR THE PRODUCT TO WORK: both routes fall back to their normal,
# single-role lookup when DATASTORE_DSN_PHONE_SEARCH is unset, so a from-scratch install that
# somehow skipped this step would still boot and serve correctly — just without the extra
# isolation. Run here, not earlier: needs operations' and affiliate-service's own databases (step
# 5&6), their own secrets holding a real DATASTORE_DSN (step 6b / gen-secrets.py), AND their
# Deployments to already exist (this step, just above) so the restart at the end of each hook has
# something real to restart.
step "database read-only roles"
soft "operations' phone-search role" bash "$HERE/hooks/provision-phone-search-role.sh"
soft "affiliate-service's phone-search role" bash "$HERE/hooks/provision-affiliate-phone-search-role.sh"

# ── 8 ─────────────────────────────────────────────────────────────────────────────────────────
# THE INSTALL ENDED HERE, AND THE CLUSTER WAS EMPTY. Every service ran, every probe was green, and
# the product had no roles, no price list and no legal library — because
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
# account. `library.register` (services/operations) does that registration automatically per
# tenant the moment the account connects; there is no platform-wide seeder to run here.
step "seed"
soft "roles" bash "$HERE/seed/seed-roles.sh"
# EVERY EXISTING TENANT'S ROLES, BROUGHT UP TO THE CURRENT DEFINITIONS — never wired into any
# deploy path until now (found live, 2026-10-06: `operations.freelancer_manage` sat correctly in
# roles.json and the owner-holds-it CI gate passed clean, because that gate only reads THIS repo's
# files — the capability simply never reached any establishment that signed up before the day it
# was added, and nothing here or in ship.sh ever ran `repair-roles.sh` to close that gap). Additive
# only (see that script's own header) — safe on every ordinary deploy and every WIPE=1 reinstall
# alike, never undoes a role an owner customised by hand.
soft "repair existing roles" bash "$HERE/seed/repair-roles.sh"
# assistant-service's OWN HAND-AUTHORED KB (Phase 4) — a ConfigMap this repo's own
# deploy/kb/sync-shop-kb.sh builds from deploy/kb/shop/*.json, mounted via the chart's
# extraVolumes hook. NEVER PART OF A FRESH-CLUSTER CHAIN UNTIL TODAY — a WIPE=1 install deletes
# this ConfigMap along with everything else in the namespace, and nothing here ever recreated
# it, so assistant-service sat in ContainerCreating forever (FailedMount: configmap
# "assistant-kb-shop" not found) on the FIRST from-scratch install this KB feature ever saw.
# Every ordinary (non-wipe) deploy never noticed, because the ConfigMap from whenever it was
# last synced by hand was still sitting there. `soft`, matching every other seeder here — a
# missing/invalid KB file must not fail the whole install; ci/check_shop_kb_is_valid.py is the
# gate that actually enforces the content is correct, on every commit.
soft "assistant KB" bash "$HERE/kb/sync-shop-kb.sh"
# THE ADMINISTRATION ACCOUNT THE INSTALLER ASKED FOR (ل-2). install.sh collects an email and a
# password, enforces a floor on the password, generates one when it is left blank, and prints it
# under «تُعرض مرة واحدة فقط» — and nothing here read either value, so no account was ever created.
# The operator saved a credential for somebody who did not exist and discovered it at the sign-in
# screen, after the terminal that showed it once had been closed.
#
# AFTER THE ROLES, and the order is the requirement: the account is granted `platform-owner`, and a
# role granted before it is defined is a membership pointing at nothing.
soft "admin account" bash "$HERE/seed/seed-admin.sh"
# THE CROSS-TENANT CREDENTIAL operations-service NEEDS FROM billing-service (settlements' partner
# statement + the wallet top-up reconcile poller) — minted here because this is the first point in
# the install where a platform-owner account (holding platform.billing + service_accounts:write)
# actually exists to log in as. See the script's own header for why this could not run any earlier
# and why it is safe to re-run.
soft "billing service-account for operations" bash "$HERE/hooks/provision-billing-service-account.sh"
# THE DEDICATED, PERSISTENT ACCOUNT job-service SCHEDULE/DISPATCH ADMIN ACTIONS RUN AS — never the
# platform owner's own login (2026-09-16 decision, once our own services' CronJobs start migrating
# to job-service push-dispatch). Scoped to EXACTLY `platform.jobs`, same "mint here because this is
# the first point a platform-owner account exists" reasoning as the billing service-account above.
soft "job-service automation account" bash "$HERE/hooks/provision-job-service-automation.sh"
# EVERY MIGRATED SERVICE'S HEARTBEAT (2026-09-16) — without this, a fresh install ships with all
# seven services' own cron entries removed and nothing having replaced them: every probe green,
# nothing ever fires (playbook trap §4.1). Idempotent (see the script's own header) — safe on every
# re-run, including a WIPE=1 reinstall that starts job-service's own schedule store empty again.
soft "cron -> job-service migrations" bash "$HERE/hooks/provision-cron-migrations.sh"
soft "plans" bash "$HERE/seed/seed-plans.sh"
soft "legal" bash "$HERE/seed/seed-legal.sh"
# OUR OWN PLATFORM-WIDE in-app/email/sms TEMPLATES (rating-app-feature.md phase 8) — without this,
# a fresh install's `InAppNotifier.send(template_key=...)` calls (the staff-rating alert first,
# any future in-app alert after it) fail silently forever, same as any other unconfigured peer.
# Mints its own token directly (like seed-plans.sh above), so it needs no account seeded first.
soft "notification templates" bash "$HERE/seed/seed-notification-templates.sh"
# THE BACKUP TARGETS — runtime data, and nothing was creating it.
#
# The fleet came up green with backup-service deployed, a bucket, and BACKUP_KEK shared everywhere,
# and NOTHING was backed up: targets are rows, no script wrote any, and the scheduler reported
# success against an empty list. The day postgres is lost, operations — the only holder of
# customers' phone numbers in the clear — has no archive, and the first sign of it is the restore.
soft "backup targets" bash "$HERE/seed/seed-backup-targets.sh"
# RATING AND REPORT FLOWS BOTH REMOVED (2026-09-16) — the rating screen moved off native
# WhatsApp Flow entirely to a hosted web page ([[task-service-procedure-checklists]] phase 2);
# the report Flow's template was already deleted 2026-09-13 but this install-chain step (and its
# script/JSON) were accidentally left behind — found and removed alongside the rating cleanup
# rather than repeating that same incomplete-deletion mistake a second time.
# THE SAME CLONE-PER-SHOP PATTERN, THE REMAINING FLOWS — WhatsApp booking (assignment-mode
# redesign, Phase 5). Content is GENERATED (notification-service's own JSON generator, not a
# hand-authored file — see the script's own header), so this must run AFTER notification-service
# is up with a real WHATSAPP_BOOKING_DEFINITION configured. Missing from this install chain until
# 2026-09-08 — found the same day the display-row gap (ci/check_listed_apps_are_wired.py) was
# found, same root cause: a feature finished in code with no install-chain step to make it real
# on a fresh cluster.
soft "booking flow" bash "$HERE/seed/bootstrap-booking-flow.sh"
# THE SUBSCRIPTION-RENEWAL FLOW IS DELIBERATELY NOT HERE (owner's decision, 2026-09-10) — unlike
# rating/report/booking above, minting its master is a MANUAL admin action
# (POST /api/v1/platform/flows/subscription-renewal/seed, platform.operations capability, console-
# reachable), the same "nothing reaches Meta until a person presses the button" posture the
# template registry already holds. No install-chain step is missing here; see
# services/operations/app/api/v1/platform.py's own route docstring.

# AND THE SEED THAT LIVES INSIDE THE SERVICE, WHICH DEPENDS ON AN ORDER NOTHING GUARANTEES.
# operations seeds its 78 templates on the first boot that finds an empty table. On this install it
# booted before its database existed — the databases were being created in another step — so it
# found nothing to seed and never looked again, and everything reported success.
#
# The trade a shop was in used to be seeded the same way and checked here; it is gone. A shop now
# starts with an empty catalogue it writes itself, so «empty» is no longer evidence of anything.

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
  # AFFILIATES.<DOMAIN> AND ADMIN.<DOMAIN> RIDE THE SAME CERTIFICATE, THE SAME SITE BLOCK, THE
  # SAME UPSTREAM. Neither is a second edge target — the console image still answers for both;
  # the console's own router reads the hostname at boot and mounts the affiliate/admin tree at
  # '/' instead of the shop app at '/app' (main.tsx).
  python3 - "$EDGE_SRC" "$EDGE_TMP/edge.json" "${DOMAIN:-}" "${ACME_EMAIL:-}" <<'PYEOF'
import json, sys
src, dst, domain, email = sys.argv[1:5]
cfg = json.load(open(src, encoding='utf-8'))
if domain:
    cfg['domain'] = domain
    cfg['tls'] = True
    cfg['aliases'] = [f"affiliates.{domain}", f"admin.{domain}"]
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

# ── AND THE HONEST ENDING ─────────────────────────────────────────────────────────────────────
# A non-zero exit, because an installer that finishes 0 having skipped the plans is a machine
# telling its operator the shop can sell.
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo -e "
${C_Y}  ! the install did NOT complete: ${FAILED[*]} — the cluster is up and these "          "steps did not run. Fix the cause above and re-run this script; it is safe to repeat."${C_N}
  exit 1
fi
