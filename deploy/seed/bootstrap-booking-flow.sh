#!/usr/bin/env bash
# Mint the ONE master booking Flow every shop's clone descends from — run once, ever, per install.
#
#   ./deploy/seed/bootstrap-booking-flow.sh
#
# WHY THIS EXISTS (assignment-mode redesign, Phase 5). Same "one master, cloned per shop" shape
# every clone-per-shop Flow in core/flows.py follows — with ONE real difference from a Flow whose
# content is a hand-authored, never-changing static file: the booking Flow is DYNAMIC and its
# content is GENERATED, by notification-service itself, from its own WHATSAPP_BOOKING_DEFINITION
# config — so this script asks the running service for the JSON
# (`GET /internal/whatsapp/flow/booking-json`) rather than reading a file nobody wrote by hand.
# The generator's own docstring guarantees the screens/field names can never drift from the
# engine that answers them, which a hand-authored file could never promise for a dynamic Flow.
#
# IDEMPOTENT TWICE OVER, so a re-run (safe to leave in the install chain forever):
#   1. If operations already has MASTER_BOOKING_FLOW_ID set, this exits without calling Meta again.
#   2. Even if it did not skip, notification-service's own provision route is idempotent BY NAME.
#
# WHERE THE RESULT LIVES. operations' own runtime-config override (PUT /api/v1/operations/operator/config,
# platform scope: tenant="") — the very next connect() reads it live, no restart required.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

NS="${NS:-base-services}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }
ylw(){ printf '  \e[33m! %s\e[0m\n' "$*"; }

OPS_POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^operations-/ && $3=="Running" {print $1; exit}')
[ -n "$OPS_POD" ] || { red "operations is not running"; exit 1; }
NOTIFY_POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^notification-service-/ && $3=="Running" {print $1; exit}')
[ -n "$NOTIFY_POD" ] || { red "notification-service is not running"; exit 1; }

KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
# THE kid HEADER — see seed-roles.sh's own note (and seed-backup-targets.sh, which carries the
# identical block). A token minted with none is rejected by every JWKS verifier on this fleet as
# 401 UNAUTHORIZED, not a mere missing-capability 403 — found live on this reinstall: this script
# predated that fix and never got it, so "storing the config failed: UNAUTHORIZED" every run,
# authored Flow and all, never actually landing MASTER_BOOKING_FLOW_ID. Thumbprints the SAME key
# it signs with (RFC 7638, identical to identity-service's own `public_jwk`), so it works across a
# rotation with no code change here.
ADMIN=$(SEED_KEY="$KEY" python3 -c '
import base64, hashlib, json, os, jwt, time
from jwt.algorithms import RSAAlgorithm
now = int(time.time())
private_pem = os.environ["SEED_KEY"]
key_obj = RSAAlgorithm(RSAAlgorithm.SHA256).prepare_key(private_pem)
jwk = json.loads(RSAAlgorithm.to_jwk(key_obj))
canonical = json.dumps({"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]},
                       separators=(",", ":"), sort_keys=True).encode("ascii")
kid = base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode("ascii")
print(jwt.encode({"sub": "bootstrap-booking-flow", "tenant": "_platform",
                  "caps": ["platform.config"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  "exp": now + 300},
                 private_pem, algorithm="RS256", headers={"kid": kid}), end="")')
case "$ADMIN" in
  ey*) : ;;
  *) red "minting failed; got a ${#ADMIN}-character value that is not a JWT"; exit 1 ;;
esac

# ── 1. ALREADY DONE? ─────────────────────────────────────────────────────────────────────────
EXISTING=$(kubectl -n "$NS" exec -i "$OPS_POD" -- python - "$ADMIN" <<'PY'
import json, sys, urllib.request
admin = sys.argv[1]
req = urllib.request.Request("http://localhost:8000/api/v1/operations/operator/config",
                             headers={"Authorization": "Bearer " + admin})
try:
    u = urllib.request.urlopen(req, timeout=15)
    out = json.loads(u.read() or b"{}")
    print(((out.get("config") or {}).get("MASTER_BOOKING_FLOW_ID") or ""), end="")
except Exception:
    print("", end="")
PY
)
if [ -n "$EXISTING" ]; then
  grn "MASTER_BOOKING_FLOW_ID already set ($EXISTING) — nothing to do"
  exit 0
fi

INTERNAL_TOKEN=$(kubectl -n "$NS" get secret notification-service-secrets \
      -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$INTERNAL_TOKEN" ] || { red "no INTERNAL_SERVICE_TOKEN in notification-service-secrets"; exit 1; }

# ── 2. FETCH THE GENERATED JSON, THEN AUTHOR THE MASTER ─────────────────────────────────────
# ONE POD, ONE PYTHON PROCESS for both steps — the generated JSON never touches a shell variable
# (Windows Git Bash / kubectl exec quoting has bitten this exact pattern before — see
# seed-templates.sh's own lesson on quoted heredocs) — it stays inside the running interpreter
# from the moment it is read to the moment it is sent back out to Meta.
echo "generating + authoring the master booking Flow on the platform's own WABA"
FLOW_ID=$(kubectl -n "$NS" exec -i "$NOTIFY_POD" -- python - "$INTERNAL_TOKEN" <<'PY'
import json, sys, urllib.error, urllib.request
token = sys.argv[1]
headers = {"X-Internal-Token": token, "Content-Type": "application/json"}

req = urllib.request.Request(
    "http://localhost:8000/internal/whatsapp/flow/booking-json", headers=headers)
try:
    u = urllib.request.urlopen(req, timeout=15)
    flow_json = json.loads(u.read() or b"{}")
except urllib.error.HTTPError as e:
    if e.code == 404:
        sys.stderr.write(
            "NO_BOOKING_DEFINITION — set WHATSAPP_BOOKING_DEFINITION on notification-service "
            "before running this script (see deploy/services/notification-service.values.yaml)\n")
    else:
        sys.stderr.write("fetching the generated Flow JSON failed: %s\n" % e.read().decode()[:300])
    sys.exit(1)

body = json.dumps({
    "tenant": "_platform",
    "name": "booking_flow",
    "categories": ["APPOINTMENT_BOOKING"],
    "flow_json": json.dumps(flow_json),
    "publish": True,
}).encode()
req2 = urllib.request.Request(
    "http://localhost:8000/internal/whatsapp/flows/provision", data=body, method="POST",
    headers=headers)
try:
    u = urllib.request.urlopen(req2, timeout=30)
    out = json.loads(u.read() or b"{}")
except urllib.error.HTTPError as e:
    sys.stderr.write("provision failed: %s\n" % e.read().decode()[:300])
    sys.exit(1)
if not out.get("ok") or not out.get("flow_id"):
    sys.stderr.write("provision returned no flow_id: %s\n" % json.dumps(out)[:300])
    sys.exit(1)
print(out["flow_id"], end="")
PY
) || { red "authoring the master Flow failed"; exit 1; }
[ -n "$FLOW_ID" ] || { red "no flow_id came back"; exit 1; }
grn "master Flow authored: $FLOW_ID"

# ── 3. STORE IT ───────────────────────────────────────────────────────────────────────────────
kubectl -n "$NS" exec -i "$OPS_POD" -- python - "$ADMIN" "$FLOW_ID" <<'PY'
import json, sys, urllib.error, urllib.request
admin, flow_id = sys.argv[1], sys.argv[2]
body = json.dumps({"tenant": "", "key": "MASTER_BOOKING_FLOW_ID", "value": flow_id}).encode()
req = urllib.request.Request("http://localhost:8000/api/v1/operations/operator/config", data=body,
                             method="PUT",
                             headers={"Authorization": "Bearer " + admin,
                                      "Content-Type": "application/json"})
try:
    u = urllib.request.urlopen(req, timeout=15)
    json.loads(u.read() or b"{}")
except urllib.error.HTTPError as e:
    sys.stderr.write("storing the config failed: %s\n" % e.read().decode()[:300])
    sys.exit(1)
PY
if [ $? -eq 0 ]; then
  grn "MASTER_BOOKING_FLOW_ID stored in operations' runtime config"
  grn "each shop's own Flow-encryption key is sealed automatically at connect time (base-services"
  grn "v0.18.55, operations/app/api/v1/connect.py) — no further manual step needed per shop."
else
  red "authored the Flow but failed to store its id — re-run this script; it is idempotent by name"
  exit 1
fi
