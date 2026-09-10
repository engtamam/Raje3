#!/usr/bin/env bash
# Mint the ONE master subscription-renewal Flow every shop's clone descends from — run once, ever,
# per install.
#
#   ./deploy/seed/bootstrap-subscription-renewal-flow.sh
#
# WHY THIS EXISTS. Mirrors bootstrap-rating-flow.sh/bootstrap-report-flow.sh EXACTLY (see either
# for the full "one master, cloned per shop" reasoning) — this Flow's content is a STATIC,
# hand-authored file (subscription-renewal-flow.json), same as rating/report, even though the
# Flow itself is DYNAMIC (data_exchange, answered live by operations' own
# app/adapters/renewal_provider.py through platform v0.19.12's
# LoyaltyEngine(name="subscription_renewal")) — "static content" and "dynamic Flow" are different
# axes: the screens' LAYOUT is fixed and authored once here; what fills `${data.*}` on each
# screen is live, per-shop, per-invoice. The per-shop endpoint_uri that makes the live half work
# is set at CLONE time (operations/app/api/v1/connect.py), not here on the master.
#
# IDEMPOTENT TWICE OVER, so a re-run (safe to leave in the install chain forever):
#   1. If operations already has MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID set, this exits without
#      calling Meta again.
#   2. Even if it did not skip, notification-service's own provision route is idempotent BY NAME.
#
# WHERE THE RESULT LIVES. operations' own runtime-config override (PUT /api/v1/operator/config,
# platform scope: tenant="") — the very next connect() reads it live, no restart required.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

HERE="$(cd "$(dirname "$0")" && pwd)"
NS="${NS:-base-services}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

FLOW_JSON_FILE="$HERE/subscription-renewal-flow.json"
[ -f "$FLOW_JSON_FILE" ] || { red "no $FLOW_JSON_FILE — the master Flow's content lives there"; exit 2; }

OPS_POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^operations-/ && $3=="Running" {print $1; exit}')
[ -n "$OPS_POD" ] || { red "operations is not running"; exit 1; }
NOTIFY_POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^notification-service-/ && $3=="Running" {print $1; exit}')
[ -n "$NOTIFY_POD" ] || { red "notification-service is not running"; exit 1; }

# THE SIGNING KEY NEVER TOUCHES DISK (seed-backup-targets.sh's fix) — the environment carries it.
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
ADMIN=$(SEED_KEY="$KEY" python3 -c '
import os, jwt, time
now = int(time.time())
print(jwt.encode({"sub": "bootstrap-subscription-renewal-flow", "tenant": "_platform",
                  "caps": ["platform.config"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  "exp": now + 300},
                 os.environ["SEED_KEY"], algorithm="RS256"), end="")')
case "$ADMIN" in
  ey*) : ;;
  *) red "minting failed; got a ${#ADMIN}-character value that is not a JWT"; exit 1 ;;
esac

# ── 1. ALREADY DONE? — read operations' own effective config, platform scope ───────────────────
EXISTING=$(kubectl -n "$NS" exec -i "$OPS_POD" -- python - "$ADMIN" <<'PY'
import json, sys, urllib.request
admin = sys.argv[1]
req = urllib.request.Request("http://localhost:8000/api/v1/operator/config",
                             headers={"Authorization": "Bearer " + admin})
try:
    u = urllib.request.urlopen(req, timeout=15)
    out = json.loads(u.read() or b"{}")
    print(((out.get("config") or {}).get("MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID") or ""), end="")
except Exception:
    print("", end="")
PY
)
if [ -n "$EXISTING" ]; then
  grn "MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID already set ($EXISTING) — nothing to do"
  exit 0
fi

# ── 2. AUTHOR THE MASTER, ONCE — the internal token, not a JWT: this is service-to-service ─────
INTERNAL_TOKEN=$(kubectl -n "$NS" get secret notification-service-secrets \
      -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$INTERNAL_TOKEN" ] || { red "no INTERNAL_SERVICE_TOKEN in notification-service-secrets"; exit 1; }

echo "authoring the master subscription-renewal Flow on the platform's own WABA"
# NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS (seed-templates.sh's lesson) — the
# heredoc is unquoted because it interpolates the Flow JSON.
FLOW_ID=$(kubectl -n "$NS" exec -i "$NOTIFY_POD" -- python - "$INTERNAL_TOKEN" <<PY
import json, sys, urllib.error, urllib.request
token = sys.argv[1]
FLOW_JSON = json.loads('''$(cat "$FLOW_JSON_FILE")''')
FLOW_JSON.pop("_readme", None)
body = json.dumps({
    "tenant": "_platform",
    "name": "subscription_renewal",
    "categories": ["OTHER"],
    "flow_json": json.dumps(FLOW_JSON),
    "publish": True,
}).encode()
req = urllib.request.Request(
    "http://localhost:8000/internal/whatsapp/flows/provision", data=body, method="POST",
    headers={"X-Internal-Token": token, "Content-Type": "application/json"})
try:
    u = urllib.request.urlopen(req, timeout=30)
    out = json.loads(u.read() or b"{}")
except urllib.error.HTTPError as e:
    sys.stderr.write("provision failed: %s\\n" % e.read().decode()[:300])
    sys.exit(1)
if not out.get("ok") or not out.get("flow_id"):
    sys.stderr.write("provision returned no flow_id: %s\\n" % json.dumps(out)[:300])
    sys.exit(1)
print(out["flow_id"], end="")
PY
) || { red "authoring the master Flow failed"; exit 1; }
[ -n "$FLOW_ID" ] || { red "no flow_id came back"; exit 1; }
grn "master Flow authored: $FLOW_ID"

# ── 3. STORE IT — platform scope, so every shop's connect() reads it with no redeploy ──────────
kubectl -n "$NS" exec -i "$OPS_POD" -- python - "$ADMIN" "$FLOW_ID" <<'PY'
import json, sys, urllib.error, urllib.request
admin, flow_id = sys.argv[1], sys.argv[2]
body = json.dumps({"tenant": "", "key": "MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID",
                   "value": flow_id}).encode()
req = urllib.request.Request("http://localhost:8000/api/v1/operator/config", data=body,
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
  grn "MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID stored in operations' runtime config"
  grn "each shop's own Flow-encryption key is sealed automatically at connect time (base-services"
  grn "v0.18.55, operations/app/api/v1/connect.py) — no further manual step needed per shop."
else
  red "authored the Flow but failed to store its id — re-run this script; it is idempotent by name"
  exit 1
fi
