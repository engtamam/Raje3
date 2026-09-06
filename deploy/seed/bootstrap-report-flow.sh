#!/usr/bin/env bash
# Mint the ONE master weekly-report Flow every shop's clone descends from — run once, ever, per
# install. Mirrors bootstrap-rating-flow.sh exactly (rating-app-feature.md phase 6b); see that
# script's own docstring for the full reasoning, not repeated here.
#
#   ./deploy/seed/bootstrap-report-flow.sh
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

HERE="$(cd "$(dirname "$0")" && pwd)"
NS="${NS:-base-services}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

FLOW_JSON_FILE="$HERE/report-flow.json"
[ -f "$FLOW_JSON_FILE" ] || { red "no $FLOW_JSON_FILE — the master Flow's content lives there"; exit 2; }

OPS_POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^operations-/ && $3=="Running" {print $1; exit}')
[ -n "$OPS_POD" ] || { red "operations is not running"; exit 1; }
NOTIFY_POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^notification-service-/ && $3=="Running" {print $1; exit}')
[ -n "$NOTIFY_POD" ] || { red "notification-service is not running"; exit 1; }

KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
ADMIN=$(SEED_KEY="$KEY" python3 -c '
import os, jwt, time
now = int(time.time())
print(jwt.encode({"sub": "bootstrap-report-flow", "tenant": "_platform",
                  "caps": ["platform.config"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  "exp": now + 300},
                 os.environ["SEED_KEY"], algorithm="RS256"), end="")')
case "$ADMIN" in
  ey*) : ;;
  *) red "minting failed; got a ${#ADMIN}-character value that is not a JWT"; exit 1 ;;
esac

# ── 1. ALREADY DONE? ─────────────────────────────────────────────────────────────────────────
EXISTING=$(kubectl -n "$NS" exec -i "$OPS_POD" -- python - "$ADMIN" <<'PY'
import json, sys, urllib.request
admin = sys.argv[1]
req = urllib.request.Request("http://localhost:8000/api/v1/operator/config",
                             headers={"Authorization": "Bearer " + admin})
try:
    u = urllib.request.urlopen(req, timeout=15)
    out = json.loads(u.read() or b"{}")
    print(((out.get("config") or {}).get("MASTER_REPORT_FLOW_ID") or ""), end="")
except Exception:
    print("", end="")
PY
)
if [ -n "$EXISTING" ]; then
  grn "MASTER_REPORT_FLOW_ID already set ($EXISTING) — nothing to do"
  exit 0
fi

# ── 2. AUTHOR THE MASTER, ONCE ───────────────────────────────────────────────────────────────
INTERNAL_TOKEN=$(kubectl -n "$NS" get secret notification-service-secrets \
      -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$INTERNAL_TOKEN" ] || { red "no INTERNAL_SERVICE_TOKEN in notification-service-secrets"; exit 1; }

echo "authoring the master weekly-report Flow on the platform's own WABA"
# NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS (seed-templates.sh's lesson).
FLOW_ID=$(kubectl -n "$NS" exec -i "$NOTIFY_POD" -- python - "$INTERNAL_TOKEN" <<PY
import json, sys, urllib.error, urllib.request
token = sys.argv[1]
FLOW_JSON = json.loads('''$(cat "$FLOW_JSON_FILE")''')
FLOW_JSON.pop("_readme", None)
body = json.dumps({
    "tenant": "_platform",
    "name": "report_flow",
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

# ── 3. STORE IT ───────────────────────────────────────────────────────────────────────────────
kubectl -n "$NS" exec -i "$OPS_POD" -- python - "$ADMIN" "$FLOW_ID" <<'PY'
import json, sys, urllib.error, urllib.request
admin, flow_id = sys.argv[1], sys.argv[2]
body = json.dumps({"tenant": "", "key": "MASTER_REPORT_FLOW_ID", "value": flow_id}).encode()
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
  grn "MASTER_REPORT_FLOW_ID stored in operations' runtime config"
else
  red "authored the Flow but failed to store its id — re-run this script; it is idempotent by name"
  exit 1
fi
