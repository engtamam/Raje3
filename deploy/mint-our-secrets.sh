#!/usr/bin/env bash
# ==================================================================================================
#  mint-our-secrets.sh — the seven secrets gen-secrets.py cannot know about.
# --------------------------------------------------------------------------------------------------
#  Upstream mints one secret per service from a schema built by reading each service's config.py —
#  under THEIR services/ directory. Ours live in this repository, so their generator has never heard
#  of campaigns, insights, loyalty, operations, portal or reminders, and a fresh cluster gives every
#  one of them `CreateContainerConfigError: secret "operations-secrets" not found`. On the old box
#  these six existed because somebody once created them by hand, and they survived every reinstall
#  by being invisible.
#
#  THE SHARED VALUES ARE COPIED, NEVER GENERATED, and this is the whole design:
#
#    PII_SALT turns a pseudonym back into a phone number. Every service but operations stores people
#    as pseudonyms, and a service holding a DIFFERENT salt folds one person into two — while
#    everything boots, every screen renders, and nothing looks wrong for months.
#
#    INTERNAL_SERVICE_TOKEN is what makes an internal call an internal call. Two values means half
#    the fleet 401s the other half.
#
#    BACKUP_KEK opens the archives; a second one produces backups nobody can restore.
#
#  A `openssl rand` here would be a second secret that must equal a first one — the exact shape of
#  the bug this file exists to prevent. So each value is read from a platform secret that already
#  has it, and this script generates exactly nothing.
#
#  WHAT IS OURS ALONE is the DSN: one database per service, because a migration in one service must
#  not lock a table in another. pre-deploy.sh creates them.
#
#  EXCEPT TWO, WHICH NEVER GET THAT TREATMENT. affiliate-service and portal are genuinely new
#  services (2026-08-20) that gen-secrets.py's own schema already covers end to end, database
#  included — both were deliberately put on the platform's shared `base_services` database rather
#  than a same-named one of their own, and gen-secrets.py's dsn_for() already sets that correctly
#  the first time either secret is minted. This script used to put them through the same
#  create-secret-then-patch loop as the seven that DO get their own database, and that `kubectl
#  create ... | kubectl apply` REPLACES the whole secret — silently overwriting the correct
#  base_services DSN gen-secrets.py had just set with a wrong same-named one
#  (`InvalidCatalogNameError: database "affiliate-service" does not exist`, reproduced on every
#  single fresh install because this script always runs after gen-secrets.py). They still need the
#  shared values below (PII_SALT etc.), so they get ONLY the patch — never the secret recreation
#  that would touch DATASTORE_DSN.
# ==================================================================================================
set -euo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
NS="${NS:-base-services}"
C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_N=$'\e[0m'
info(){ echo -e "${C_C}  ▸ $*${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ! $*${C_N}"; }

OURS="bookings campaigns insights loyalty operations reminders whatsapp-assistant"
SHARED_ONLY="affiliate-service portal"
SHARED="PII_SALT INTERNAL_SERVICE_TOKEN BACKUP_KEK SECRETS_KEK CACHE_URL EVENTBUS_URL QUEUE_URL RATELIMIT_URL TOKEN_PUBLIC_KEY"

# READ EACH SHARED VALUE FROM WHOEVER ALREADY HOLDS IT. They are byte-identical across the fleet by
# construction, so the first one found is the right one — and if none has it, that is a fact worth
# stopping for rather than papering over with a fresh random string.
declare -A VAL
for k in $SHARED; do
  for src in identity-service tenant-service audit-service; do
    v="$(kubectl -n "$NS" get secret "$src-secrets" -o jsonpath="{.data.$k}" 2>/dev/null || true)"
    [ -n "$v" ] && { VAL[$k]="$v"; break; }
  done
  [ -n "${VAL[$k]:-}" ] || warn "$k is in no platform secret — the services that need it will refuse to boot"
done

# The DSN is rewritten per service: same host, same credentials, its own database.
BASE_DSN="$(kubectl -n "$NS" get secret tenant-service-secrets -o jsonpath='{.data.DATASTORE_DSN}' 2>/dev/null | base64 -d || true)"
[ -n "$BASE_DSN" ] || { echo "  no DATASTORE_DSN to model ours on — run gen-secrets first" >&2; exit 1; }

# NOT MINTED: the object-store credential used to be read here and handed to all seven of these
# services identically — a shared key none of them ever read. OBJECTSTORE_DRIVER defaults to
# "local" and not one of $OURS' values.yaml files ever set it to "s3" (confirmed by grep across
# deploy/services/*.values.yaml — only backup-service does, and it is not in $OURS). A credential
# injected into seven pods and read by zero of them is not a convenience held in reserve; it is
# blast radius nobody is spending. The one service that genuinely needs object storage gets its
# own credential, scoped to its own bucket, when that need is real — not this shared one.
#
# If a future OURS service needs blobs: give it OBJECTSTORE_ACCESS_KEY/SECRET_KEY explicitly, in
# its own block below, the same way DATASTORE_DSN already is — never by re-adding this fleet-wide
# read.

info "minting ${OURS// /, }"
for svc in $OURS; do
  DSN="${BASE_DSN%/*}/$svc"
  args=(--from-literal="DATASTORE_DSN=$DSN")

  # Created empty-then-patched with the base64 we already hold: decoding a value only to re-encode
  # it would put every shared secret through this shell's argument list for no reason.
  kubectl -n "$NS" create secret generic "$svc-secrets" "${args[@]}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  patch='{"data":{'
  first=1
  for k in $SHARED; do
    [ -n "${VAL[$k]:-}" ] || continue
    [ $first -eq 1 ] || patch+=','
    patch+="\"$k\":\"${VAL[$k]}\""
    first=0
  done
  patch+='}}'
  [ $first -eq 0 ] && kubectl -n "$NS" patch secret "$svc-secrets" --type=merge -p "$patch" >/dev/null
done
ok "seven secrets present — shared values identical to the platform's"

# ── secrets-admin, WHICH GETS TWO VALUES AND NOT SEVEN ─────────────────────────────────────────
#
# IT IS MINTED SEPARATELY BECAUSE THE LOOP ABOVE WOULD LIE ABOUT IT. That loop hands every OURS
# service a DSN, PII_SALT, BACKUP_KEK and SECRETS_KEK — and this service has no database, no
# pseudonyms and nothing of its own to seal or restore. Its store is the k8s Secret objects it
# patches; see deploy/services/secrets-admin.values.yaml and deploy/k3s/secrets-admin-rbac.yaml.
#
# Handing it those anyway would cost nothing at boot and everything at review: the next person
# reading the Secret would conclude this service has a database, and the one after that would put
# something in it. A credential a workload does not need is a credential it should not hold —
# same rule this file just applied to the object-store key above, the other direction: there it
# was an unread credential removed; here it is a credential deliberately never granted.
info "minting secrets-admin (INTERNAL_SERVICE_TOKEN and TOKEN_PUBLIC_KEY only — it has no store)"
kubectl -n "$NS" create secret generic secrets-admin-secrets \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
patch='{"data":{'
first=1
for k in INTERNAL_SERVICE_TOKEN TOKEN_PUBLIC_KEY; do
  [ -n "${VAL[$k]:-}" ] || continue
  [ $first -eq 1 ] || patch+=','
  patch+="\"$k\":\"${VAL[$k]}\""
  first=0
done
patch+='}}'
[ $first -eq 0 ] && kubectl -n "$NS" patch secret secrets-admin-secrets --type=merge -p "$patch" >/dev/null
ok "secrets-admin minted (two values, no store)"

# affiliate-service and portal: PATCH ONLY, never recreate — see the header. gen-secrets.py must
# have already minted the secret (DSN included) for there to be anything to patch onto.
info "patching shared values onto ${SHARED_ONLY// /, } (DSN left untouched — gen-secrets.py owns it)"
for svc in $SHARED_ONLY; do
  if ! kubectl -n "$NS" get secret "$svc-secrets" >/dev/null 2>&1; then
    warn "$svc-secrets does not exist yet — run gen-secrets.py first, skipping"
    continue
  fi
  patch='{"data":{'
  first=1
  for k in $SHARED; do
    [ -n "${VAL[$k]:-}" ] || continue
    [ $first -eq 1 ] || patch+=','
    patch+="\"$k\":\"${VAL[$k]}\""
    first=0
  done
  patch+='}}'
  [ $first -eq 0 ] && kubectl -n "$NS" patch secret "$svc-secrets" --type=merge -p "$patch" >/dev/null
done
ok "shared values patched onto ${SHARED_ONLY// /, } — their own DSN was never touched"
