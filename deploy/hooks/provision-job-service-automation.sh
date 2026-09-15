#!/usr/bin/env bash
# ==================================================================================================
#  A REAL, PERSISTENT SERVICE ACCOUNT FOR job-service SCHEDULE/DISPATCH ADMIN ACTIONS
# --------------------------------------------------------------------------------------------------
#  WHY THIS EXISTS, AND WHY NOT THE EARLIER SELF-SIGNED-JWT APPROACH. Migrating a service's own
#  CronJob to job-service needs an admin action gated by `platform.jobs` (creating/deleting a
#  schedule). The owner's own instruction (2026-09-15): every such action must be attributable to
#  automation in job-service's own audit log, never to the platform owner personally. An earlier
#  version of this tooling minted a short-lived, self-signed JWT per call (the same technique
#  seed-roles.sh uses for its own one-time bootstrap) — that technique is real and used elsewhere in
#  this codebase, but it is NOT the standard, ongoing pattern: it cannot be rotated or revoked on
#  its own (only by rotating the whole fleet's TOKEN_PRIVATE_KEY), and nothing distinguishes ONE
#  automation task from another in an audit trail beyond a `sub` string nobody enforces.
#
#  THE ACTUAL INDUSTRY STANDARD (checked 2026-09-16): a DEDICATED, PERSISTENT service account —
#  OAuth2 client-credentials, least-privilege-scoped, rotatable and revocable on its own — is what
#  this codebase ALREADY does for operations' own read of billing-service
#  (deploy/hooks/provision-billing-service-account.sh, BILLING_CLIENT_ID/SECRET). This script is the
#  SAME pattern for job-service's admin API, mirrored line for line: log in ONCE as whichever
#  administration account already exists, mint a service account scoped to EXACTLY `platform.jobs`
#  (identity refuses granting anything the issuer does not also hold — see that account's own
#  `grantable_caps` rule), and seal the resulting client_id/secret into its own dedicated k8s secret.
#  From then on, deploy/hooks/job-schedule.sh mints its OWN short bearer from THIS credential via
#  the ordinary client_credentials grant (identical to how operations' renewal_provider.py mints its
#  own platform.billing bearer) — job-service's audit log names this service account as the actor,
#  never the human who ran this script once.
#
#  IDEMPOTENT BY WHAT THE SECRET ALREADY HOLDS, same reasoning as provision-billing-service-account.sh's
#  own header: identity has no "give me back the same secret" route, so re-issuing on every re-run
#  would abandon the previous account. If the secret already has a value, this script does nothing.
#
#  USAGE
#    ADMIN_PHONE=… ADMIN_PASSWORD=… bash deploy/hooks/provision-job-service-automation.sh
# ==================================================================================================
set -Eeuo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"
NS="${NS:-base-services}"
TENANT="${ADMIN_TENANT:-_platform}"
SECRET_NAME="job-service-automation-secrets"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_N=$'\e[0m'
info(){ echo -e "${C_C}  ▸ $*${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ! $*${C_N}"; }
die(){  echo -e "\e[31m  ✘ $*${C_N}" >&2; exit 1; }

if [ -z "${ADMIN_PHONE:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
  warn "no administration account was asked for — skipping (mint this by hand later once one exists)"
  exit 0
fi

EXISTING="$(kubectl -n "$NS" get secret "$SECRET_NAME" \
            -o jsonpath='{.data.JOB_CLIENT_SECRET}' 2>/dev/null || true)"
if [ -n "$EXISTING" ]; then
  ok "a job-service automation credential already exists — nothing to do"
  exit 0
fi

POD=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
      | awk '/^identity-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || die "identity-service is not running — the credential cannot be minted"

info "minting a platform.jobs service account (as ${ADMIN_PHONE}, tenant ${TENANT})"

# THE PASSWORD TRAVELS ON STDIN, NEVER ON A COMMAND LINE — same reasoning as
# provision-billing-service-account.sh's own header.
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
                   {"name": "job-service-automation", "caps": ["platform.jobs"]},
                   token=access_token)
except urllib.error.HTTPError as exc:
    sys.exit(f"identity refused the service account ({exc.code}): "
             f"{exc.read().decode(errors='replace')[:200]}")

client_id = account.get("client_id") or ""
client_secret = account.get("client_secret") or ""
if not client_id or not client_secret:
    sys.exit("identity minted a service account but the response carried no client_id/secret")

print(f"{client_id}\t{client_secret}")
PY
)"

RESULT="$(printf '%s' "$ADMIN_PASSWORD" | kubectl -n "$NS" exec -i "$POD" -- \
  python -c "import base64; exec(base64.b64decode('$PY_B64'))" "$TENANT" "$ADMIN_PHONE")" \
  || die "minting the service account failed — see the output above"

CLIENT_ID="$(printf '%s' "$RESULT" | cut -f1)"
CLIENT_SECRET="$(printf '%s' "$RESULT" | cut -f2)"
[ -n "$CLIENT_ID" ] && [ -n "$CLIENT_SECRET" ] || die "no client_id/secret came back — refusing to seal an empty credential"
ok "service account minted ($CLIENT_ID) — scoped to exactly platform.jobs"

info "sealing JOB_CLIENT_ID/JOB_CLIENT_SECRET into $SECRET_NAME"
kubectl -n "$NS" create secret generic "$SECRET_NAME" \
  --from-literal=JOB_CLIENT_ID="$CLIENT_ID" \
  --from-literal=JOB_CLIENT_SECRET="$CLIENT_SECRET" \
  --dry-run=client -o yaml | kubectl -n "$NS" apply -f - >/dev/null
ok "sealed — deploy/hooks/job-schedule.sh will use this credential from now on, never a human login"
