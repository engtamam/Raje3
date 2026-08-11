#!/usr/bin/env bash
# Prove that a visit awards points — ON THE CLUSTER, through the real event.
#
#   bash deploy/prove-points.sh
#
# WHY THIS EXISTS. `Earner.from_visit` had four hundred passing tests around it and nothing called
# it: a visit was recorded and no point was awarded, for every shop, always. The rewards table, the
# redemption sheet and «نقاطي» all stood on a balance that could never be anything but zero, and
# the whole suite was green throughout. A unit test cannot see a missing caller — that is what this
# checks, and the only place it is true or false is a running cluster.
#
# IT RECORDS A REAL VISIT through the public API, then reads the balance loyalty actually holds.
# Nothing is faked: the event travels the bus it travels in production.
#
# THE POINTS ARE CONFIGURED FIRST, because a shop with no earning rule correctly awards nothing —
# and a script that skipped that step would report the wire broken when it is the settings that
# are empty.
set -euo pipefail
NS="${NS:-base-services}"
API="${API:-http://127.0.0.1:8090}"
PHONE="${SHOP_PHONE:-0549491771}"
PASSWORD="${SHOP_PASSWORD:-Raje3-Test-Passphrase!1}"

C_G=$'\e[32m'; C_R=$'\e[31m'; C_C=$'\e[36m'; C_N=$'\e[0m'
echo -e "${C_C}━━━ a visit awards points ━━━${C_N}"

API="$API" PHONE="$PHONE" PASSWORD="$PASSWORD" python3 - <<'PY'
import json, os, time, urllib.request, uuid

API, PHONE, PASSWORD = os.environ["API"], os.environ["PHONE"], os.environ["PASSWORD"]


def call(path, method="GET", body=None, token=""):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API + path, data, headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200]


_, tok = call("/api/v1/signup/signin", "POST", {"phone": PHONE, "password": PASSWORD})
token = tok["access_token"]

# A CUSTOMER NOBODY ELSE IS USING, so the balance read at the end is about this visit alone.
customer = "05" + str(int(time.time()))[-8:]

_, cat = call("/api/v1/field/catalogue", token=token)
service = cat["services"][0]
print(f"  service: {service['name']}")

# THE EARNING RULE, set to a number no default would produce.
st, _ = call("/api/v1/loyalty/settings/general", "PUT", {"points": 37}, token)
print(f"  earning rule set (37 per visit): {st}")

st, visit = call("/api/v1/field/visits", "POST", {
    "phone": customer, "service_ids": [service["id"]],
    "idempotency_key": str(uuid.uuid4()),
}, token)
print(f"  visit recorded: {st}")

_, who = call(f"/api/v1/field/customers/by-phone?phone={customer}", token=token)
subject = (who.get("customer") or {}).get("subject_ref", "")
print(f"  subject_ref: {subject}")

# THE BUS IS ASYNCHRONOUS. Polling rather than one read: a single check a moment after the visit
# would fail on a slow cluster and be indistinguishable from a missing subscription.
balance = 0
for _ in range(20):
    # THE SUBJECT IS IN THE PATH, not a query — read off the action catalogue rather than
    # guessed. My first version asked for a route that does not exist and got a 404, which
    # this script then reported as "the visit awarded nothing": a probe accusing the code.
    _, bal = call(f"/api/v1/loyalty/balance/{subject}", token=token)
    balance = (bal or {}).get("points", 0) if isinstance(bal, dict) else 0
    if balance:
        break
    time.sleep(1)

ok = balance == 37
print(f"  balance after the visit: {balance}")
if not ok:
    print("  ✗ the visit awarded nothing — loyalty is not consuming operations.visit.recorded")
else:
    print("  ✔ the visit awarded 37 points, through the event, on the cluster")

raise SystemExit(0 if ok else 1)
PY

echo -e "${C_G}✔ points proven live${C_N}"
