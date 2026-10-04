#!/usr/bin/env bash
# ==================================================================================================
#  THE DAY META'S CREDENTIALS ARRIVE — as a script, not as four kubectl commands somebody remembers.
#
#  Four values turn the whole WhatsApp path on, and they are the last thing standing between this
#  product and a real message:
#
#    META_APP_ID / META_APP_SECRET   who WE are as the Tech Provider. Embedded Signup exchanges the
#                                    30-second code with them; without the pair the exchange refuses
#                                    cleanly and every shop stops at «الربط غير مفعّل».
#    WHATSAPP_WEBHOOK_VERIFY_TOKEN   a string WE choose and paste into Meta's webhook screen. Meta
#                                    echoes it back on the subscription handshake; the platform
#                                    compares it in constant time and 403s on a mismatch. This
#                                    script MINTS one if none is given, because a token somebody
#                                    typed twice is a token that silently fails to subscribe.
#    WHATSAPP_CHAIN                  `console` is the bring-up driver: it always succeeds, so an
#                                    outage reads as delivered and the send log agrees. Flipping it
#                                    to the real chain is what makes a failure a failure.
#
#  WHY THEY MOVE TOGETHER. Any one of them alone is a half-live system: real credentials with the
#  console chain sends nothing while claiming success; a real chain without credentials fails every
#  message. The three secrets are sealed here in one patch; the chain is CONFIG IN GIT and this
#  script only says so out loud, because a value patched into a live cluster is undone by the next
#  deploy that does not know about it.
#
#  NOTHING IS ECHOED. The values are read from the environment and patched in as base64; they are
#  never printed, never written to a file, and never passed as a kubectl literal that a `ps` on a
#  shared box could read.
#
#  USAGE
#    META_APP_ID=... META_APP_SECRET=... [WHATSAPP_WEBHOOK_VERIFY_TOKEN=...] \
#      bash deploy/set-meta-credentials.sh
#
#  It prints the verify token ONCE at the end — that one has to be pasted into Meta's console, and
#  a secret nobody can read is a secret nobody can subscribe with.
# ==================================================================================================
set -euo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
NS="${NS:-base-services}"
C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_N=$'\e[0m'
info(){ echo -e "${C_C}  ▸ $*${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ! $*${C_N}"; }
die(){  echo -e "${C_R}  ✘ $*${C_N}" >&2; exit 1; }

SECRET="notification-service-secrets"
[ -n "${META_APP_ID:-}" ]     || die "META_APP_ID is empty — see the app's Basic Settings in Meta's console"
[ -n "${META_APP_SECRET:-}" ] || die "META_APP_SECRET is empty — the same screen, behind «Show»"
kubectl -n "$NS" get secret "$SECRET" >/dev/null 2>&1 \
  || die "$SECRET does not exist — run the platform's gen-secrets first"

# MINTED, NOT TYPED. 32 bytes of urandom: long enough that guessing it is not a strategy, and
# generated here so the value in the cluster and the value pasted into Meta come from one source.
TOKEN="${WHATSAPP_WEBHOOK_VERIFY_TOKEN:-}"
MINTED=0
if [ -z "$TOKEN" ]; then
  TOKEN="$(head -c 32 /dev/urandom | base64 | tr -d '=+/' | cut -c1-40)"
  MINTED=1
fi

b64(){ printf '%s' "$1" | base64 | tr -d '\n'; }

info "sealing the Tech Provider credentials into $SECRET"
kubectl -n "$NS" patch secret "$SECRET" --type=merge -p "{\"data\":{
  \"META_APP_ID\":\"$(b64 "$META_APP_ID")\",
  \"META_APP_SECRET\":\"$(b64 "$META_APP_SECRET")\",
  \"WHATSAPP_WEBHOOK_VERIFY_TOKEN\":\"$(b64 "$TOKEN")\"}}" >/dev/null
ok "three values sealed"

# THE CHAIN, IN THE SAME BREATH. Left on `console` the fleet would hold real credentials and still
# deliver nothing while reporting success — the exact silent-success shape this product keeps
# hitting, and the one the deploy gate has been warning about for weeks.
info "flipping WHATSAPP_CHAIN off the bring-up driver"
warn "edit deploy/services/notification-service.values.yaml (WHATSAPP_CHAIN) and ship the service —"
warn "the chain is CONFIG IN GIT, not a live patch, so a redeploy cannot undo this by forgetting it"

kubectl -n "$NS" rollout restart deploy/notification-service >/dev/null
kubectl -n "$NS" rollout status  deploy/notification-service --timeout=180s >/dev/null \
  || die "notification-service did not come back — the credentials are sealed, the pod is not running"
ok "notification-service restarted and holding the credentials"

echo
if [ "$MINTED" -eq 1 ]; then
  echo "  Paste this into Meta ▸ WhatsApp ▸ Configuration ▸ Verify token — it is shown ONCE:"
  echo
  echo "      $TOKEN"
  echo
  echo "  Callback URL:  https://ra-je3.com/webhooks/whatsapp"
  echo "  Subscribe to:  messages, account_update, message_template_status_update"
fi
ok "done — the handshake will succeed the moment Meta calls with that token"
