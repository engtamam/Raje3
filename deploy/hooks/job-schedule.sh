#!/usr/bin/env bash
# ==================================================================================================
#  CREATE/LIST/DELETE A job-service SCHEDULE — THE REPLACEMENT FOR ONE K8S CronJob, ONE CALL AT A TIME
# --------------------------------------------------------------------------------------------------
#  WHY THIS EXISTS. Migrating a service's own CronJob to job-service's push-dispatch (base-services
#  v0.24.0) needs exactly one admin action first: register a `schedule` (POST /api/v1/jobs/schedules),
#  gated by the `platform.jobs` capability — a real Principal, not the fleet's shared internal token.
#
#  NEVER THE PLATFORM OWNER'S OWN LOGIN (the owner's own instruction, 2026-09-15/16: every action
#  here must be attributable to automation, not to a person, through a REAL, PERSISTENT, rotatable
#  service account — the industry-standard pattern, not a one-off self-signed token). This mints a
#  bearer via the ordinary OAuth2 client-credentials grant, using JOB_CLIENT_ID/JOB_CLIENT_SECRET
#  from `job-service-automation-secrets` (provisioned once, at install time, by
#  deploy/hooks/provision-job-service-automation.sh — see that script's own header for why this
#  replaced an earlier self-signed-JWT draft). The SAME pattern operations' own
#  `renewal_provider.py` already uses to mint its `platform.billing` bearer — this is that pattern's
#  second occurrence, not a new one. job-service's own audit log then names the service account
#  ("job-service-automation") as the actor for every call this script makes, never the owner.
#
#  USAGE
#    ./deploy/hooks/job-schedule.sh create <name> <cron> <queue> <type> [tenant=global] [payload_json]
#    ./deploy/hooks/job-schedule.sh list
#    ./deploy/hooks/job-schedule.sh delete <schedule_id>
#
#  Run by a human operator with real cluster access (this file follows the existing deploy/hooks
#  kubectl-exec pattern) — never by an automated agent without that access.
# ==================================================================================================
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$HERE/../cluster.sh"
NS="${NS:-base-services}"

C_G=$'\e[32m'; C_R=$'\e[31m'; C_C=$'\e[36m'; C_N=$'\e[0m'
ok(){  echo -e "${C_G}  ✔ $*${C_N}"; }
red(){ echo -e "${C_R}  ✘ $*${C_N}" >&2; }
info(){ echo -e "${C_C}  ▸ $*${C_N}"; }

ACTION="${1:-}"
[ -n "$ACTION" ] || { red "usage: $0 create|list|delete ..."; exit 2; }

IDENTITY_POD=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
              | awk '/^identity-service-/ && $3=="Running" {print $1; exit}')
[ -n "$IDENTITY_POD" ] || { red "identity-service is not running — cannot mint a token"; exit 1; }

JOB_POD=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
         | awk '/^job-service-/ && $3=="Running" {print $1; exit}')
[ -n "$JOB_POD" ] || { red "job-service is not running"; exit 1; }

CLIENT_ID=$(kubectl -n "$NS" get secret job-service-automation-secrets \
           -o jsonpath='{.data.JOB_CLIENT_ID}' 2>/dev/null | base64 -d)
CLIENT_SECRET=$(kubectl -n "$NS" get secret job-service-automation-secrets \
                -o jsonpath='{.data.JOB_CLIENT_SECRET}' 2>/dev/null | base64 -d)
if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
  red "no job-service automation credential — run deploy/hooks/provision-job-service-automation.sh first"
  exit 1
fi

# THE ORDINARY client_credentials GRANT, FROM THE IDENTITY POD ITSELF (loopback, no ingress
# needed) — the credential never leaves the cluster, and this bearer is good for whatever
# `expires_in` identity-service issues (short-lived by its own default), not five minutes chosen
# by this script.
TOKEN=$(kubectl -n "$NS" exec -i "$IDENTITY_POD" -- python - "$CLIENT_ID" "$CLIENT_SECRET" <<'PY'
import json, sys, urllib.error, urllib.request
client_id, client_secret = sys.argv[1:3]
body = json.dumps({"grant_type": "client_credentials", "client_id": client_id,
                   "client_secret": client_secret}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/v1/oauth/token", data=body,
                             method="POST", headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(json.loads(resp.read()).get("access_token", ""), end="")
except urllib.error.HTTPError as exc:
    sys.exit(f"identity refused the client-credentials grant ({exc.code}): "
             f"{exc.read().decode(errors='replace')[:200]}")
PY
)
case "$TOKEN" in
  ey*) : ;;
  *) red "minting failed; got a ${#TOKEN}-character value that is not a JWT"; exit 1 ;;
esac

case "$ACTION" in
  list)
    kubectl -n "$NS" exec -i "$JOB_POD" -- python - "$TOKEN" <<'PY'
import json, sys, urllib.error, urllib.request
token = sys.argv[1]
req = urllib.request.Request("http://127.0.0.1:8000/api/v1/jobs/schedules",
                             headers={"Authorization": "Bearer " + token})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(json.dumps(json.loads(resp.read()), ensure_ascii=False, indent=2))
except urllib.error.HTTPError as exc:
    sys.exit(f"job-service refused ({exc.code}): {exc.read().decode(errors='replace')[:300]}")
PY
    ;;
  create)
    NAME="${2:?usage: create <name> <cron> <queue> <type> [tenant] [payload_json]}"
    CRON="${3:?cron expression required}"
    QUEUE="${4:?queue name required}"
    TYPE="${5:?job type required}"
    TENANT="${6:-global}"
    PAYLOAD="${7:-{\}}"
    info "creating schedule '$NAME' ($CRON) on queue '$QUEUE', tenant '$TENANT'"
    kubectl -n "$NS" exec -i "$JOB_POD" -- python - "$TOKEN" "$NAME" "$CRON" "$QUEUE" "$TYPE" "$TENANT" "$PAYLOAD" <<'PY'
import json, sys, urllib.error, urllib.request
token, name, cron, queue, type_, tenant, payload_json = sys.argv[1:8]
body = json.dumps({"name": name, "cron": cron, "queue": queue, "type": type_,
                   "tenant": tenant, "payload": json.loads(payload_json)}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/v1/jobs/schedules", data=body,
                             method="POST",
                             headers={"Authorization": "Bearer " + token,
                                      "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(json.dumps(json.loads(resp.read()), ensure_ascii=False, indent=2))
except urllib.error.HTTPError as exc:
    sys.exit(f"job-service refused ({exc.code}): {exc.read().decode(errors='replace')[:300]}")
PY
    ok "schedule created"
    ;;
  delete)
    SCHEDULE_ID="${2:?usage: delete <schedule_id>}"
    kubectl -n "$NS" exec -i "$JOB_POD" -- python - "$TOKEN" "$SCHEDULE_ID" <<'PY'
import sys, urllib.error, urllib.request
token, sid = sys.argv[1:3]
req = urllib.request.Request(f"http://127.0.0.1:8000/api/v1/jobs/schedules/{sid}",
                             method="DELETE", headers={"Authorization": "Bearer " + token})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(resp.read().decode())
except urllib.error.HTTPError as exc:
    sys.exit(f"job-service refused ({exc.code}): {exc.read().decode(errors='replace')[:300]}")
PY
    ok "schedule deleted"
    ;;
  *)
    red "unknown action '$ACTION' — use create|list|delete"
    exit 2
    ;;
esac
