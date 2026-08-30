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

# The object store credential, which our services reach the same way theirs do.
OS_JSON="$(kubectl -n "$NS" get secret objectstore-secrets -o jsonpath='{.data.s3\.json}' 2>/dev/null | base64 -d || true)"
OS_AK="$(printf '%s' "$OS_JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["identities"][0]["credentials"][0]["accessKey"])' 2>/dev/null || true)"
OS_SK="$(printf '%s' "$OS_JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["identities"][0]["credentials"][0]["secretKey"])' 2>/dev/null || true)"

info "minting ${OURS// /, }"
for svc in $OURS; do
  DSN="${BASE_DSN%/*}/$svc"
  args=(--from-literal="DATASTORE_DSN=$DSN")
  [ -n "$OS_AK" ] && args+=(--from-literal="OBJECTSTORE_ACCESS_KEY=$OS_AK")
  [ -n "$OS_SK" ] && args+=(--from-literal="OBJECTSTORE_SECRET_KEY=$OS_SK")

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
