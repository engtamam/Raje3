#!/usr/bin/env bash
# The seam nothing else proves: does the receipt actually REACH reminders?
#
# Four defects in this product were found only by a live call — an event subscription never
# registered, a catch-up that could not bootstrap, an import that printed success while failing, a
# shop name blank in every message. All four were seams. This is loyalty's.
set -uo pipefail
NS=base-services
L=$(kubectl -n $NS get pods --no-headers | awk '/^loyalty-/ && $3=="Running" {print $1; exit}')
TOKEN=$(kubectl -n $NS get secret loyalty-secrets -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' | base64 -d)

kubectl -n $NS exec -i "$L" -- python - "$TOKEN" <<'PY'
import json, sys, urllib.error, urllib.request
INT = sys.argv[1]

def post(url, body):
    r = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                               headers={"Content-Type": "application/json",
                                        "X-Internal-Token": INT})
    try:
        u = urllib.request.urlopen(r, timeout=25)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"raw": e.read().decode()[:300]}
    except Exception as e:                                           # noqa: BLE001
        return 0, {"unreachable": str(e)[:200]}

print("── is reminders' send path real, from INSIDE loyalty? ───")
# The path loyalty is configured with, called exactly as its adapter calls it. A path that does not
# exist answers 404 here and NOTHING anywhere else: the receipt fails inside a try/except that is
# deliberately not allowed to undo the redemption.
s, d = post("http://reminders:8000/internal/reminders/send",
            {"tenant": "wired-shop", "subject_ref": "ref_seamproof0001",
             "template_type": "per_account_notice", "class": "personal",
             "owner_text": "تم استبدال 30 نقطة مقابل قهوة مجانية. رصيدك المتبقي: 20 نقطة.",
             "idempotency_key": "loyalty:seam:proof-1"})
print(f"  status {s}")
print(f"  {json.dumps(d, ensure_ascii=False)[:300]}")
if s == 404:
    print("  \033[31m✗ the configured path does not exist — every receipt would vanish silently\033[0m")
    sys.exit(1)
if s == 0:
    print("  \033[31m✗ reminders is unreachable from loyalty — NetworkPolicy or DNS\033[0m")
    sys.exit(1)
print("  \033[32m✔ the path exists and reminders answered — the gate decided, not us\033[0m")

print()
print("── and operations' by-ref visit route, likewise ─────────")
s, d = post("http://operations:8000/internal/operations/visits/by-ref",
            {"tenant": "wired-shop", "subject_ref": "ref_seamproof0001",
             "service_id": "svc-any", "actor": "emp-live", "source": "rdm_seamproof"})
print(f"  status {s}")
print(f"  {json.dumps(d, ensure_ascii=False)[:250]}")
if s == 404:
    print("  \033[31m✗ the route loyalty is configured with does not exist\033[0m")
    sys.exit(1)
print("  \033[32m✔ the route exists — a free wash would be recorded as a visit\033[0m")
PY
