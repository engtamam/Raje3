#!/usr/bin/env bash
# ==================================================================================================
#  REGISTER/LIST/DELETE A job-service PUSH-DISPATCH WEBHOOK FOR ONE QUEUE
# --------------------------------------------------------------------------------------------------
#  /internal/dispatch/targets is internal-token-gated (no `platform.jobs` capability needed) — the
#  fleet's shared secret is enough, same as every other internal-tier call. See job-schedule.sh's
#  own header for the companion step (creating the schedule that actually enqueues onto this queue).
#
#  THE TARGET HOST MUST ALREADY BE IN job-service's OWN EGRESS_ALLOWED_HOSTS
#  (deploy/services/job-service.values.yaml) or registration is refused (SSRF guard, by design).
#
#  USAGE
#    ./deploy/hooks/job-dispatch-target.sh register <queue> <url> [active=true]
#    ./deploy/hooks/job-dispatch-target.sh list
#    ./deploy/hooks/job-dispatch-target.sh delete <queue>
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
[ -n "$ACTION" ] || { red "usage: $0 register|list|delete ..."; exit 2; }

JOB_POD=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
         | awk '/^job-service-/ && $3=="Running" {print $1; exit}')
[ -n "$JOB_POD" ] || { red "job-service is not running"; exit 1; }

TOKEN=$(kubectl -n "$NS" get secret job-service-secrets \
        -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$TOKEN" ] || { red "no INTERNAL_SERVICE_TOKEN in job-service-secrets"; exit 1; }

case "$ACTION" in
  list)
    kubectl -n "$NS" exec -i "$JOB_POD" -- python - "$TOKEN" <<'PY'
import json, sys, urllib.error, urllib.request
token = sys.argv[1]
req = urllib.request.Request("http://127.0.0.1:8000/internal/dispatch/targets",
                             headers={"X-Internal-Token": token})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(json.dumps(json.loads(resp.read()), ensure_ascii=False, indent=2))
except urllib.error.HTTPError as exc:
    sys.exit(f"job-service refused ({exc.code}): {exc.read().decode(errors='replace')[:300]}")
PY
    ;;
  register)
    QUEUE="${2:?usage: register <queue> <url> [active]}"
    URL="${3:?url required}"
    ACTIVE="${4:-true}"
    info "registering push target for queue '$QUEUE' -> $URL (active=$ACTIVE)"
    kubectl -n "$NS" exec -i "$JOB_POD" -- python - "$TOKEN" "$QUEUE" "$URL" "$ACTIVE" <<'PY'
import json, sys, urllib.error, urllib.request
token, queue, url, active = sys.argv[1:5]
body = json.dumps({"queue": queue, "url": url, "active": active == "true"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/internal/dispatch/targets", data=body,
                             method="POST",
                             headers={"X-Internal-Token": token, "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(json.dumps(json.loads(resp.read()), ensure_ascii=False, indent=2))
except urllib.error.HTTPError as exc:
    sys.exit(f"job-service refused ({exc.code}): {exc.read().decode(errors='replace')[:300]}")
PY
    ok "target registered"
    ;;
  delete)
    QUEUE="${2:?usage: delete <queue>}"
    kubectl -n "$NS" exec -i "$JOB_POD" -- python - "$TOKEN" "$QUEUE" <<'PY'
import sys, urllib.error, urllib.request
token, queue = sys.argv[1:3]
req = urllib.request.Request(f"http://127.0.0.1:8000/internal/dispatch/targets/{queue}",
                             method="DELETE", headers={"X-Internal-Token": token})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(resp.read().decode())
except urllib.error.HTTPError as exc:
    sys.exit(f"job-service refused ({exc.code}): {exc.read().decode(errors='replace')[:300]}")
PY
    ok "target removed"
    ;;
  *)
    red "unknown action '$ACTION' — use register|list|delete"
    exit 2
    ;;
esac
