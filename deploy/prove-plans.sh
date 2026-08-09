#!/usr/bin/env bash
# Prove the price list is the price list — on the cluster, against the running billing-service.
#
#   ./deploy/prove-plans.sh
#
# WHAT THIS PROVES, and why reading plans.json back is not it: a plan row can be perfect and the
# entitlement answer still wrong, because the answer comes from the SUBSCRIPTION's snapshot of the
# limits rather than from the plan. So this subscribes a throwaway establishment to each plan and
# asks the question every service will actually ask — /internal/billing/entitlements/check — for
# every key in the table.
#
# INCLUDING THE ZEROS, and that is the part worth the extra lines. `0` means the key exists and the
# answer is DENY; a MISSING key means not entitled with no reason to show. A console can turn the
# first into "your plan does not include this, here is the one that does" and the second into
# nothing at all. Proving only the ones that should be on would pass with every zero missing.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^billing-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "billing-service is not running"; exit 1; }

KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.prove-key.pem
chmod 600 /tmp/.prove-key.pem
TOKEN=$(python3 -c '
import jwt, time
now = int(time.time())
print(jwt.encode({"sub": "prove-plans", "tenant": "_platform",
                  "caps": ["platform.billing", "billing.manage"],
                  "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 600},
                 open("/tmp/.prove-key.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.prove-key.pem

INTERNAL=$(kubectl -n "$NS" get secret billing-service-secrets \
           -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$INTERNAL" ] || { red "no INTERNAL_SERVICE_TOKEN"; exit 1; }

# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$INTERNAL" <<PY
import json, sys, time, urllib.error, urllib.request
token, internal = sys.argv[1], sys.argv[2]
H = "http://localhost:8000"

# THE TABLE, WRITTEN OUT INDEPENDENTLY OF THE SEED FILE. Reading the expectations out of
# plans.json would prove the seeder agrees with itself, which it does by construction. These
# numbers are transcribed from the specification, so a seeder that writes the wrong ones fails.
EXPECT = {
  "الأساسية": {"messages.monthly": 1000, "staff.seats": 5, "branches": 1,
               "feature.campaigns": 0, "feature.loyalty": 0, "feature.insights.engine": 0,
               "feature.roles.custom": 0, "templates.custom": 0, "feature.api": 0},
  "الذكية":   {"messages.monthly": 3000, "staff.seats": 15, "branches": 2,
               "feature.campaigns": 1, "feature.loyalty": 1, "feature.insights.engine": 0,
               "feature.roles.custom": 0, "templates.custom": 1, "feature.api": 0},
  "الأعمال":  {"messages.monthly": 8000, "staff.seats": -1, "branches": 8,
               "feature.campaigns": 1, "feature.loyalty": 1, "feature.insights.engine": 1,
               "feature.roles.custom": 1, "templates.custom": -1, "feature.api": 0},
  "المؤسسات":    {"messages.monthly": -1, "staff.seats": -1, "branches": -1,
               "feature.campaigns": 1, "feature.loyalty": 1, "feature.insights.engine": 1,
               "feature.roles.custom": 1, "templates.custom": -1, "feature.api": 1},
}

def call(path, body=None, method=None, tok=None, hdr=None):
    d = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": "Bearer " + (tok or token)}
    if hdr:
        headers.update(hdr)
    r = urllib.request.Request(H + path, data=d, method=method or ("POST" if d else "GET"),
                               headers=headers)
    if d:
        r.add_header("Content-Type", "application/json")
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

s, out = call("/api/v1/billing/plans?include_hidden=true")
if s >= 400:
    print("  ! cannot read plans:", s, out)
    sys.exit(1)
plans = {p["name"]: p for p in (out.get("plans") or [])}

stamp = str(int(time.time()))
failed = 0
for name, table in EXPECT.items():
    plan = plans.get(name)
    if plan is None:
        print("  ! no plan named " + name + " — run deploy/seed/seed-plans.sh")
        failed += 1
        continue
    tenant = "prove-plan-" + stamp + "-" + str(len(plan["id"]))[:2] + plan["id"][-6:]
    s, sub = call("/api/v1/billing/subscriptions", {"plan_id": plan["id"], "tenant": tenant})
    if s >= 400:
        print("  ! " + name + ": could not subscribe " + str(s) + " " + str(sub))
        failed += 1
        continue

    # PRESENCE IS PROVEN FROM THE SUBSCRIPTION, NOT FROM THE CHECK — and finding that out is
    # itself worth the trip. The advisory check answers with evaluate(), which does not carry
    # present: an absent key resolves to the deny-by-default spec and answers limit 0, exactly
    # like a key the plan sets to 0. Through that route the two are INDISTINGUISHABLE, which is
    # precisely the distinction every plan carrying every key exists to preserve.
    #
    # So the number comes from the entitlement answer, and the presence comes from the limits
    # snapshot the subscription was created with — which is also the thing that actually decides,
    # since a plan edited later does not reprice anybody already on it.
    snapshot = sub.get("limits_snapshot") or {}

    bad = []
    for key, want in table.items():
        if key not in snapshot:
            bad.append(key + ": MISSING from the subscription (a plan must carry every key, "
                             "including the zeros — 0 is DENY, absent is no reason to show)")
            continue
        s2, res = call("/internal/billing/entitlements/check?tenant=" + tenant + "&key=" + key,
                       tok=internal, hdr={"X-Internal-Token": internal})
        if s2 >= 400:
            bad.append(key + ": HTTP " + str(s2))
            continue
        # UNLIMITED ANSWERS limit=None, not -1. -1 is how a limit is WRITTEN; None is how the
        # answer says "there is no ceiling". Reading one as the other crashed the first run.
        got = -1 if res.get("unlimited") else res.get("limit")
        if got is None or int(got) != int(want):
            bad.append(key + ": " + str(got) + " != " + str(want))
    if bad:
        print("  ! " + name)
        for b in bad:
            print("      " + b)
        failed += 1
    else:
        print("  ok " + name + " — all " + str(len(table)) + " keys match, and every zero is present")

print("")
if failed:
    print(str(failed) + " plan(s) do not match the table")
sys.exit(1 if failed else 0)
PY
