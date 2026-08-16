#!/usr/bin/env bash
# Prove that a redemption JOINS the visit confirmation instead of sending a second message (§9.6).
#
#   bash deploy/prove-redeem-merge.sh
#
# THE RULE THIS DEFENDS, IN THE OWNER'S WORDS: «تأكيد الاستبدال تكون ضمن رسالة تأكيد الزيارة بحيث
# ما نرسل رسايل كثير». Before this, a redemption sent its own receipt — a second message minutes
# after the first, from a product whose entire discipline is not sending many.
#
# AND THE TEN-MINUTE DELAY IS WHAT MAKES IT HONEST. The confirmation waits on purpose, and a reward
# is handed over inside exactly that window: the two are genuinely one moment at the counter, not
# two events we decided to staple together.
set -euo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
API="${API:-http://127.0.0.1:8090}"
PHONE="${SHOP_PHONE:-0549491771}"
PASSWORD="${SHOP_PASSWORD:-Raje3-Test-Passphrase!1}"
NS="${NS:-base-services}"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_N=$'\e[0m'
echo -e "${C_C}━━━ a redemption joins the confirmation ━━━${C_N}"

SUBJECT=$(API="$API" PHONE="$PHONE" PASSWORD="$PASSWORD" python3 - <<'PY'
import json, os, sys, time, urllib.request, uuid

API, PHONE, PASSWORD = os.environ["API"], os.environ["PHONE"], os.environ["PASSWORD"]


def call(path, method="GET", body=None, token=""):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API + path, data, h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  ! {method} {path} -> {e.code} {e.read()[:120]}", file=sys.stderr)
        raise


token = call("/api/v1/signup/signin", "POST", {"phone": PHONE, "password": PASSWORD})["access_token"]
customer = "05" + str(int(time.time()))[-8:]
cat = call("/api/v1/field/catalogue", token=token)
service = cat["services"][0]["id"]

# EARN ENOUGH TO SPEND. The cheapest reward decides how many visits — read, not assumed, because a
# seeded table differs by sector and a hardcoded loop would pass in a car wash and fail in a salon.
rewards = sorted(call("/api/v1/loyalty/rewards", token=token)["rewards"], key=lambda r: r["cost"])
if not rewards:
    print("  ! this shop has no rewards seeded", file=sys.stderr)
    raise SystemExit(1)
cheapest = rewards[0]
call("/api/v1/loyalty/settings/general", "PUT", {"points": cheapest["cost"]}, token)

# ONE VISIT PAYS FOR IT, so the confirmation waiting when we redeem is that visit's own.
call("/api/v1/field/visits", "POST", {
    "phone": customer, "service_ids": [service], "idempotency_key": str(uuid.uuid4())}, token)
who = call(f"/api/v1/field/customers/by-phone?phone={customer}", token=token)
subject = (who.get("customer") or {}).get("subject_ref", "")

for _ in range(20):
    bal = call(f"/api/v1/loyalty/balance/{subject}", token=token)
    if bal.get("points", 0) >= cheapest["cost"]:
        break
    time.sleep(1)

# WAIT FOR THE THING WE INTEND TO JOIN. The confirmation is written by REMINDERS consuming the
# visit event, and the balance by LOYALTY consuming the same event — two independent consumers on
# an asynchronous bus. Waiting only for the balance and then redeeming meant redeeming before the
# confirmation existed, and this script reported "the merge did not happen" about a race of its
# own making. In the shop the operator redeems minutes later and the row is always there.
for _ in range(30):
    sched = call(f"/api/v1/reminders/schedule?state=pending&limit=200", token=token)
    if any(r.get("subject_ref") == subject and r.get("kind") == "visit_confirmation"
           for r in sched.get("schedule", [])):
        break
    time.sleep(1)
else:
    print("  ! no confirmation was ever scheduled", file=sys.stderr)

call("/api/v1/loyalty/redeem", "POST", {
    "subject_ref": subject, "reward_id": cheapest["id"],
    "idempotency_key": str(uuid.uuid4())}, token)
print(subject)
PY
)

echo "  subject_ref: $SUBJECT"
sleep 2

kubectl -n "$NS" exec -i deploy/reminders -- env "SUBJECT=$SUBJECT" python3 - <<'PY'
import asyncio, os, sys
sys.path.insert(0, "/app")

from app.config import get_settings
from app.container import build_container
from app.core.stores import SCHEDULES

SUBJECT = os.environ["SUBJECT"]


async def main() -> int:
    c = build_container(get_settings())
    rows = [r for r in await c.datastore.scan_all(SCHEDULES, 20_000)
            if r.get("subject_ref") == SUBJECT]
    confirm = [r for r in rows if r.get("kind") == "visit_confirmation"]

    ok = True
    if not confirm:
        print("  ✗ no confirmation at all")
        return 1

    # THE MERGED ONE IF THERE IS ONE, and the count is asserted separately below. Taking
    # `confirm[0]` blindly reported "not upgraded" while a correctly upgraded row sat second in
    # the list — the duplicate was the real bug and this reading hid it behind a wrong sentence.
    row = next((r for r in confirm if r.get("template_type") == "svc_visit_redeemed"), confirm[0])
    print(f"    template_type = {row.get('template_type')}")
    print(f"    redeemed      = {row.get('redeemed_name')!r}"
          f"  cost={row.get('redeemed_cost')}  remaining={row.get('redeemed_remaining')}")

    if row.get("template_type") != "svc_visit_redeemed":
        print("  ✗ the confirmation was not upgraded — the redemption sent its own message instead")
        ok = False
    if not row.get("redeemed_name"):
        print("  ✗ no reward name on the row — the message would render an empty slot")
        ok = False
    # ONE MESSAGE, NOT TWO. A second pending row for the same customer is the failure this whole
    # change exists to prevent.
    if len(confirm) != 1:
        print(f"  ✗ {len(confirm)} confirmations pending")
        ok = False

    print("  ✔ one message, carrying both the visit and what he spent" if ok else "  ✗ FAILED")
    return 0 if ok else 1


raise SystemExit(asyncio.run(main()))
PY

echo -e "${C_G}✔ the merge is real${C_N}"
