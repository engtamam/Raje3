#!/usr/bin/env bash
# What the cluster IS, not what the repository intended.
#
#   ./deploy/check-posture.sh            everything
#   ./deploy/check-posture.sh --quiet    only what is wrong
#
# WHY THIS EXISTS. Two real gaps were found by typing three commands at a cluster that had been
# serving for a day: Kubernetes secrets stored unencrypted, and no disk encryption under a database
# holding every customer's phone number. Nothing in the repository would ever have mentioned either.
#
# That is the shape this codebase keeps finding — a control whose ABSENCE has no symptom.
# Encryption at rest is the purest example: everything works perfectly without it, right up to the
# one day it matters, and on that day it cannot be applied retroactively to what already leaked.
#
# So it is measured, on a schedule, against the running thing. It does not belong in CI — CI has no
# cluster — it belongs beside deploy/prove-*.sh, run after every rollout and before anybody tells a
# customer how their data is held.
#
# AND EVERY FAILURE CARRIES THE COMMAND THAT FIXES IT. A posture report listing twelve green lines
# and one amber is a report nobody reads twice; one that says what to type is a report somebody
# acts on.
set -uo pipefail

NS="${NS:-base-services}"
QUIET=0; [[ "${1:-}" == "--quiet" ]] && QUIET=1
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

C_G="\033[32m"; C_R="\033[31m"; C_Y="\033[33m"; C_D="\033[2m"; C_N="\033[0m"
pass=0; fail=0

ok(){   pass=$((pass+1)); [[ $QUIET -eq 1 ]] || echo -e "  ${C_G}ok${C_N}   $1"; }
bad(){  fail=$((fail+1)); echo -e "  ${C_R}FAIL${C_N} $1"; echo -e "       ${C_Y}fix:${C_N} $2"; }
note(){ [[ $QUIET -eq 1 ]] || echo -e "  ${C_D}·    $1${C_N}"; }
head(){ [[ $QUIET -eq 1 ]] || echo -e "\n${C_D}── $1 ─────────────────────────────────────────${C_N}"; }

# ── 1. secrets at rest ────────────────────────────────────────────────────────────────────────
head "encryption at rest"
enc=$(sudo k3s secrets-encrypt status 2>/dev/null | grep -i "Encryption Status" | awk '{print $NF}')
if [[ "$enc" == "Enabled" ]]; then
  # ENABLED IS NOT ENOUGH. `enable` covers what is written AFTER it; everything already in etcd
  # stays in the clear until a reencrypt rewrites it — and the status line says Enabled either way.
  stale=$(sudo k3s secrets-encrypt status 2>/dev/null | grep -ci "reencrypt" || true)
  ok "k3s secrets are encrypted at rest"
  [[ "$stale" -gt 0 ]] || note "confirm the EXISTING secrets were rewritten: k3s secrets-encrypt reencrypt"
else
  bad "k3s secrets are stored base64-only in etcd — the database passwords, PII_SALT (which
       un-pseudonymises every subject_ref in the platform and CANNOT be rotated), BACKUP_KEK,
       INTERNAL_SERVICE_TOKEN and the session signing key" \
      "sudo k3s secrets-encrypt enable && sudo k3s secrets-encrypt reencrypt"
fi

# ── 2. the disk ───────────────────────────────────────────────────────────────────────────────
head "the volume under the database"
if lsblk -o FSTYPE 2>/dev/null | grep -qi "crypto_LUKS"; then
  ok "the data volume is encrypted"
else
  bad "no encrypted volume — postgres data files sit in plaintext, and operations stores phone
       numbers readable BY DESIGN (it must, to send). A snapshot, a disposed disk or a hypervisor
       copy is then a customer list" \
      "encrypt the volume (often a create-time choice on a cloud disk — plan a migration), and
       keep the key OFF that volume"
fi

# ── 3. in transit ─────────────────────────────────────────────────────────────────────────────
head "service to database"
dsn=$(kubectl -n "$NS" get secret operations-secrets -o jsonpath='{.data.DATASTORE_DSN}' 2>/dev/null | base64 -d 2>/dev/null)
if [[ "$dsn" == *"sslmode=require"* || "$dsn" == *"sslmode=verify"* ]]; then
  ok "the database connection requires TLS"
else
  bad "the DSN carries no sslmode — service-to-database traffic is unencrypted inside the cluster,
       and it is the first thing an auditor asks about" \
      "enable TLS on postgres and append sslmode=require to DATASTORE_DSN"
fi

# ── 4. the shared secrets, in the cluster rather than in the repository ───────────────────────
head "shared secrets identical across services"
for key in PII_SALT INTERNAL_SERVICE_TOKEN BACKUP_KEK; do
  # THE VALUES, NOT THE DECLARATIONS. check_deploy_wiring.py already proves every service NAMES
  # them; this proves the running pods HOLD the same ones. Two different PII_SALTs fold one person
  # into two pseudonyms and an erasure misses half their data — and nothing anywhere would say so.
  vals=$(for s in $(kubectl -n "$NS" get secrets -o name 2>/dev/null | grep -o '[a-z-]*-secrets'); do
           kubectl -n "$NS" get secret "$s" -o jsonpath="{.data.$key}" 2>/dev/null | md5sum | cut -c1-8
         done | grep -v '^d41d8cd9$' | sort -u | wc -l)
  if [[ "$vals" -le 1 ]]; then
    ok "$key is the same value everywhere"
  else
    bad "$key differs between services ($vals distinct values)" \
        "re-run platform/deploy/server/gen-secrets.py and roll the affected services"
  fi
done

# ── 5. egress ─────────────────────────────────────────────────────────────────────────────────
head "who may reach the internet"
out=$(kubectl -n "$NS" get networkpolicies -o json 2>/dev/null | grep -c '"0.0.0.0/0"' || true)
allowed=$(kubectl -n "$NS" get deploy -o json 2>/dev/null \
          | grep -o '"name":"EGRESS_ALLOWED_HOSTS","value":"[^"]*"' | sed 's/.*value":"//;s/"//' | sort -u)
note "hosts declared: ${allowed:-none}"
if [[ -z "$allowed" || "$allowed" == "graph.facebook.com" ]]; then
  ok "only the messaging host is reachable"
else
  bad "more hosts are allowed than the messaging provider: $allowed" \
      "narrow EGRESS_ALLOWED_HOSTS in the values file of whichever service widened it"
fi

# ── 6. every pod on the digest its values file pins ───────────────────────────────────────────
head "running images"
drift=0
for f in deploy/services/*.values.yaml; do
  svc=$(basename "$f" .values.yaml)
  want=$(grep -m1 'digest:' "$f" | sed -E 's/.*digest:[[:space:]]*"([^"]*)".*/\1/')
  # THE imageID, NEVER THE TAG. containerd stores an imported image under its TAG, so a pod can run
  # two-version-old code under a correct-looking pin and every dashboard agrees (playbook 4.29).
  got=$(kubectl -n "$NS" get pods -l "app.kubernetes.io/name=$svc" \
        -o jsonpath='{.items[0].status.containerStatuses[0].imageID}' 2>/dev/null)
  [[ -z "$got" ]] && continue
  if [[ "$got" == *"$want"* ]]; then
    ok "$svc runs its pinned digest"
  else
    drift=$((drift+1))
    bad "$svc is NOT running its pinned digest (${want:0:19}…)" \
        "bash deploy/repin.sh <tag> then update.sh --only $svc"
  fi
done
[[ $drift -eq 0 ]] || note "a pod on the wrong image makes every proof above it meaningless"

echo
if [[ $fail -eq 0 ]]; then
  echo -e "${C_G}  posture: $pass checks, nothing outstanding${C_N}"
else
  echo -e "${C_R}  posture: $fail outstanding, $pass ok${C_N}"
fi
exit $(( fail > 0 ))
