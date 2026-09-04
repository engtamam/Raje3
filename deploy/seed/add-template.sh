#!/usr/bin/env bash
# Add ONE custom template for one establishment — the end of the request journey (spec §6.7).
#
#   ./deploy/seed/add-template.sh --tenant shop-123 --name cst_eid_greeting \
#       --category MARKETING --body 'كل عام وأنتم بخير {{1}}، من {{2}}.'
#
# WHERE THIS SITS. An owner who wants a message the library does not cover writes it in his own
# words and it becomes a support ticket. `ticket-service` already owns that queue entirely —
# create, reply, assign, status, history — so there is no queue to build. What is missing is the
# LAST STEP: turning the rewrite we approved into a registered template on that establishment's own
# WhatsApp account. This is that step, and nothing more.
#
# THE REVIEW BEFORE META'S REVIEW IS THE POINT (§8.4.1). The owner's text never goes to Meta as he
# wrote it: we rewrite it with proper variables and the right category first. A shop submitting its
# own words collects rejections it cannot interpret, and repeated rejections damage the quality
# rating of a number we are responsible for — a cost paid by every other establishment on the
# product, none of whom did anything.
#
# WHAT IT REFUSES, and each refusal is a Meta rejection caught here instead of hours later against
# a name that is then burned:
#   a gap in the variable numbering
#   a variable above {{4}}, which is not in our contract
#   a category outside Meta's three
#   a name that already exists for this tenant — see seed-templates.sh on why re-registering is
#   never harmless
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

NS="${NS:-base-services}"

TENANT=""; NAME=""; CATEGORY=""; BODY=""; SUBMIT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --tenant)   TENANT="${2:-}";   shift 2 ;;
    --name)     NAME="${2:-}";     shift 2 ;;
    --category) CATEGORY="${2:-}"; shift 2 ;;
    --body)     BODY="${2:-}";     shift 2 ;;
    --no-submit) SUBMIT=0; shift ;;
    *) shift ;;
  esac
done

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }

[ -n "$TENANT" ]   || { red "--tenant is required";   exit 2; }
[ -n "$NAME" ]     || { red "--name is required";     exit 2; }
[ -n "$CATEGORY" ] || { red "--category is required (UTILITY | MARKETING | AUTHENTICATION)"; exit 2; }
[ -n "$BODY" ]     || { red "--body is required";     exit 2; }

# A CUSTOM TEMPLATE IS NAMED FOR WHAT IT IS. `cst_` keeps it out of the library's five class
# prefixes, so a glance at Meta's flat list says which templates are ours and which one shop asked
# for — and so a future library text can never collide with a name one establishment already holds.
case "$NAME" in
  cst_*) : ;;
  *) red "a custom template's name must start with cst_ — the library owns the other prefixes"; exit 2 ;;
esac

POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^notification-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "notification-service is not running"; exit 1; }

KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > "$HERE/.cst-key.pem"
chmod 600 "$HERE/.cst-key.pem"
# THE kid HEADER — see seed-roles.sh's own note. A token minted with none is rejected by every
# JWKS verifier on this fleet; this thumbprints the SAME key it signs with (RFC 7638, identical to
# identity-service's own `public_jwk`), so it works across a rotation with no code change.
TOKEN=$(TENANT="$TENANT" python3 -c '
import base64, hashlib, json, jwt, os, sys, time
from jwt.algorithms import RSAAlgorithm
now = int(time.time())
private_pem = open(sys.argv[1]).read()
key_obj = RSAAlgorithm(RSAAlgorithm.SHA256).prepare_key(private_pem)
jwk = json.loads(RSAAlgorithm.to_jwk(key_obj))
canonical = json.dumps({"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]},
                       separators=(",", ":"), sort_keys=True).encode("ascii")
kid = base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode("ascii")
print(jwt.encode({"sub": "add-template", "tenant": os.environ["TENANT"],
                  "caps": ["notifications.templates"],
                  "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 300},
                 private_pem, algorithm="RS256", headers={"kid": kid}), end="")' "$HERE/.cst-key.pem")
rm -f "$HERE/.cst-key.pem"
case "$TOKEN" in
  ey*) : ;;
  *) red "minting failed; got a ${#TOKEN}-character value that is not a JWT"; exit 1 ;;
esac

# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS — the heredoc is
# unquoted so the shell evaluates them before python sees it (see seed-roles.sh).
# THE OWNER'S TEXT TRAVELS AS AN ARGUMENT, never interpolated into the program. `kubectl exec` has
# no --env, and putting a stranger's sentence inside the heredoc would put it inside a Python
# source file — one quote in his greeting ends the string and everything after it is code. He is
# writing a message, not a program.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$SUBMIT" "$NAME" "$CATEGORY" "$BODY" <<'PY'
import json, re, sys, urllib.error, urllib.request

token, submit = sys.argv[1], sys.argv[2] == "1"
name, category, body = sys.argv[3], sys.argv[4].upper(), sys.argv[5]
H = "http://localhost:8000"

# TWO LISTS PER TEMPLATE, AND THEY ARE NOT THE SAME THING. NAME is the parameter's name — what a
# send substitutes by, ordered so each maps to a position. EXAMPLE is a value Meta requires at
# creation, and a name is not a valid one: their review rejects placeholder-looking examples.
NAME = {1: "customer_name", 2: "establishment", 3: "service", 4: "detail"}
EXAMPLE = {1: "محمد", 2: "مغسلة النخيل", 3: "غيار الزيت", 4: "1234"}

def call(path, payload=None):
    d = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(H + path, data=d, method="POST" if d is not None else "GET",
                               headers={"Authorization": "Bearer " + token})
    if d is not None:
        r.add_header("Content-Type", "application/json")
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]

if category not in ("UTILITY", "MARKETING", "AUTHENTICATION"):
    print("  x category must be one of Meta's three, not " + category)
    sys.exit(2)

used = sorted({int(n) for n in re.findall(r"\{\{(\d+)\}\}", body)})
if used and used != list(range(1, len(used) + 1)):
    print("  x variables " + str(used) + " have a gap — Meta rejects the submission hours later, "
          "against a name that cannot then be reused or renamed")
    sys.exit(2)
if used and used[-1] > 4:
    print("  x variable " + str(used[-1]) + " is outside our four-variable contract")
    sys.exit(2)

s, listing = call("/api/v1/whatsapp/templates?limit=500")
have = {t.get("name") for t in ((listing or {}).get("templates") or [])} if s < 400 else set()
if name in have:
    # Re-registering resets the status to pending and takes an approved template off the air.
    print("  x " + name + " already exists for this establishment — nothing was changed")
    sys.exit(2)

s, out = call("/api/v1/whatsapp/templates", {
    "name": name, "language": "ar", "category": category, "body": body,
    "variables": [NAME[i] for i in used],
    "examples": [EXAMPLE[i] for i in used],
})
if s != 201:
    print("  x register " + str(s) + " " + str(out))
    sys.exit(1)
print("  + registered " + name + " with " + str(len(used)) + " variables")

if submit:
    s2, out2 = call("/api/v1/whatsapp/templates/" + name + "/ar/submit")
    if s2 < 400:
        print("  + submitted for approval")
    else:
        # The registration stands. A later pass submits what is still pending, so a rate limit
        # here costs a retry rather than the template.
        print("  ~ submit " + str(s2) + " " + str(out2))
PY
