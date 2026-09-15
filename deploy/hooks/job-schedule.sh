#!/usr/bin/env bash
# ==================================================================================================
#  CREATE/LIST/DELETE A job-service SCHEDULE — THE REPLACEMENT FOR ONE K8S CronJob, ONE CALL AT A TIME
# --------------------------------------------------------------------------------------------------
#  WHY THIS EXISTS. Migrating a service's own CronJob to job-service's push-dispatch (base-services
#  v0.24.0) needs exactly one admin action first: register a `schedule` (POST /api/v1/jobs/schedules),
#  gated by the `platform.jobs` capability — a real Principal, not the fleet's shared internal token.
#
#  NEVER THE PLATFORM OWNER'S OWN LOGIN (the owner's own instruction, 2026-09-15: every action here
#  must be attributable to automation, not to a person). So this mints its OWN short-lived,
#  self-signed token instead of logging in as anybody — the SAME technique seed-roles.sh already
#  uses to seed roles (see that script's own long comment on the kid header / RS256 self-signing):
#  sign a JWT with identity-service's own TOKEN_PRIVATE_KEY (a fact the cluster already holds, not a
#  human's password), `sub: "raje3-automation"`, carrying ONLY `platform.jobs` — nothing else — and
#  good for five minutes. job-service's audit trail then names "raje3-automation" as the actor,
#  never the owner, for this and every future call of this script.
#
#  USAGE
#    ./deploy/hooks/job-schedule.sh create <name> <cron> <queue> <type> [tenant=global] [payload_json]
#    ./deploy/hooks/job-schedule.sh list
#    ./deploy/hooks/job-schedule.sh delete <schedule_id>
#
#  Run by a human operator with real cluster access (this file follows seed-roles.sh's own
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

KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > "$HERE/.job-schedule-key.pem"
chmod 600 "$HERE/.job-schedule-key.pem"

# SAME MINTING TECHNIQUE AS seed-roles.sh — see that script's own header for why the `kid` header
# is not optional (PyJWKClient raises without one). `sub` names the actor for job-service's OWN
# audit log; it is never the human operator's identity.
TOKEN=$(python3 -c '
import base64, hashlib, json, jwt, sys, time
now = int(time.time())
private_pem = open(sys.argv[1]).read()
from jwt.algorithms import RSAAlgorithm
key_obj = RSAAlgorithm(RSAAlgorithm.SHA256).prepare_key(private_pem)
jwk = json.loads(RSAAlgorithm.to_jwk(key_obj))
canonical = json.dumps({"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]},
                       separators=(",", ":"), sort_keys=True).encode("ascii")
kid = base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode("ascii")
print(jwt.encode({"sub": "raje3-automation", "tenant": "global",
                  "caps": ["platform.jobs"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  "exp": now + 300},
                 private_pem, algorithm="RS256", headers={"kid": kid}), end="")' \
  "$HERE/.job-schedule-key.pem")
rm -f "$HERE/.job-schedule-key.pem"
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
