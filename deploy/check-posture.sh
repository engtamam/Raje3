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
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"

NS="${NS:-base-services}"
QUIET=0; [[ "${1:-}" == "--quiet" ]] && QUIET=1

C_G="\033[32m"; C_R="\033[31m"; C_Y="\033[33m"; C_D="\033[2m"; C_N="\033[0m"
pass=0; fail=0

# ── 0. CAN WE READ THE CLUSTER AT ALL? ─────────────────────────────────────────────────────────
# THIS SCRIPT ONCE PRINTED A CLEAN SECURITY POSTURE FROM A LAPTOP THAT COULD NOT REACH THE CLUSTER.
# Every kubectl below swallows its own errors with `2>/dev/null`, so an unreachable API server does
# not look like an error — it looks like an empty answer, and three checks read "empty" as "fine":
# the shared-secret comparison counted 0 distinct values and said "the same value everywhere", the
# egress check saw no declared hosts and said "only the messaging host is reachable", and the image
# loop `continue`d over all 24 services in silence. The footer then said "4 ok".
#
# An unreadable cluster is not a posture. It is the absence of one, and it must stop the run.
if ! kubectl -n "$NS" get ns "$NS" >/dev/null 2>&1; then
  echo -e "  ${C_R}✗ cannot read the cluster${C_N} (namespace $NS, KUBECONFIG=$KUBECONFIG)" >&2
  echo -e "       ${C_Y}fix:${C_N} run this ON the node — it reads the live cluster, not the repo:" >&2
  echo -e "            ssh <node> 'sudo bash /root/raje3/deploy/check-posture.sh'" >&2
  exit 2
fi

ok(){   pass=$((pass+1)); [[ $QUIET -eq 1 ]] || echo -e "  ${C_G}ok${C_N}   $1"; }
bad(){  fail=$((fail+1)); echo -e "  ${C_R}FAIL${C_N} $1"; echo -e "       ${C_Y}fix:${C_N} $2"; }
note(){ [[ $QUIET -eq 1 ]] || echo -e "  ${C_D}·    $1${C_N}"; }
# NAMED `head` UNTIL 2026-08-17, WHICH BLINDED EVERY PIPELINE IN THIS FILE. A shell function beats
# the binary of the same name, so `... | head -1` stopped filtering and started calling THIS —
# which ignores its stdin entirely and prints a section rule. Two reads died of it: the etcd probe
# that CONFIRMS secrets are really encrypted at rest, and the postgres pod lookup that all three
# database claims depend on. Neither then said «I could not read»; each produced a verdict.
section(){ [[ $QUIET -eq 1 ]] || echo -e "\n${C_D}── $1 ─────────────────────────────────────────${C_N}"; }

# ── 1. secrets at rest ────────────────────────────────────────────────────────────────────────
section "encryption at rest"
enc=$(sudo k3s secrets-encrypt status 2>/dev/null | grep -i "Encryption Status" | awk '{print $NF}')
if [[ "$enc" == "Enabled" ]]; then
  # ENABLED IS NOT ENOUGH, AND THE STATUS LINE CANNOT TELL YOU. `enable` covers what is written
  # AFTER it; everything already in etcd stays in the clear until a reencrypt rewrites it — and
  # the status says Enabled either way. So the VALUE is read, the way an attacker with the disk
  # would read it: a secret that comes back as plaintext is a secret that is plaintext, whatever
  # any status claims.
  probe=$(sudo k3s kubectl get secret -n "$NS" -o name 2>/dev/null | head -1)
  raw=""
  if [[ -n "$probe" ]]; then
    name="${probe#secret/}"
    raw=$(sudo /var/lib/rancher/k3s/data/current/bin/etcdctl           get "/registry/secrets/$NS/$name" --prefix 2>/dev/null | head -c 400)
  fi
  if [[ -z "$raw" ]]; then
    ok "k3s secrets encryption is enabled"
    note "could not read etcd directly to CONFIRM the stored bytes — if this host has been serving,
       run: sudo k3s secrets-encrypt reencrypt"
  elif [[ "$raw" == *"k8s:enc:"* ]]; then
    ok "k3s secrets are encrypted at rest — confirmed by reading the stored bytes"
  else
    bad "encryption is ENABLED but the stored secret is still plaintext — enable covers only what
       is written after it, and this cluster was serving before that"         "sudo k3s secrets-encrypt reencrypt"
  fi
else
  bad "k3s secrets are stored base64-only in etcd — the database passwords, PII_SALT (which
       un-pseudonymises every subject_ref in the platform and CANNOT be rotated), BACKUP_KEK,
       INTERNAL_SERVICE_TOKEN and the session signing key" \
      "sudo k3s secrets-encrypt enable && sudo k3s secrets-encrypt reencrypt"
fi

# ── 2. the disk ───────────────────────────────────────────────────────────────────────────────
section "the volume under the database"
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
section "service to database"

# THREE MEASUREMENTS, NOT ONE, because the DSN alone answers the wrong question.
#
# This used to check only whether DATASTORE_DSN carried sslmode=require, and report a flat failure
# otherwise. That reads as "the traffic is in the clear", and for months it was — but it stopped
# being true the moment postgres began serving TLS, because libpq NEGOTIATES TLS whenever the
# server offers it. Without sslmode the encryption is OPPORTUNISTIC: real, and not enforced.
#
# The distinction matters in exactly one direction. Opportunistic TLS protects against a passive
# listener on the pod network, which is the realistic threat inside a cluster. It does NOT protect
# against an active attacker who can strip the offer — for that the client has to refuse a plaintext
# connection, which is what sslmode=require means. Reporting the two as the same thing would either
# panic about a solved problem or declare a half-solved one finished.
#
# So: does the server offer it, how many live sessions actually use it, and does the client demand
# it. The middle one is the only measurement of reality; the other two are of intent.

# AND THE POD IS CONFIRMED, NOT ASSUMED. The label lookup returned nothing here while returning
# `pod/postgres-0` from an interactive shell one second earlier, so the fallback ran, `${pg#pod/}`
# was still empty, and every read below became `pods ""` — «Error from server (NotFound)». Which
# name it lands on matters less than this: a script about to make three security claims must know
# it is talking to something. `kubectl get` is the cheapest possible way to be sure.
pg=$(kubectl -n "$NS" get pod -l app=postgres -o name 2>/dev/null | head -1 | tr -d '\r')
pg="${pg#pod/}"
[[ -n "$pg" ]] || pg="postgres-0"
if ! kubectl -n "$NS" get pod "$pg" >/dev/null 2>&1; then
  bad "no postgres pod named '$pg' in namespace '$NS' — the three database claims below cannot be
       made at all" \
      "check the namespace, or name the pod: PGPOD=… bash deploy/check-posture.sh"
  pg=""
fi
# THE ROLE IS READ, NEVER SPELLED. This said `-U platform`, postgres has no such role, and so both
# reads below returned nothing from the day they were written — which is not «no TLS», it is «I
# could not ask». So this check has reported a TLS failure on every run since, including on
# clusters that serve TLS perfectly; and a permanent red alarm is a thing people learn to scroll
# past, which costs more than the check was ever worth. `pg_role` lives in cluster.sh for the same
# reason the cluster's address does: one answer, in one file, for every script here.
PGU=$(pg_role) || exit 1
serving=$(kubectl -n "$NS" exec "$pg" -- psql -U "$PGU" -d operations -tAc "SHOW ssl" 2>&1 | tr -d '[:space:]')
# THREE ANSWERS, NOT TWO. `on` and `off` are what postgres says; anything else is what the plumbing
# says, and folding it into «does not serve TLS» is how this check spent its whole life accusing a
# cluster that answers `on` when asked directly. An operator who is told the wrong thing about
# encryption either panics or stops reading — and it has been the second one.
if [[ "$serving" == "on" ]]; then
  ok "postgres serves TLS"
elif [[ "$serving" == "off" ]]; then
  bad "postgres does not serve TLS — no client can encrypt to it however its DSN is written" \
      "mint the postgres-tls Secret and apply platform/deploy/k3s/platform/datastores.yaml"
else
  bad "cannot ask postgres whether it serves TLS: ${serving:-<no answer>}" \
      "this is not a verdict about encryption — fix the read, then run this again"
fi

# THE ONE THAT CANNOT BE ARGUED WITH. Configuration says what should happen; pg_stat_ssl says what
# is happening on every connection open right now.
enc=$(kubectl -n "$NS" exec "$pg" -- psql -U "$PGU" -d operations -tAc \
      "SELECT count(*) FILTER (WHERE ssl) || '/' || count(*) FROM pg_stat_ssl" 2>&1 | tr -d '[:space:]')
# `-n` IS NOT A MEASUREMENT, AND BELIEVING IT PRINTED A GREEN VERDICT OUT OF AN ERROR MESSAGE.
# When the read failed, `2>&1` put `Error from server (NotFound): pods...` into this variable.
# `-n` was true, `${enc#*/}` and `${enc%/*}` both returned the whole unsplit string, the two were
# therefore equal, and the check announced «every live database session is encrypted» — quoting
# the error as its evidence. Silence read as failure was the old defect; noise read as success is
# the worse one, because it is the answer nobody goes back to check.
#
# So the shape is verified before the value is believed: `N/M` and nothing else.
if [[ "$enc" =~ ^[0-9]+/[0-9]+$ ]]; then
  plain=${enc#*/}; cipher=${enc%/*}
  if [[ "$cipher" == "$plain" ]]; then
    ok "every live database session is encrypted ($enc)"
  elif [[ "$cipher" -gt 0 ]]; then
    # postgres opens a few unencrypted local connections to itself; those are not on the network.
    ok "$enc live database sessions are encrypted (the remainder are postgres's own local connections)"
  else
    bad "NO live database session is encrypted ($enc) — every phone number crossing the pod
       network is in the clear" \
        "check that the services reconnected after postgres began serving TLS"
  fi
else
  # AND NO `else` AT ALL WAS THE ORIGINAL SHAPE: an unreadable answer printed nothing, so the
  # measurement this section calls «the one that cannot be argued with» simply vanished from the
  # report — and a report with a line missing reads as a report with nothing wrong.
  bad "cannot measure live session encryption: ${enc:-<no answer>}" \
      "this is not a verdict about encryption — fix the read, then run this again"
fi

dsn=$(kubectl -n "$NS" get secret operations-secrets -o jsonpath='{.data.DATASTORE_DSN}' 2>/dev/null | base64 -d 2>/dev/null)
if [[ "$dsn" == *"sslmode=require"* || "$dsn" == *"sslmode=verify"* ]]; then
  ok "and the client REQUIRES it — a stripped offer is refused rather than downgraded"
else
  note "the DSN carries no sslmode, so encryption is opportunistic: negotiated because the server
       offers it, not demanded. That stops a passive listener and not an active one. The upstream
       gate holds this deliberately until the client half lands (ALLOW_DSN_SSLMODE), because a DSN
       that demands TLS from a server not yet serving it fails every service at boot."
fi

# ── 4. the shared secrets, in the cluster rather than in the repository ───────────────────────
section "shared secrets identical across services"
for key in PII_SALT INTERNAL_SERVICE_TOKEN BACKUP_KEK; do
  # THE VALUES, NOT THE DECLARATIONS. check_deploy_wiring.py already proves every service NAMES
  # them; this proves the running pods HOLD the same ones. Two different PII_SALTs fold one person
  # into two pseudonyms and an erasure misses half their data — and nothing anywhere would say so.
  vals=$(for s in $(kubectl -n "$NS" get secrets -o name 2>/dev/null | grep -o '[a-z-]*-secrets'); do
           kubectl -n "$NS" get secret "$s" -o jsonpath="{.data.$key}" 2>/dev/null | md5sum | cut -c1-8
         done | grep -v '^d41d8cd9$' | sort -u | wc -l)
  # 0 IS NOT 1. No secret carried this key — either none is set, or the read failed. Saying "the
  # same value everywhere" about a key that was read nowhere is the same sentence as agreement.
  if [[ "$vals" -eq 0 ]]; then
    bad "$key was not readable in any service secret — this check proved nothing" \
        "confirm the secrets exist: kubectl -n $NS get secrets | grep -- -secrets"
  elif [[ "$vals" -eq 1 ]]; then
    ok "$key is the same value everywhere"
  else
    bad "$key differs between services ($vals distinct values)" \
        "re-run platform/deploy/server/gen-secrets.py and roll the affected services"
  fi
done

# ── 5. egress ─────────────────────────────────────────────────────────────────────────────────
section "who may reach the internet"
out=$(kubectl -n "$NS" get networkpolicies -o json 2>/dev/null | grep -c '"0.0.0.0/0"' || true)
allowed=$(kubectl -n "$NS" get deploy -o json 2>/dev/null \
          | grep -o '"name":"EGRESS_ALLOWED_HOSTS","value":"[^"]*"' | sed 's/.*value":"//;s/"//' | sort -u)
note "hosts declared: ${allowed:-none}"
# NO DECLARATION IS NOT A NARROW DECLARATION. An empty EGRESS_ALLOWED_HOSTS everywhere means either
# nothing restricts egress, or the deployments were not readable. Neither is "only the messaging
# host is reachable" — that sentence claims a restriction that was never observed.
if [[ -z "$allowed" ]]; then
  bad "no service declares EGRESS_ALLOWED_HOSTS — egress is unrestricted or unreadable" \
      "set EGRESS_ALLOWED_HOSTS on the sending services, or confirm the NetworkPolicies"
elif [[ "$allowed" == "graph.facebook.com" ]]; then
  ok "only the messaging host is reachable"
else
  bad "more hosts are allowed than the messaging provider: $allowed" \
      "narrow EGRESS_ALLOWED_HOSTS in the values file of whichever service widened it"
fi

# ── 6. every pod on the digest its values file pins ───────────────────────────────────────────
# WHICH PINS? THE ONES BESIDE THIS SCRIPT — AND ON THE NODE THOSE GO STALE. A ship syncs only the
# values file it shipped, so /opt/raje3/deploy/services drifts from the repo service by service.
# Measured once against a healthy cluster: all 24 pods were correct, and this section accused 8 of
# them because the node still held the previous release's digests. A mismatch here therefore means
# "the pod disagrees with THIS COPY of the pins", which is a question, not a verdict.
#
# deploy/verify-fleet.sh answers it: it runs from the repo — the only place that holds the whole
# fleet's intended pins — and reads the cluster over ssh.
section "running images"
note "compared against the values files beside this script; the repo's pins are authoritative — deploy/verify-fleet.sh"
drift=0
for f in deploy/services/*.values.yaml; do
  svc=$(basename "$f" .values.yaml)
  want=$(grep -m1 'digest:' "$f" | sed -E 's/.*digest:[[:space:]]*"([^"]*)".*/\1/')
  # THE imageID, NEVER THE TAG. containerd stores an imported image under its TAG, so a pod can run
  # two-version-old code under a correct-looking pin and every dashboard agrees (playbook 4.29).
  got=$(kubectl -n "$NS" get pods -l "app.kubernetes.io/name=$svc" \
        -o jsonpath='{.items[0].status.containerStatuses[0].imageID}' 2>/dev/null)
  # A SERVICE WITH NO READABLE POD IS A FINDING, NOT A SKIP. `continue` here once swallowed all 24
  # services and printed an empty section under a green footer.
  if [[ -z "$got" ]]; then
    drift=$((drift+1))
    bad "$svc has no readable running pod — its image could not be checked" \
        "kubectl -n $NS get pods -l app.kubernetes.io/name=$svc"
    continue
  fi
  if [[ "$got" == *"$want"* ]]; then
    ok "$svc runs its pinned digest"
  else
    drift=$((drift+1))
    bad "$svc does not match the pin in THIS copy of its values file (${want:0:19}…)" \
        "confirm against the repo first: bash deploy/verify-fleet.sh — if it agrees, ship $svc"
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
