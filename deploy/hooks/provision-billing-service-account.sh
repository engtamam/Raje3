#!/usr/bin/env bash
# ==================================================================================================
#  THE CROSS-TENANT CREDENTIAL operations-service NEEDS FROM billing-service, MINTED AT INSTALL TIME
# --------------------------------------------------------------------------------------------------
#  Two things operations-service runs — the partner commission statement (adapters/settlements.py)
#  and the wallet top-up reconcile poller (core/wallet_topup_reconcile.py) — read billing-service
#  routes declared on the ADMIN tier (platform.billing), never the internal one: cross-tenant money
#  data is not something the fleet's shared internal secret should unlock for free. So a service
#  that wants it presents a real capability token instead, the same way a human would.
#
#  BEFORE THIS SCRIPT, THAT TOKEN DID NOT EXIST ANYWHERE — BILLING_CLIENT_ID/BILLING_CLIENT_SECRET
#  sat declared in operations' own config.py with nothing to fill them, on every fresh install, and
#  BOTH features ran permanently idle (the settlement sweep issuing nothing, the reconcile poller
#  reporting "unreachable") until somebody minted one BY HAND and pasted it in. This script is that
#  step, run once by the installer instead.
#
#  WHAT IT DOES. Logs in as the administration account seed-admin.sh just created (the only
#  identity that exists yet and holds BOTH platform.billing and service_accounts:write — see
#  deploy/seed/operator-roles.json's own platform-owner entry), asks identity-service to mint a
#  machine identity scoped to EXACTLY platform.billing (never more — grantable_caps refuses
#  anything the issuer does not also hold), and seals the resulting client_id/client_secret straight
#  into operations-secrets. Nobody, including whoever runs this script, ever sees the secret land
#  anywhere but inside the cluster — it is read once from identity-service's one-time response and
#  piped directly into `kubectl patch`.
#
#  WHY A LOGIN RATHER THAN AN INTERNAL-TOKEN CALL. /api/v1/service-accounts is gated by
#  require_cap(SERVICE_ACCOUNTS_WRITE_CAP) on a human Principal — there is no internal-tier route
#  that mints one, on purpose (minting a cross-tenant credential is exactly the kind of act that
#  must be attributable to a person, not to "the mesh"). seed-admin.sh's own bootstrap problem (no
#  role exists yet to check) does not apply here — this runs AFTER seed-roles.sh and seed-admin.sh,
#  by which point the platform-owner account is real and holds the caps this needs.
#
#  IDEMPOTENT BY WHAT operations-secrets ALREADY HOLDS, NOT BY ASKING IDENTITY. Re-issuing on every
#  re-run would mint a fresh, unrelated service account each time and abandon the previous one
#  active against SERVICE_ACCOUNTS_MAX_PER_TENANT — identity has no "give me back the same secret"
#  route (secrets are one-time by design), so the only safe idempotency check is: does the secret
#  already have a value. If it does, this script has already run and does nothing.
#
#  NO ADMIN ACCOUNT, NO ATTEMPT — same posture as seed-admin.sh's own: an install that skipped the
#  admin account cannot log in as one, and that is a deferral, not a failure. Both features stay
#  idle until an operator runs this by hand once a platform-owner account exists.
#
#  USAGE
#    ADMIN_PHONE=… ADMIN_PASSWORD=… bash deploy/hooks/provision-billing-service-account.sh
# ==================================================================================================
set -Eeuo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"
NS="${NS:-base-services}"
TENANT="${ADMIN_TENANT:-_platform}"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_D=$'\e[2m'; C_N=$'\e[0m'
info(){ echo -e "${C_C}  ▸ $*${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ! $*${C_N}"; }
die(){  echo -e "\e[31m  ✘ $*${C_N}" >&2; exit 1; }

if [ -z "${ADMIN_PHONE:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
  warn "no administration account was asked for — skipping (mint this by hand later once one exists)"
  exit 0
fi

# ALREADY SEALED — the whole idempotency check, and it is enough: see this file's own header.
EXISTING="$(kubectl -n "$NS" get secret operations-secrets \
            -o jsonpath='{.data.BILLING_CLIENT_SECRET}' 2>/dev/null || true)"
if [ -n "$EXISTING" ]; then
  ok "operations already holds a billing service-account credential — nothing to do"
  exit 0
fi

POD=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
      | awk '/^identity-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || die "identity-service is not running — the credential cannot be minted"

info "minting a platform.billing service account for operations (as ${ADMIN_PHONE}, tenant ${TENANT})"

# THE PASSWORD TRAVELS ON STDIN, NEVER ON A COMMAND LINE — same reason seed-admin.sh's own header
# gives at length: an argument is visible in `ps` to every process on the node for as long as the
# call runs, and this credential opens the administration account itself.
PY_B64="$(base64 -w0 <<'PY'
import json
import sys
import urllib.error
import urllib.request

tenant, phone = sys.argv[1:3]
password = sys.stdin.read().strip()
if not password:
    sys.exit("the password did not reach the pod — refusing to log in without one")

BASE = "http://127.0.0.1:8000"


def call(path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:      # nosec B310 - loopback, in-pod
        return json.loads(resp.read() or b"{}")


try:
    logged_in = call("/api/v1/auth/login",
                     {"tenant": tenant, "username": phone, "password": password})
except urllib.error.HTTPError as exc:
    sys.exit(f"could not log in as {phone} ({exc.code}): "
             f"{exc.read().decode(errors='replace')[:200]}")
access_token = logged_in.get("access_token") or ""
if not access_token:
    sys.exit("login answered with no access_token — cannot mint a service account without one")

try:
    account = call("/api/v1/service-accounts",
                   {"name": "operations-billing-reader", "caps": ["platform.billing"]},
                   token=access_token)
except urllib.error.HTTPError as exc:
    sys.exit(f"identity refused the service account ({exc.code}): "
             f"{exc.read().decode(errors='replace')[:200]}")

client_id = account.get("client_id") or ""
client_secret = account.get("client_secret") or ""
if not client_id or not client_secret:
    sys.exit("identity minted a service account but the response carried no client_id/secret")

# THE ONLY LINE THAT PRINTS ANYTHING — read by the shell below and piped straight into
# `kubectl patch`, never echoed, never logged.
print(f"{client_id}\t{client_secret}")
PY
)"

RESULT="$(printf '%s' "$ADMIN_PASSWORD" | kubectl -n "$NS" exec -i "$POD" -- \
  python -c "import base64; exec(base64.b64decode('$PY_B64'))" "$TENANT" "$ADMIN_PHONE")" \
  || die "minting the service account failed — see the output above"

CLIENT_ID="$(printf '%s' "$RESULT" | cut -f1)"
CLIENT_SECRET="$(printf '%s' "$RESULT" | cut -f2)"
[ -n "$CLIENT_ID" ] && [ -n "$CLIENT_SECRET" ] || die "no client_id/secret came back — refusing to seal an empty credential"
ok "service account minted ($CLIENT_ID)"

info "sealing BILLING_CLIENT_ID/BILLING_CLIENT_SECRET into operations-secrets"
kubectl -n "$NS" patch secret operations-secrets --type=merge -p \
  "{\"data\":{\"BILLING_CLIENT_ID\":\"$(printf '%s' "$CLIENT_ID" | base64 -w0)\",\"BILLING_CLIENT_SECRET\":\"$(printf '%s' "$CLIENT_SECRET" | base64 -w0)\"}}" >/dev/null
ok "sealed"

info "restarting operations to pick it up"
kubectl -n "$NS" rollout restart deploy/operations >/dev/null
kubectl -n "$NS" rollout status  deploy/operations --timeout=180s >/dev/null \
  || die "operations did not come back — the credential is sealed, the pod is not running"
ok "operations restarted — the partner statement and the wallet top-up reconcile poller can now read billing-service"
