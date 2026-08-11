#!/usr/bin/env bash
# Prove that a visit schedules its confirmation — the message the library opens with.
#
#   bash deploy/prove-confirmation.sh
#
# WHY. `svc_visit_confirmation` shipped in three tones in the very first template seed, and
# `gate.py` exempts the type from quiet hours by name — so every part of the system knew about a
# message that nothing ever created. A visit produced a reminder in ninety days and a follow-up in
# fifteen, and said nothing at all on the day. Sixth severed wire, and it was the most visible one
# in the product: the first message a customer was ever supposed to receive.
#
# IT RECORDS A REAL VISIT and reads the schedule the engine actually wrote.
set -euo pipefail
API="${API:-http://127.0.0.1:8090}"
PHONE="${SHOP_PHONE:-0549491771}"
PASSWORD="${SHOP_PASSWORD:-Raje3-Test-Passphrase!1}"
NS="${NS:-base-services}"
SSH="${SSH:-ssh -o StrictHostKeyChecking=no -p 2224 tamam@127.0.0.1}"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_N=$'\e[0m'
echo -e "${C_C}━━━ a visit schedules its confirmation ━━━${C_N}"

SUBJECT=$(API="$API" PHONE="$PHONE" PASSWORD="$PASSWORD" python3 - <<'PY'
import json, os, time, urllib.request, uuid

API, PHONE, PASSWORD = os.environ["API"], os.environ["PHONE"], os.environ["PASSWORD"]


def call(path, method="GET", body=None, token=""):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API + path, data, h, method=method)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


token = call("/api/v1/signup/signin", "POST", {"phone": PHONE, "password": PASSWORD})["access_token"]
customer = "05" + str(int(time.time()))[-8:]
cat = call("/api/v1/field/catalogue", token=token)
call("/api/v1/field/visits", "POST", {
    "phone": customer, "service_ids": [cat["services"][0]["id"]],
    "idempotency_key": str(uuid.uuid4())}, token)
who = call(f"/api/v1/field/customers/by-phone?phone={customer}", token=token)
print((who.get("customer") or {}).get("subject_ref", ""))
PY
)

echo "  subject_ref: $SUBJECT"
sleep 3      # the bus is asynchronous; the schedule is written by the consumer

$SSH "kubectl -n $NS exec -i deploy/reminders -- env SUBJECT=$SUBJECT python3 -" <<'PY'
import asyncio, os, sys, time
sys.path.insert(0, "/app")

from app.config import get_settings
from app.container import build_container
from app.core.stores import ScheduleStore, SCHEDULES

SUBJECT = os.environ["SUBJECT"]


async def main() -> int:
    c = build_container(get_settings())
    rows = [r for r in await c.datastore.scan_all(SCHEDULES, 20_000)
            if r.get("subject_ref") == SUBJECT]
    kinds = sorted({r.get("kind", "") for r in rows})
    print(f"  scheduled kinds: {kinds}")

    confirm = [r for r in rows if r.get("kind") == "visit_confirmation"]
    ok = True
    if not confirm:
        print("  ✗ no confirmation scheduled — the message the library opens with still never goes")
        return 1

    row = confirm[0]
    delay = row["due_at"] - int(row.get("created") or row["due_at"])
    print(f"    due in {delay // 60} minute(s)  ·  type={row.get('template_type')}  cls={row.get('cls')}")

    # TEN MINUTES, from configuration. Not instantly — a message that arrives while he is still at
    # the counter is about something he is watching happen.
    if not (540 <= delay <= 660):
        print(f"  ✗ due in {delay}s, expected about 600")
        ok = False
    if row.get("template_type") != "svc_visit_confirmation":
        print(f"  ✗ template_type is {row.get('template_type')!r}")
        ok = False
    # ONE PER VISIT, NOT ONE PER SERVICE. It confirms the visit, and a visit with two services is
    # still one event — two confirmations would be the noise this product exists to prevent.
    if len(confirm) != 1:
        print(f"  ✗ {len(confirm)} confirmations for one visit")
        ok = False

    print("  ✔ one confirmation, ten minutes out, on the right template"
          if ok else "  ✗ FAILED")
    return 0 if ok else 1


raise SystemExit(asyncio.run(main()))
PY

echo -e "${C_G}✔ confirmation proven live${C_N}"
