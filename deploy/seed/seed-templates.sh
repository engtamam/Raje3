#!/usr/bin/env bash
# Register this establishment's WhatsApp library, and submit it for approval.
#
#   ./deploy/seed/seed-templates.sh --tenant shop-123
#   ./deploy/seed/seed-templates.sh --tenant shop-123 --no-submit   # register only
#
# WHAT THIS IS, AND WHAT IT IS NOT. `notification-service` already owns the whole lifecycle: it
# registers a template per (tenant, name, language), submits it to Meta, tracks its status, and
# REFUSES TO SEND an unapproved one. We built none of that and must not. What is ours is the
# CONTENT — the twenty-four texts in three tones — and putting it into their registry for one
# establishment is all this script does.
#
# WHY IT RUNS ON CONNECT (spec §6.6.1). A template at Meta belongs to one WhatsApp Business Account
# and every shop has its own, which is the whole basis of the promise that messages arrive under the
# shop's name. So the library is authored once and approved per establishment — and it goes in the
# moment the account is connected rather than when a message is first needed, because asking then
# means a delay in the exact minute it should have gone out.
#
# ALL SEVENTY-TWO, NOT THE TWENTY-FOUR OF ONE TONE. The tone is in the NAME and a name cannot be
# changed after approval, so submitting one tone would make a later change twenty-four new
# templates and a second review the owner waits through. Submitting all makes it a switch.
#
# IDEMPOTENT, AND IT HAD TO BE MADE SO. The header here once claimed the registry refuses a
# duplicate. It does not: register() UPSERTS and RESETS THE STATUS TO PENDING, so a second run
# over a shop whose library Meta had approved would have silently un-approved all seventy-two and
# stopped every message it sends. Found by running the script twice and reading the counters,
# which is the only reason it is not still true. This script now reads the registry first and
# registers only what is missing.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

HERE="$(cd "$(dirname "$0")" && pwd)"
NS="${NS:-base-services}"

TENANT=""
SUBMIT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --tenant) TENANT="${2:-}"; shift 2 ;;
    --no-submit) SUBMIT=0; shift ;;
    *) shift ;;
  esac
done

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

[ -n "$TENANT" ] || { red "--tenant is required"; exit 2; }
FILE="$HERE/templates.json"
[ -f "$FILE" ] || { red "no $FILE — run: python ci/gen_templates.py"; exit 2; }

POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^notification-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "notification-service is not running"; exit 1; }

# A SIGNED TOKEN, NOT THE INTERNAL ONE. /api/v1/whatsapp/templates is a user-tier route and wants
# `notifications.templates`; the internal token authenticates a service and answers 401 here — a
# 401 that does not say which of the two kinds of credential it wanted, which cost an afternoon
# the first time (see seed-roles.sh).
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.tpl-key.pem
chmod 600 /tmp/.tpl-key.pem
TOKEN=$(TENANT="$TENANT" python3 -c '
import jwt, os, time
now = int(time.time())
print(jwt.encode({"sub": "seed-templates", "tenant": os.environ["TENANT"],
                  "caps": ["notifications.templates"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  # SHORT. It exists for the length of one run.
                  "exp": now + 900},
                 open("/tmp/.tpl-key.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.tpl-key.pem
case "$TOKEN" in
  ey*) : ;;   # a JWT starts `ey` — anything else is a credential of the wrong kind
  *) red "minting failed; got a ${#TOKEN}-character value that is not a JWT"; exit 1 ;;
esac

echo "seeding the WhatsApp library into tenant=$TENANT"
# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS. The heredoc is
# unquoted because it interpolates the library and the flag, so the SHELL evaluates substitution
# inside it before python sees it — three backticked words in a comment ran as commands during a
# real seed once (see seed-roles.sh).
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$SUBMIT" <<PY
import json, sys, urllib.error, urllib.request
token, submit = sys.argv[1], sys.argv[2] == "1"
H = "http://localhost:8000"
LIB = json.loads('''$(cat "$FILE")''')

def call(path, body=None):
    d = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(H + path, data=d, method="POST" if d is not None else "GET",
                               headers={"Authorization": "Bearer " + token})
    if d is not None:
        r.add_header("Content-Type", "application/json")
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160]

# WHAT IS ALREADY THERE, READ FIRST — and this is not an optimisation, it is the whole safety of
# re-running this script.
#
# notification-service's register() UPSERTS: same id, same created date, and STATUS RESET TO
# PENDING. So a second run over an establishment whose library Meta had already approved would
# silently un-approve all seventy-two, and every message that shop sends would stop — because the
# send path correctly refuses a pending template. An operator re-running the seeder to add one new
# text would have taken the shop off the air, and nothing would have said so.
#
# So we read the registry and register only what is missing. Nothing is ever re-registered.
s, listing = call("/api/v1/whatsapp/templates?limit=500")
have = {t.get("name") for t in ((listing or {}).get("templates") or [])} if s < 400 else set()

registered = submitted = existing = failed = 0
for ty in LIB["types"]:
    for tone, text in ty["tones"].items():
        name = ty["name"] + "_" + tone
        # The ordered placeholders the body references. Their ORDER is the contract: Meta numbers
        # variables and does not name them, so a variable that moves between two templates is a
        # send error waiting for its day.
        used = sorted({int(n) for n in __import__("re").findall(r"\\{\\{(\\d+)\\}\\}", text)})
        # TWO ORDERED LISTS, AND THEY ARE NOT THE SAME THING.
        #
        # `variables` are the parameter NAMES the send substitutes by, whose order maps each to a
        # position. `examples` are the example VALUES Meta requires at creation — and a name is
        # not a valid example: their review rejects placeholder-looking ones.
        #
        # We sent the values in the names field for a day. It was correct against the older port,
        # which had one list, and wrong the moment it became two.
        variables = [LIB["variables"][str(i)]["name"] for i in used]
        examples = [LIB["variables"][str(i)]["example"] for i in used]

        if name in have:
            existing += 1
            continue

        s, out = call("/api/v1/whatsapp/templates", {
            "name": name,
            # ARABIC ONLY TODAY, and the language is part of the identity — adding English later is
            # a second row under the same name, not a redesign (spec 8.4.1).
            "language": "ar",
            "category": ty["category"],
            "body": text,
            "variables": variables,
            "examples": examples,
            # WHICH BLANK IS WHOSE, AND IT TRAVELS OR IT IS NOT TRUE (ط-4). The library validates
            # `fills` and every reader downstream branches on it — the campaign screen to know
            # which blanks to draw, the preview to know what to substitute, `sanitise_owner_text`
            # to know whether a free line is even wanted. The seeder never sent the field, so
            # every template arrived declaring nothing: each blank resolved to «system», the
            # owner's typed value reached no slot, and the preview rendered «…» where his
            # discount should have been.
            "fills": ty.get("fills") or [],
        })
        if s == 201:
            registered += 1
        else:
            print("  ! " + name + " register " + str(s) + " " + str(out))
            failed += 1
            continue

        if submit:
            s2, out2 = call("/api/v1/whatsapp/templates/" + name + "/ar/submit")
            if s2 < 400:
                submitted += 1
            else:
                # NOT fatal to the run. A rate limit at template forty must not lose the other
                # thirty-two: the registration stands, and a later pass submits what is pending.
                print("  ~ " + name + " submit " + str(s2) + " " + str(out2))

print("")
print("registered=" + str(registered) + " existing=" + str(existing)
      + " submitted=" + str(submitted) + " failed=" + str(failed))
sys.exit(1 if failed else 0)
PY
