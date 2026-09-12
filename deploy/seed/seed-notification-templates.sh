#!/usr/bin/env bash
# Seed our own platform-wide in-app/email/sms templates into notification-service.
#
#   ./deploy/seed/seed-notification-templates.sh
#
# WHY A SEED SCRIPT, NOT A MIGRATION — same reason as roles and plans: this content lives on a
# GLOBAL surface (`POST /api/v1/templates`, gated `platform.notifications`, distinct from the
# per-tenant WhatsApp-template capability `notifications.templates` — see
# `services/operations/app/adapters/authz_desk.py`'s own module note on how easy the two are to
# confuse) that a fresh install must have populated before anything calling
# `InAppNotifier.send(template_key=...)` (any of our services) can deliver a single notification —
# an unregistered key fails the send silently, same as any other unreachable/unconfigured peer.
#
# ALWAYS SAFE TO RE-RUN. `POST /api/v1/templates` is a genuine upsert (Template's own key is
# `(key, locale)`) — no drift detection needed here the way seed-plans.sh needs it for a LIVE-
# EDITABLE price list; nobody edits these templates through a console screen, so re-applying the
# file is always the intended, current content, not a possible clobber of someone's manual change.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

HERE="$(cd "$(dirname "$0")" && pwd)"
NS="${NS:-base-services}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }

FILE="$HERE/notification-templates.json"
[ -f "$FILE" ] || { red "no $FILE"; exit 2; }

POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^notification-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "notification-service is not running"; exit 1; }

# A SIGNED TOKEN, NOT THE INTERNAL ONE — same reasoning seed-plans.sh states for its own route:
# /api/v1/templates is a user-tier, capability-gated admin route, not a service-to-service call.
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > "$HERE/.seed-key.pem"
chmod 600 "$HERE/.seed-key.pem"
# THE kid HEADER — see seed-roles.sh's own note; a token minted with none is rejected by every
# JWKS verifier on this fleet.
TOKEN=$(python3 -c '
import base64, hashlib, json, jwt, sys, time
from jwt.algorithms import RSAAlgorithm
now = int(time.time())
private_pem = open(sys.argv[1]).read()
key_obj = RSAAlgorithm(RSAAlgorithm.SHA256).prepare_key(private_pem)
jwk = json.loads(RSAAlgorithm.to_jwk(key_obj))
canonical = json.dumps({"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]},
                       separators=(",", ":"), sort_keys=True).encode("ascii")
kid = base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode("ascii")
print(jwt.encode({"sub": "seed-notification-templates", "tenant": "_platform",
                  "caps": ["platform.notifications"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  "exp": now + 300},
                 private_pem, algorithm="RS256", headers={"kid": kid}), end="")' "$HERE/.seed-key.pem")
rm -f "$HERE/.seed-key.pem"
case "$TOKEN" in
  ey*) : ;;
  *) red "minting failed; got a ${#TOKEN}-character value that is not a JWT"; exit 1 ;;
esac

echo "seeding notification-templates.json into notification-service"
# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS — see
# seed-plans.sh's own identical warning; the heredoc interpolates the file, so the SHELL evaluates
# anything that looks like one before python ever sees it.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" <<PY
import json, sys, urllib.error, urllib.request
token = sys.argv[1]
H = "http://localhost:8000"
LIB = json.loads('''$(cat "$FILE")''')

def call(path, body):
    d = json.dumps(body).encode()
    r = urllib.request.Request(H + path, data=d, method="POST",
                               headers={"Authorization": "Bearer " + token,
                                        "Content-Type": "application/json"})
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

upserted = failed = 0
for tmpl in LIB["templates"]:
    key, category = tmpl["key"], tmpl["category"]
    for locale, content in tmpl["locales"].items():
        s, out = call("/api/v1/templates", {
            "key": key, "locale": locale, "subject": content["subject"],
            "body": content["body"], "category": category,
        })
        if s < 300:
            print("  + " + key + " (" + locale + ") upserted")
            upserted += 1
        else:
            print("  ! " + key + " (" + locale + ") " + str(s) + " " + str(out))
            failed += 1

print("")
print("upserted=" + str(upserted) + " failed=" + str(failed))
sys.exit(1 if failed else 0)
PY
