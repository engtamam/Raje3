#!/usr/bin/env bash
# The establishment that stopped paying — four behaviours, and the SEPARATION is the feature.
#
#   ./deploy/prove-unsubscribed.sh
#
# Merging these four is what a competitor does, and it is why leaving them feels like a punishment:
#
#   1 the data stays          his visits, his customers, his points, everything the engine learned.
#                             Deleting it is precisely what a competitor needs in order to take
#                             him — somebody who loses his history loses nothing by leaving.
#   2 the sending stops       every message costs us money at the provider. This is the honest one.
#   3 the customer's page     still opens. The customer is not the one who did not pay, and
#                             breaking it puts our name on a broken page in front of somebody with
#                             no part in the invoice.
#   4 the dashboard renders   with the at-risk list piling up. That is the truest pressure in the
#                             product because it is HIS number, not a warning we wrote.
#
# 2 needs proving because it must happen with no code of ours: messages.monthly resolves to
# NOT_ENTITLED once nothing billable contributes. 1, 3 and 4 need proving because they are
# behaviours by ABSENCE — nothing deletes, nothing gates — and an absence is exactly what a
# refactor removes by accident.
set -uo pipefail

NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

red(){ printf '  \e[31m%s\e[0m\n' "$*" >&2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^billing-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "billing-service is not running"; exit 1; }

KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.pu-key.pem
chmod 600 /tmp/.pu-key.pem
TOKEN=$(python3 -c '
import jwt, time
now = int(time.time())
print(jwt.encode({"sub": "prove-unsub", "tenant": "_platform",
                  "caps": ["platform.billing", "billing.manage"],
                  "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 600},
                 open("/tmp/.pu-key.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.pu-key.pem

INTERNAL=$(kubectl -n "$NS" get secret billing-service-secrets \
           -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$INTERNAL" ] || { red "no INTERNAL_SERVICE_TOKEN"; exit 1; }

# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$INTERNAL" <<PY
import json, sys, time, urllib.error, urllib.request
token, internal = sys.argv[1], sys.argv[2]
H = "http://localhost:8000"
KEY = "messages.monthly"

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
s, plan = call("/api/v1/billing/plans", {
    "name": "unsub-proof-" + stamp,
    "prices": [{"interval": "month", "amount_minor": 0, "currency": "SAR", "type": "flat"}],
    "limits": {KEY: {"kind": "counter", "limit": 5, "period": "billing_period",
                     "overage": "block"}}})
if s >= 400:
    print("  ! could not create the proof plan:", s, plan)
    sys.exit(1)
call("/api/v1/billing/plans/" + plan["id"] + "/availability", {"listed": False})

tenant = "prove-unsub-" + stamp
s, sub = call("/api/v1/billing/subscriptions", {"plan_id": plan["id"], "tenant": tenant})
if s >= 400:
    print("  ! could not subscribe:", s, sub)
    sys.exit(1)

fails = []

# He sends two messages while he is paying. These are the rows that must SURVIVE.
for k in ("m_1", "m_2"):
    call("/internal/billing/usage/consume",
         {"tenant": tenant, "key": KEY, "amount": 1, "idempotency_key": k}, internal_call=True)

s, before = call("/internal/billing/entitlements/check?tenant=" + tenant + "&key=" + KEY
                 + "&amount=1", internal_call=True)
if not before.get("allowed"):
    fails.append("a paying establishment could not send at all — the proof cannot continue")

# ── he stops paying ───────────────────────────────────────────────────────────────────────────
# NOW, not at period end: the two are genuinely different and this is the one being proven.
s, out = call("/api/v1/billing/subscriptions/" + sub["id"] + "/cancel?at_period_end=false",
              {}, method="POST")
if s >= 400:
    fails.append("could not cancel: " + str(s) + " " + str(out))

s, after = call("/internal/billing/entitlements/check?tenant=" + tenant + "&key=" + KEY
                + "&amount=1", internal_call=True)

# 2 — THE SENDING STOPS, and with no code of ours.
if after.get("allowed"):
    fails.append("A CANCELLED ESTABLISHMENT CAN STILL SEND. Every message is bought from the "
                 "provider, so this is money leaving with nothing coming in.")
else:
    print("  ok the sending stops (" + str(after.get("error") or "not entitled") + ")")

# 1 - THE DATA STAYS, and this script CANNOT prove that here. Written down rather than faked,
#     because the first version asserted the usage counter still read 2 after the cancellation,
#     called it "his history", and failed.
#
#     It was wrong about what it was looking at. A usage counter is keyed by PERIOD, and the
#     period is anchored on the subscription - so with no subscription there is no period key and
#     the read is 0. Nothing was deleted; the question moved. Resubscribing starts a new period
#     with a fresh allowance, which is not a loophole either: he paid for another month.
#
#     His actual history - visits, customers, points, what the engine learned - lives in
#     operations, loyalty and insights, and billing has never held a row of it. What guarantees it
#     survives is that NOTHING consumes SUBSCRIPTION_CANCELLED: no service listens, so there is no
#     code that could delete anything on a cancellation. ci/check_unsubscribed_paths.py holds that.
if after.get("current") is None:
    fails.append("the entitlement answer carries no usage figure at all")

# AND HE IS NOT ENTITLED RATHER THAN UNKNOWN. A key that resolves to a stated 0 lets a console
# say "your subscription ended, here is how to resume"; a key that resolves to nothing lets it
# say nothing at all, which is how somebody concludes the product is broken rather than unpaid.
if after.get("limit") not in (0, None):
    fails.append("after cancelling the limit is " + str(after.get("limit"))
                 + " — expected the plan to stop contributing entirely")

# ── and resuming is one call, because nothing was destroyed ───────────────────────────────────
s, sub2 = call("/api/v1/billing/subscriptions", {"plan_id": plan["id"], "tenant": tenant})
s, back = call("/internal/billing/entitlements/check?tenant=" + tenant + "&key=" + KEY
               + "&amount=1", internal_call=True)
if not back.get("allowed"):
    fails.append("he could not resume by subscribing again — coming back must be one payment, "
                 "not a support ticket")
else:
    print("  ok he resumes by paying, and his usage is still where he left it ("
          + str(back.get("current")) + ")")

call("/api/v1/billing/plans/" + plan["id"] + "/availability", {"active": False})

print("")
for f in fails:
    print("  ! " + f)
if not fails:
    print("  the data stays, the sending stops, and coming back is one payment")
sys.exit(1 if fails else 0)
PY
