#!/usr/bin/env bash
# Prove the message PACK on the cluster — against the running billing-service.
#
#   ./deploy/prove-packs.sh
#
# THE CLAIM BEING TESTED, which the design rests on entirely: a message pack needs no new model,
# no second purchase path and no branch in the sending code, because an entitlement is the UNION
# of every billable subscription — so a pack is just a subscription with interval `once` carrying
# only messages.monthly, and its messages ADD to the plan's with no arithmetic of ours.
#
# That is documented behaviour, and documented behaviour is a claim until it is asked. If the
# union does not add, the whole pack design is wrong — and it is far better to learn that here
# than from an owner who paid 50 riyals for messages that never arrived.
#
#   a plan of 2, exhausted        -> the next send is refused
#   buy a pack of 3               -> the limit becomes 5 WITHOUT anyone adding anything
#   send again                    -> it goes
#
# Nothing real is touched: both products are created here, unlisted, and retired at the end.
set -uo pipefail

NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

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
print(jwt.encode({"sub": "prove-packs", "tenant": "_platform",
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
PLAN_LIMIT, PACK_LIMIT = 2, 3

def make_product(name, limit, interval):
    s, p = call("/api/v1/billing/plans", {
        "name": name,
        "prices": [{"interval": interval, "amount_minor": 0, "currency": "SAR", "type": "flat"}],
        "limits": {KEY: {"kind": "counter", "limit": limit, "period": "billing_period",
                         "overage": "block"}}})
    if s >= 400:
        print("  ! could not create " + name + ":", s, p)
        sys.exit(1)
    call("/api/v1/billing/plans/" + p["id"] + "/availability", {"listed": False})
    return p

plan = make_product("pack-proof-plan-" + stamp, PLAN_LIMIT, "month")
# INTERVAL once IS WHAT MAKES IT A PACK. It is bought, it contributes, and it never renews —
# which is also exactly what our monthly-manual decision needs from every other subscription.
pack = make_product("pack-proof-pack-" + stamp, PACK_LIMIT, "once")

tenant = "prove-pack-" + stamp
s, sub = call("/api/v1/billing/subscriptions", {"plan_id": plan["id"], "tenant": tenant})
if s >= 400:
    print("  ! could not subscribe:", s, sub)
    sys.exit(1)

# Run-unique, because the idempotency record is scoped globally rather than per tenant — a fixed
# key tests a previous run's deduplication instead of this one's cap. Escalated; see prove-quota.sh.
RUN = "p" + stamp + "_"

def consume(k):
    return call("/internal/billing/usage/consume",
                {"tenant": tenant, "key": KEY, "amount": 1, "idempotency_key": RUN + k},
                internal_call=True)

def limit_now():
    s, out = call("/internal/billing/entitlements/check?tenant=" + tenant + "&key=" + KEY
                  + "&amount=0", internal_call=True)
    return out.get("limit"), int(out.get("current", -1))

fails = []

lim, _ = limit_now()
if lim != PLAN_LIMIT:
    fails.append("the plan alone reports a limit of " + str(lim) + ", not " + str(PLAN_LIMIT))

# Exhaust it.
consume("m_1")
consume("m_2")
s, out = consume("m_3")
if out.get("allowed"):
    fails.append("the send past the plan limit was allowed before any pack was bought")
else:
    print("  ok the plan alone runs out at " + str(PLAN_LIMIT))

# BUY THE PACK. Nothing else happens: no top-up, no counter reset, no arithmetic.
# THE INTERVAL IS THE SUBSCRIPTION'S, NOT THE PLAN'S — and this is the finding that matters for
# the purchase path. The plan's PRICE says once, but subscribe() takes its own interval and
# defaults it to month. Sending nothing here produced a monthly pack: it carried a real period
# end, so it would have lapsed, and the renewal sweep would have re-charged 50 riyals every month
# for a one-time purchase.
#
# So whatever buys a pack must send interval="once" explicitly. The plan row does not carry it.
s, psub = call("/api/v1/billing/subscriptions",
               {"plan_id": pack["id"], "tenant": tenant, "interval": "once"})
if s >= 400:
    fails.append("could not buy the pack: " + str(s) + " " + str(psub))

lim, cur = limit_now()
if lim != PLAN_LIMIT + PACK_LIMIT:
    fails.append("THE UNION DOES NOT ADD: after buying a pack of " + str(PACK_LIMIT)
                 + " on a plan of " + str(PLAN_LIMIT) + " the limit is " + str(lim)
                 + ". The whole pack design assumes it sums — this is a redesign.")
else:
    print("  ok the pack ADDS to the plan (" + str(lim) + "), with no arithmetic of ours")

# AND THE COUNTER IS NOT RESET. He spent 2; buying more messages must not forgive the 2 he used,
# or a pack becomes a way to reset the month rather than to extend it.
if cur != PLAN_LIMIT:
    fails.append("buying a pack reset the usage counter to " + str(cur)
                 + " — a pack must extend the month, not forgive it")
else:
    print("  ok what he already sent is still counted")

s, out = consume("m_4")
if not out.get("allowed"):
    fails.append("the send AFTER buying the pack was still refused — he paid for messages that "
                 "did not arrive")
else:
    print("  ok the very next send goes through")

# ── AND THE PACK MUST STILL BE THERE TOMORROW ────────────────────────────────────────────────
#
# The first version of this proof passed while the pack was broken. It bought, checked, and
# finished — all within seconds — and a pack bought under v0.13.6 was dropped as period_lapsed the
# next day, because interval "once" produced a period end of NOW and the resolver lapses a period
# that has passed. A shop pays 50 riyals, sends for a day, and the balance quietly reverts.
#
# We cannot wait a day here. What we CAN do is assert the property that makes lapsing impossible,
# which is what v0.13.7 changed: a one-time purchase carries a ZERO period end, so the resolver's
# "no period end means nothing to lapse" rule applies and the renewal sweep skips it.
#
# Checking the STATE rather than the elapsed time is the general answer whenever a proof cannot
# outlive the thing it is proving.
s, subs = call("/api/v1/billing/subscriptions?tenant=" + tenant)
rows = [r for r in (subs.get("subscriptions") or []) if r.get("plan_id") == pack["id"]]
if not rows:
    fails.append("the pack subscription cannot be read back")
else:
    row = rows[0]
    end = float(row.get("current_period_end") or 0)
    if end:
        fails.append("THE PACK WILL EXPIRE. Its period end is " + str(end) + " rather than 0, so "
                     "the resolver drops it once that time passes plus the tolerance — he paid "
                     "for messages that stop arriving tomorrow.")
    else:
        print("  ok the pack carries no period end, so it cannot lapse")
    if row.get("interval") != "once":
        fails.append("the pack's interval is " + str(row.get("interval")) + ", not once — the "
                     "renewal sweep would re-charge him every cycle")
    else:
        print("  ok its interval is once, so the sweep never re-charges it")

for p in (plan, pack):
    call("/api/v1/billing/plans/" + p["id"] + "/availability", {"active": False})

print("")
for f in fails:
    print("  ! " + f)
if not fails:
    print("  a pack is a subscription with interval once, and the union does the rest")
sys.exit(1 if fails else 0)
PY
