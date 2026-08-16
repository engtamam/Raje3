#!/usr/bin/env bash
# Prove the message quota on the cluster — against the running billing-service.
#
#   ./deploy/prove-quota.sh
#
# The unit tests prove what reminders DOES: consume before the send, the send's own key, release on
# failure. They cannot prove what billing does with those calls, because the fake is ours. This
# asks the real service the three questions that decide whether the cap is a wall or a suggestion:
#
#   spend one, retry with the same key   -> one unit gone, not two
#   spend to the limit                   -> refused, and refused with a reason
#   release                              -> the unit comes back and can be spent again
#
# It runs on a throwaway tenant subscribed to a small plan, so nothing real is touched.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"

NS="${NS:-base-services}"

red(){ printf '  \e[31m%s\e[0m\n' "$*" >&2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^billing-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "billing-service is not running"; exit 1; }

KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.pq-key.pem
chmod 600 /tmp/.pq-key.pem
TOKEN=$(python3 -c '
import jwt, time
now = int(time.time())
print(jwt.encode({"sub": "prove-quota", "tenant": "_platform",
                  "caps": ["platform.billing", "billing.manage"],
                  "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 600},
                 open("/tmp/.pq-key.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.pq-key.pem

INTERNAL=$(kubectl -n "$NS" get secret billing-service-secrets \
           -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$INTERNAL" ] || { red "no INTERNAL_SERVICE_TOKEN"; exit 1; }

# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$INTERNAL" <<PY
import json, sys, time, urllib.error, urllib.request
token, internal = sys.argv[1], sys.argv[2]
H = "http://localhost:8000"
KEY = "messages.monthly"
LIMIT = 3

def call(path, body=None, method=None, internal_call=False):
    d = json.dumps(body).encode() if body is not None else None
    headers = ({"X-Internal-Token": internal} if internal_call
               else {"Authorization": "Bearer " + token})
    r = urllib.request.Request(H + path, data=d, method=method or ("POST" if d else "GET"),
                               headers=headers)
    if d:
        r.add_header("Content-Type", "application/json")
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"_body": e.read().decode()[:200]}

stamp = str(int(time.time()))
# A PLAN OF ITS OWN, with a limit of 3 — small enough to exhaust in three calls, and unlisted so
# it can never be sold to anybody. Reusing a real plan would mean sending 1000 requests to prove
# a wall, or trusting that the wall at 1000 behaves like the wall at 3.
s, plan = call("/api/v1/billing/plans", {
    "name": "quota-proof-" + stamp,
    "prices": [{"interval": "month", "amount_minor": 0, "currency": "SAR", "type": "flat"}],
    "limits": {KEY: {"kind": "counter", "limit": LIMIT, "period": "billing_period",
                     "overage": "block"}}})
if s >= 400:
    print("  ! could not create the proof plan:", s, plan)
    sys.exit(1)
# UNLISTED, BUT STILL ACTIVE. The first version set active=False here and the very next call —
# subscribing to it — answered 404, correctly: active=False means nobody NEW may subscribe, which
# is exactly what this script was about to do. Retiring the plan is a thing to do AFTER the proof,
# not before it, and the two switches are separate for precisely this reason.
call("/api/v1/billing/plans/" + plan["id"] + "/availability", {"listed": False})

tenant = "prove-quota-" + stamp
s, sub = call("/api/v1/billing/subscriptions", {"plan_id": plan["id"], "tenant": tenant})
if s >= 400:
    print("  ! could not subscribe:", s, sub)
    sys.exit(1)

# EVERY RUN USES KEYS NOBODY HAS USED BEFORE, and the reason is a finding rather than hygiene.
#
# This script used the literal keys "rem_1".."rem_5" and passed. Days later, against a fresh
# tenant, every assertion about the cap failed while billing reported each consume as successful —
# because the idempotency record is scoped GLOBALLY rather than per tenant, so the second shop to
# use "rem_1" gets the first shop's replayed answer and its own counter never moves.
#
# Escalated. Until it is fixed, a proof that reuses a fixed key tests the deduplication of a
# previous run, and a proof that reuses a fixed key ACROSS tenants tests nothing at all.
RUN = "q" + stamp + "_"

def consume(key):
    return call("/internal/billing/usage/consume",
                {"tenant": tenant, "key": KEY, "amount": 1, "idempotency_key": RUN + key},
                internal_call=True)

def release(key):
    return call("/internal/billing/usage/release",
                {"tenant": tenant, "key": KEY, "amount": 1, "idempotency_key": RUN + key},
                internal_call=True)

def used():
    s, out = call("/internal/billing/entitlements/check?tenant=" + tenant + "&key=" + KEY
                  + "&amount=0", internal_call=True)
    return int(out.get("current", -1))

fails = []

# 1 — one send, one unit.
consume("rem_1")
if used() != 1:
    fails.append("a single send spent " + str(used()) + ", not 1")

# 2 — THE EXPENSIVE ONE. The bus is at-least-once; a redelivery must spend nothing.
consume("rem_1")
consume("rem_1")
if used() != 1:
    fails.append("three calls with ONE key spent " + str(used()) + " units — a redelivery is "
                 "charging the shop again")
else:
    print("  ok a retry with the same key spends nothing more")

# 3 — the wall. Two more fills it; the fourth must be refused.
consume("rem_2")
consume("rem_3")
s, out = consume("rem_4")
if out.get("allowed"):
    fails.append("the send past the limit was ALLOWED — the cap is a suggestion")
else:
    print("  ok the send past the limit is refused (" + str(out.get("error")) + ")")
if used() != LIMIT:
    fails.append("a refused send still moved the counter to " + str(used()))

# 4 — the release gives it back, and the unit can be spent again.
release("rem_3")
if used() != LIMIT - 1:
    fails.append("a release left the counter at " + str(used()) + ", not " + str(LIMIT - 1))
else:
    print("  ok a release returns the unit")
s, out = consume("rem_5")
if not out.get("allowed"):
    fails.append("the returned unit could not be spent again — a failed send permanently costs "
                 "the shop a message")
else:
    print("  ok the returned unit can be spent again")

# Retired only now that the proof is done: nobody new may subscribe to it ever again.
call("/api/v1/billing/plans/" + plan["id"] + "/availability", {"active": False})

print("")
for f in fails:
    print("  ! " + f)
if not fails:
    print("  the message cap is enforced, idempotent, and refundable")
sys.exit(1 if fails else 0)
PY
