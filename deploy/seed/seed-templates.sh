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

# THE RATING APP'S OWN BUTTON — empty is the correct default, same "not-yet-wired knob fails
# closed rather than guessing" posture NOTIFICATION_INTERACTIVE_SEND_PATH's own comment states.
# notification-service's register() has always accepted a `flow_button` (WaTemplateIn.flow_button
# — {"flow_id"|"flow_name","text",...}), and this script has never sent one for
# svc_visit_confirmation_rating, so every copy of that template ever registered was plain text
# with no tappable Flow button — a customer could read "قيّم زيارتك" but never open the form,
# whatever `_rating_eligible` and the sender's own flow_token wiring answer. A `flow_id` only
# exists once a real Flow is built and published in Meta's Flow Builder for this WABA (external —
# nothing in this repo can create one); set RATING_FLOW_ID to it once that exists and this script
# starts declaring the button. Until then this is a documented no-op, not a silent one.
RATING_FLOW_ID="${RATING_FLOW_ID:-}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

[ -n "$TENANT" ] || { red "--tenant is required"; exit 2; }
# PARSED FRESH FROM THE CURATED SEED, no stored intermediate file (2026-09-13) — this used to read
# a checked-in deploy/seed/templates.json regenerated from a markdown specification that could be
# one edit behind services/operations/data/templates.seed.json, the file operations actually
# submits. A temp file built straight off the seed on every run cannot go stale between an edit
# and this script noticing.
FILE="$(mktemp)"
trap 'rm -f "$FILE"' EXIT
python3 "$HERE/../../ci/gen_templates.py" --emit > "$FILE" || { red "the curated seed failed its own checks — see the error above"; exit 2; }

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
printf '%s\n' "$KEY" > "$HERE/.tpl-key.pem"
chmod 600 "$HERE/.tpl-key.pem"
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
print(jwt.encode({"sub": "seed-templates", "tenant": os.environ["TENANT"],
                  "caps": ["notifications.templates"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  # SHORT. It exists for the length of one run.
                  "exp": now + 900},
                 private_pem, algorithm="RS256", headers={"kid": kid}), end="")' "$HERE/.tpl-key.pem")
rm -f "$HERE/.tpl-key.pem"
case "$TOKEN" in
  ey*) : ;;   # a JWT starts `ey` — anything else is a credential of the wrong kind
  *) red "minting failed; got a ${#TOKEN}-character value that is not a JWT"; exit 1 ;;
esac

echo "seeding the WhatsApp library into tenant=$TENANT"
# THE HEREDOC IS QUOTED (<<'PY') SO THE SHELL EXPANDS NOTHING INSIDE IT AT ALL — this used to be
# unquoted specifically to interpolate the library via `$(cat "$FILE")`, and that same unquoting
# made bash re-scan the heredoc's OWN PYTHON SOURCE for backticks too. Three backticked words in a
# comment ran as commands during a real seed once (the note this replaced said so), and
# deploy/seed/seed-plans.sh hit the identical failure again 2026-09-14 from ITS OWN comments —
# documented as a danger twice and fixed neither time. Fixed at the root here instead: the file
# now travels as base64 in an argv value the shell never parses as text, so the heredoc can be
# quoted and this whole class of bug is gone, not patched around with a warning comment again.
FILE_B64=$(base64 -w0 "$FILE" 2>/dev/null || base64 "$FILE" | tr -d '\n')
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$SUBMIT" "$RATING_FLOW_ID" "$FILE_B64" <<'PY'
import base64, json, sys, urllib.error, urllib.request
token, submit, rating_flow_id, file_b64 = sys.argv[1], sys.argv[2] == "1", sys.argv[3], sys.argv[4]
H = "http://localhost:8000"
LIB = json.loads(base64.b64decode(file_b64))

# THE TWO BLANKS THAT CARRY AN ADDRESS. Named and exampled by what they ARE rather than by where
# they sit, because they sit somewhere different in every text. See the substitution below.
ADDRESS_SLOTS = {
    "invite": {"name": "invite_line",
               "example": "ولك عندنا مزايا خاصة — فعّلها من هنا: https://my.raje3.sa/p/nakheel.sub_rj7k2m/allow"},
    "stop_link": {"name": "stop_link",
                  "example": "https://my.raje3.sa/p/nakheel.sub_rj7k2m/stop"},
}

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
        # AND THE ADDRESS SLOT IS NAMED BY ITS FILL, NOT BY ITS POSITION.
        #
        # Every other blank means the same thing wherever it lands, so a table keyed by number is
        # honest for them. The last blank is not: it is the invitation on a utility text and the
        # one-tap stop on a marketing one, and it lands on slot 3 in a visit confirmation and on
        # slot 6 in an offer. Keyed by number alone it would be submitted to Meta's reviewer under
        # the name «service» with «قص شعر» as its example — a human reads that, sees a service
        # name where a link belongs, and the whole library is refused against names that then
        # cannot be reused.
        fills = list(ty.get("fills") or [])
        by_pos = {n: (fills[i] if i < len(fills) else "") for i, n in enumerate(used)}
        variables, examples = [], []
        for i in used:
            fill = by_pos.get(i, "")
            if fill in ADDRESS_SLOTS:
                variables.append(ADDRESS_SLOTS[fill]["name"])
                examples.append(ADDRESS_SLOTS[fill]["example"])
            else:
                variables.append(LIB["variables"][str(i)]["name"])
                examples.append(LIB["variables"][str(i)]["example"])

        if name in have:
            existing += 1
            continue

        body = {
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
        }
        # THE RATING APP'S OWN BUTTON — declared ONLY on its own template, and only once a real
        # Flow exists to point it at. Every other template must not grow this key: notification-
        # service's register() compares `flow_button` byte-for-byte to decide whether an unchanged
        # re-run may skip re-pending an already-approved template, so sending `{}` everywhere is
        # correct — sending a non-empty value on the wrong template would submit a button Meta has
        # nothing to attach it to.
        if ty["name"] == "svc_visit_confirmation_rating" and rating_flow_id:
            body["flow_button"] = {"flow_id": rating_flow_id, "text": "قيّم زيارتك"}
        s, out = call("/api/v1/whatsapp/templates", body)
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
