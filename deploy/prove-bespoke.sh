#!/usr/bin/env bash
# A plan built for ONE establishment — and the proof that no service can tell.
#
#   ./deploy/prove-bespoke.sh
#
# THE WHOLE TEST OF THE DESIGN is that nothing learns anything. A negotiated customer — twenty
# branches, an agreed message volume — gets a plan of his own, created from our panel, and every
# service resolves his entitlements through the same path, with the same code, as a shop on the
# 148 plan. No flag, no special case, and no tenant id in a conditional anywhere.
#
# So this script does not test a feature. It tests that there ISN'T one: it creates a bespoke
# plan, subscribes a tenant, and reads the entitlements back — and they must be indistinguishable
# in shape from a published plan's.
#
# WHAT IT MUST NOT BECOME: a discount mechanism. Billing has coupons for that. A bespoke plan is
# for a different SHAPE, not a different price for the same thing — otherwise the pricing table
# stops reconciling at year end and nobody can say what the product costs.
#
# The other half of the proof is a grep, and it lives in the task rather than here: any tenant id
# in a conditional in any service is the design having failed. It is clean today.
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
print(jwt.encode({"sub": "prove-bespoke", "tenant": "_platform",
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

# THE NAME IS THE DOCUMENTATION. In six months this row is one line in a list, and "custom" or
# "special" tells the next operator nothing. The convention is: خاص · <the shop> · <why>.
s, plan = call("/api/v1/billing/plans", {
    "name": "خاص · مغسلة النخيل · 20 فرعاً",
    "prices": [{"interval": "month", "amount_minor": 120000, "currency": "SAR",
                "type": "flat", "includes_tax": True}],
    "limits": {"messages.monthly": {"kind": "counter", "limit": 40000,
                                    "period": "billing_period", "overage": "block"},
               "staff.seats": {"kind": "gauge", "limit": -1},
               "branches": {"kind": "gauge", "limit": 20},
               "feature.campaigns": {"kind": "boolean", "limit": 1},
               "feature.loyalty": {"kind": "boolean", "limit": 1},
               "feature.insights.engine": {"kind": "boolean", "limit": 1},
               "feature.roles.custom": {"kind": "boolean", "limit": 1},
               "templates.custom": {"kind": "counter", "limit": -1, "period": "month",
                                    "overage": "block"},
               "feature.api": {"kind": "boolean", "limit": 0}}})
if s >= 400:
    print("  ! could not create the bespoke plan:", s, plan)
    sys.exit(1)

# UNLISTED IS THE ENTIRE MECHANISM. Invisible on the pricing page, still subscribable, and no code
# anywhere learns that a fourth shape exists.
s, _ = call("/api/v1/billing/plans/" + plan["id"] + "/availability", {"listed": False})

fails = []

# It must not appear in what a shop sees.
s, pub = call("/api/v1/billing/public/plans")
if any(p.get("id") == plan["id"] for p in (pub.get("plans") or [])):
    fails.append("the bespoke plan is on the PUBLIC pricing page — one customer's negotiated "
                 "terms are being offered to everybody")
else:
    print("  ok it is invisible on the public pricing page")

# And it must appear to us.
s, ours = call("/api/v1/billing/plans?include_hidden=true")
if not any(p.get("id") == plan["id"] for p in (ours.get("plans") or [])):
    fails.append("the operator cannot see the plan he just created")
else:
    print("  ok the operator still sees it")

tenant = "prove-bespoke-" + stamp
s, sub = call("/api/v1/billing/subscriptions", {"plan_id": plan["id"], "tenant": tenant})
if s >= 400:
    fails.append("could not subscribe to it: " + str(s) + " " + str(sub))
    print("")
    for f in fails:
        print("  ! " + f)
    sys.exit(1)
print("  ok a tenant subscribes to it through the ordinary route")

# THE POINT OF THE WHOLE THING: the same read, the same shape, the same code.
EXPECT = {"messages.monthly": 40000, "staff.seats": -1, "branches": 20,
          "feature.campaigns": 1, "feature.loyalty": 1, "feature.insights.engine": 1,
          "feature.roles.custom": 1, "templates.custom": -1, "feature.api": 0}
bad = []
for key, want in EXPECT.items():
    s, res = call("/internal/billing/entitlements/check?tenant=" + tenant + "&key=" + key,
                  internal_call=True)
    got = -1 if res.get("unlimited") else res.get("limit")
    if got is None or int(got) != int(want):
        bad.append(key + ": " + str(got) + " != " + str(want))
if bad:
    fails.append("a bespoke plan does not resolve like a published one: " + "; ".join(bad))
else:
    print("  ok all 9 keys resolve exactly as a published plan's do, through the same path")

call("/api/v1/billing/plans/" + plan["id"] + "/availability", {"active": False})

print("")
for f in fails:
    print("  ! " + f)
if not fails:
    print("  a plan for one shop is a plan. No service can tell, and none needs to.")
sys.exit(1 if fails else 0)
PY
