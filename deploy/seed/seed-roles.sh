#!/usr/bin/env bash
# Seed the roles into authz-service — ours once, an establishment's per tenant.
#
#   ./deploy/seed/seed-roles.sh                    # our operator roles, under the platform tenant
#   ./deploy/seed/seed-roles.sh --tenant shop-123  # that establishment's roles
#   ./deploy/seed/seed-roles.sh --strict-skip      # never touch a role that already exists
#
# WHY A SCRIPT AND NOT A MIGRATION. Roles are content: somebody wants a new one on a Tuesday
# afternoon because a shop asked. A migration makes that a deploy, and content that needs a deploy
# is content nobody edits. This is idempotent, so running it again after adding a role to the JSON
# adds the role and leaves every edit an operator has made to the others.
#
# AND IT NEVER OVERWRITES. A role that already exists is skipped, loudly. The alternative — force
# every role back to the file on every run — would silently undo a customisation somebody made
# through the console, which is the same failure as re-applying a seed on every boot.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

TENANT=""
STRICT=0
for arg in "$@"; do
  case "$arg" in
    --strict-skip) STRICT=1 ;;
  esac
done
[ "${1:-}" = "--tenant" ] && TENANT="${2:-}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
yel(){ printf '  \e[33m⚠ %s\e[0m\n' "$*"; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

if [ -n "$TENANT" ]; then
  FILE="$HERE/roles.json"
  SCOPE="$TENANT"
else
  FILE="$HERE/operator-roles.json"
  # The reserved tenant our own roles live under — the same one operations uses for sectors and
  # templates. One reserved name across the product rather than a different one per service.
  SCOPE="_platform"
fi
[ -f "$FILE" ] || { red "no $FILE"; exit 2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^authz-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "authz-service is not running"; exit 1; }
# A SIGNED TOKEN, NOT THE INTERNAL ONE. /api/v1/roles is a user-tier route: the internal token
# authenticates a service, and this is administration. The first version passed the internal token
# and every call answered 401 — correctly, and unhelpfully, because a 401 does not say which of the
# two kinds of credential it wanted.
#
# It needs `platform.authz`, which is exactly the capability the escalation policy exempts from the
# tenant denylist. Seeding a role that grants authz.manage is a thing only a platform operator may
# do, and that is the right shape rather than a workaround.
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.seed-key.pem
chmod 600 /tmp/.seed-key.pem
TOKEN=$(SCOPE="$SCOPE" python3 -c '
import jwt, os, time
now = int(time.time())
print(jwt.encode({"sub": "seed-roles", "tenant": os.environ["SCOPE"],
                  "caps": ["platform.authz", "authz.manage"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  # SHORT. This token can create a role carrying any capability; it exists for the
                  # length of one seed run and not a minute longer.
                  "exp": now + 300},
                 open("/tmp/.seed-key.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.seed-key.pem
case "$TOKEN" in
  ey*) : ;;   # a JWT starts `ey` — anything else is a credential of the wrong kind
  *) red "minting failed; got a ${#TOKEN}-character value that is not a JWT"; exit 1 ;;
esac

echo "seeding $(basename "$FILE") into tenant=$SCOPE"
# The heredoc IS the stdin. An earlier version appended `< /dev/null` to stop the loop consuming
# it — which silently replaced the script with nothing, and the command exited 0 having run an
# empty program. It printed the header and did the work of a comment.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$SCOPE" <<PY
import json, sys, urllib.error, urllib.request
token, scope = sys.argv[1], sys.argv[2]
H = "http://localhost:8000"
roles = json.loads('''$(cat "$FILE")''')["roles"]

# NO BACKTICKS AND NO $( ) ANYWHERE BELOW THIS LINE, INCLUDING IN COMMENTS.
#
# This heredoc is unquoted — it has to be, because it interpolates the JSON file and the flag — so
# the SHELL evaluates command substitution inside it before python ever sees it. Three backticked
# words in a comment ran as commands during a real seed and printed "platform.loyalty: command not
# found" in the middle of the output.
#
# And the replacement comment demonstrated it a second time: it named a substitution as an
# EXAMPLE of the danger, and the shell ran that too. There is no safe way to write one down
# in here — so the rule is absolute rather than illustrated.
def call(path, body=None, method=None):
    d = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(H + path, data=d, method=method or ("POST" if d else "GET"),
                               headers={"Authorization": "Bearer " + token})
    if d:
        r.add_header("Content-Type", "application/json")
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]

s, existing = call("/api/v1/roles")
# The whole row, not just the name: deciding what a role is MISSING needs what it currently holds.
have = {r.get("name"): r for r in (existing.get("roles") or [])} if s < 400 else {}
# Set by --strict-skip. Off by default, because the common case is a new service shipping.
STRICT_SKIP = "$STRICT" == "1"

created = updated = skipped = failed = 0
for role in roles:
    name = role["name"]
    if name in have:
        # EXISTS. Forcing it back to the file would undo whatever an operator changed through the
        # console — the same failure as re-applying a seed on every boot. So nothing is removed,
        # ever.
        #
        # BUT A MISSING CAPABILITY IS NOT A CUSTOMISATION. When a NEW SERVICE ships, its
        # capabilities are added to this file, and "left alone" meant they never reached the
        # cluster: platform.loyalty and platform.insights were declared, enforced at their
        # routes, and held by nobody. The first symptom would have been a support engineer getting
        # a 403 in the middle of an incident.
        #
        # So the two cases are separated. Additive by default — grant what the file has and the
        # role lacks, remove nothing — and --strict-skip for the operator who wants the old
        # behaviour during an investigation.
        current = set(have[name].get("capabilities") or [])
        wanted = set(role["capabilities"])
        missing = sorted(wanted - current)
        if not missing or STRICT_SKIP:
            print(f"  ~ {name:20} exists, left alone ({len(role['capabilities'])} caps in file)")
            skipped += 1
            continue
        s, out = call(f"/api/v1/roles/{have[name]['id']}",
                      {"capabilities": sorted(current | wanted)}, method="PUT")
        if s < 400:
            print(f"  ^ {name:20} + {', '.join(missing)}")
            updated += 1
        else:
            print(f"  ! {name:20} {s} {out}")
            failed += 1
        continue
    s, out = call("/api/v1/roles", {"name": name,
                                    "description": role.get("description", ""),
                                    "capabilities": role["capabilities"]})
    if s < 400:
        print(f"  + {name:20} {len(role['capabilities'])} caps")
        created += 1
    else:
        print(f"  ! {name:20} {s} {out}")
        failed += 1
print(f"\ncreated={created} skipped={skipped} failed={failed}")
sys.exit(1 if failed else 0)
PY
