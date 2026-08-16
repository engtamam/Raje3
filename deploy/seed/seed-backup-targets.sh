#!/usr/bin/env bash
# Register every service as a backup target, and store the token those exports authenticate with.
#
#   ./deploy/seed/seed-backup-targets.sh              # register what is missing, correct drift
#   ./deploy/seed/seed-backup-targets.sh --dry-run    # print what it would do, change nothing
#
# WHY THIS EXISTS. After a clean bring-up the fleet is green: backup-service is deployed, the object
# store has its bucket, BACKUP_KEK is shared to every service. And nothing is backed up. Targets are
# RUNTIME DATA — rows in backup-service — and no script created any. The scheduler then ran against
# an empty target list and reported success on zero targets, which is the most convincing kind of
# success there is. The day postgres is lost, `operations` — the only holder of customers' phone
# numbers in the clear — has no archive, and the first sign of it is the restore attempt.
#
# AND THE TOKEN. A target's `token_ref` is the NAME of an operator secret, never a token. Registered
# empty, every export answers 401 — which backup-service's own values file states, and which no
# script performed. So this stores the shared internal token once, under a name the targets point
# at.
#
# THE ROSTER COMES FROM PRIVACY_TARGETS, and that is deliberate rather than lazy. It is the same
# question asked twice — «every service that holds data» — and two hand-maintained lists of that
# answer drift the moment somebody adds a service to one. `check_deploy_wiring.py` already fails
# when a service serves the erasure endpoint and is missing from that list, so deriving from it
# means the backup roster inherits a gate it would otherwise need its own copy of.
#
# IT CORRECTS RATHER THAN SKIPS, like seed-plans.sh: a target row that disagrees with the roster is
# drift, not somebody's customisation. Nothing here is a customisation — a base_url is either right
# or the service is silently unprotected.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

VALUES="$ROOT/deploy/services/compliance-service.values.yaml"
[ -f "$VALUES" ] || { red "no $VALUES — the roster lives there"; exit 2; }

# `service=url,service=url,…` — read from the file rather than restated here.
ROSTER=$(grep -E '^\s*PRIVACY_TARGETS:' "$VALUES" | sed 's/^[^"]*"//; s/"[[:space:]]*$//')
[ -n "$ROSTER" ] || { red "PRIVACY_TARGETS is empty in $VALUES"; exit 2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^backup-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "backup-service is not running"; exit 1; }

TOKEN_VALUE=$(kubectl -n "$NS" get secret backup-service-secrets \
              -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$TOKEN_VALUE" ] || { red "no INTERNAL_SERVICE_TOKEN in backup-service-secrets"; exit 1; }

# A SIGNED TOKEN, NOT THE INTERNAL ONE — `/api/v1/backup/targets` is a user-tier route holding
# `platform.backup`, and registering what gets archived is administration.
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.seed-backup-key.pem
chmod 600 /tmp/.seed-backup-key.pem
ADMIN=$(python3 -c '
import jwt, time
now = int(time.time())
print(jwt.encode({"sub": "seed-backup-targets", "tenant": "_platform",
                  "caps": ["platform.backup", "platform.secrets"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  "exp": now + 300},
                 open("/tmp/.seed-backup-key.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.seed-backup-key.pem
case "$ADMIN" in
  ey*) : ;;
  *) red "minting failed; got a ${#ADMIN}-character value that is not a JWT"; exit 1 ;;
esac

echo "registering backup targets in backup-service"
# NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS — the heredoc is unquoted so the
# shell would evaluate one before python ever saw it. This has happened mid-seed, from a comment.
kubectl -n "$NS" exec -i "$POD" -- python - "$ADMIN" "$DRY" "$TOKEN_VALUE" "$ROSTER" <<'PY'
import json
import sys
import urllib.error
import urllib.request

admin, dry, token_value, roster = sys.argv[1], sys.argv[2] == "1", sys.argv[3], sys.argv[4]
H = "http://localhost:8000"
SECRET_NAME = "platform-internal"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        H + path, data=data, method=method,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + admin})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode()[:200]}
    except Exception as exc:                                                # noqa: BLE001
        return 0, {"error": str(exc)[:200]}


# ── 1. the token every export authenticates with ────────────────────────────────────────────
# PUT, not POST — POST is 405 on this route, which the values file says and which costs an hour
# to rediscover.
if dry:
    print("  would store operator secret " + SECRET_NAME)
else:
    code, out = call("PUT", "/api/v1/operator/secrets",
                     {"name": SECRET_NAME, "value": token_value})
    if code >= 400:
        print("  ! could not store the secret: " + str(code) + " " + str(out))
        sys.exit(1)
    print("  stored operator secret " + SECRET_NAME)

# ── 2. one target per service ───────────────────────────────────────────────────────────────
wanted = {}
for pair in roster.split(","):
    if "=" not in pair:
        continue
    name, url = pair.split("=", 1)
    name, url = name.strip(), url.strip()
    # NOT ITSELF. backup-service collecting its own archive into its own bucket protects nothing:
    # the failure that loses the data loses the copy with it.
    if not name or not url or name == "backup-service":
        continue
    wanted[name] = url

code, out = call("GET", "/api/v1/backup/targets")
have = {t.get("service"): t for t in (out.get("targets") or [])} if code < 400 else {}

added = fixed = same = 0
for name, url in sorted(wanted.items()):
    current = have.get(name)
    if current and current.get("base_url") == url and current.get("token_ref") == SECRET_NAME \
            and current.get("enabled") is True:
        same += 1
        continue
    if dry:
        print(("  would register " if current is None else "  would correct ") + name)
        continue
    code, out = call("PUT", "/api/v1/backup/targets",
                     {"service": name, "base_url": url, "token_ref": SECRET_NAME,
                      "enabled": True, "note": "seeded from PRIVACY_TARGETS"})
    if code >= 400:
        print("  ! " + name + ": " + str(code) + " " + str(out))
        continue
    if current is None:
        added += 1
    else:
        fixed += 1

print("  targets: " + str(added) + " added, " + str(fixed) + " corrected, "
      + str(same) + " already right, " + str(len(wanted)) + " expected")
# A RUN THAT REGISTERED NOTHING AND FOUND NOTHING IS A FAILURE, not a quiet success — the exact
# shape this script exists to remove.
if not dry and (added + fixed + same) == 0:
    sys.exit(1)
PY
STATUS=$?
[ $STATUS -eq 0 ] && grn "backup targets registered" || red "backup targets: see above"
exit $STATUS
