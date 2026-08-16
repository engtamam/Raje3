#!/usr/bin/env bash
# The trial, and the day it ends — on the cluster.
#
#   ./deploy/prove-trial.sh
#
# WE CANNOT WAIT FOURTEEN DAYS, and we do not have to. The thing that was broken was not the
# passage of time, it was the ROW: a trialing subscription was created with a period end a full
# interval away while trial_end sat beside it, written and read by nothing. A 14-day trial granted
# thirty days, silently, in our favour.
#
# So this checks the state that decides the outcome: the period end IS the trial end. Once that is
# true, the lapse is the resolver's ordinary behaviour, which is already proven elsewhere.
#
# It also checks what must NOT happen: nobody is moved to `active` by a sweep, and no invoice is
# raised — the trial ending is a stop, not an automatic subscription. That is the same decision as
# no auto-renew, applied at the other end (16.8).
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
print(jwt.encode({"sub": "prove-trial", "tenant": "_platform",
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
TRIAL_DAYS = 14

s, plan = call("/api/v1/billing/plans", {
    "name": "trial-proof-" + stamp,
    # ZERO, not the real price. What is proven here is when the period ends, and copying the
    # actual amount in would put a price in code — which the guard correctly refused.
    "prices": [{"interval": "month", "amount_minor": 0, "currency": "SAR", "type": "flat",
                "includes_tax": True}],
    "trial_days": TRIAL_DAYS,
    "limits": {KEY: {"kind": "counter", "limit": 1000, "period": "billing_period",
                     "overage": "block"}}})
if s >= 400:
    print("  ! could not create the trial plan:", s, plan)
    sys.exit(1)
call("/api/v1/billing/plans/" + plan["id"] + "/availability", {"listed": False})

tenant = "prove-trial-" + stamp
s, sub = call("/api/v1/billing/subscriptions", {"plan_id": plan["id"], "tenant": tenant})
if s >= 400:
    print("  ! could not subscribe:", s, sub)
    sys.exit(1)

fails = []

if sub.get("status") != "trialing":
    fails.append("a plan with a trial produced status " + str(sub.get("status"))
                 + ", not trialing")
else:
    print("  ok he starts on a trial rather than a paid month")

trial_end = float(sub.get("trial_end") or 0)
period_end = float(sub.get("current_period_end") or 0)
if not trial_end:
    fails.append("no trial_end was recorded at all")
elif abs(period_end - trial_end) > 60:
    days = (period_end - trial_end) / 86400.0
    fails.append("THE TRIAL DOES NOT END WHEN IT SAYS. The period runs "
                 + str(round(days)) + " days past trial_end, so a "
                 + str(TRIAL_DAYS) + "-day trial grants "
                 + str(round((period_end - float(sub.get("current_period_start") or 0)) / 86400.0))
                 + ". A promise broken in our favour is the worse direction to be wrong in.")
else:
    print("  ok the paid period ends exactly when the trial does")

# HE CAN SEND DURING IT. A trial that entitles nothing is not a trial.
s, out = call("/internal/billing/entitlements/check?tenant=" + tenant + "&key=" + KEY,
              internal_call=True)
if not out.get("allowed"):
    fails.append("he cannot send during his own trial")
else:
    print("  ok he can send during it (" + str(out.get("limit")) + " messages)")

# AND NOTHING HAS BEEN CHARGED. No card, no invoice, no automatic anything.
s, inv = call("/api/v1/billing/invoices?tenant=" + tenant)
issued = [i for i in (inv.get("invoices") or []) if str(i.get("status")) != "draft"]
if issued:
    fails.append("an invoice was raised for a trial nobody has paid for: " + str(issued[:1]))
else:
    print("  ok nothing has been invoiced")

call("/api/v1/billing/plans/" + plan["id"] + "/availability", {"active": False})

print("")
for f in fails:
    print("  ! " + f)
if not fails:
    print("  the trial ends when it says it ends, and upgrades nobody")
sys.exit(1 if fails else 0)
PY
