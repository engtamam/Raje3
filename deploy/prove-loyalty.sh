#!/usr/bin/env bash
# loyalty, proven with real calls against the running image on its pinned digest.
set -uo pipefail
NS=base-services
P=$(kubectl -n $NS get pods --no-headers | awk '/^loyalty-/ && $3=="Running" {print $1; exit}')
[ -n "$P" ] || { echo "no loyalty pod"; exit 1; }
TOKEN=$(kubectl -n $NS get secret loyalty-secrets -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' | base64 -d)
kubectl -n $NS get secret identity-service-secrets -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' | base64 -d > /tmp/.k.pem
USER_TOKEN=$(python3 -c '
import jwt, time
n = int(time.time())
print(jwt.encode({"sub": "emp-live", "tenant": "wired-shop",
                  "caps": ["loyalty.read", "loyalty.manage", "loyalty.redeem"],
                  "iss": "raje3", "aud": "raje3", "iat": n, "exp": n + 900},
                 open("/tmp/.k.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.k.pem

kubectl -n $NS exec -i "$P" -- python - "$TOKEN" "$USER_TOKEN" <<'PY'
import json, sys, urllib.error, urllib.request
INT, USR = sys.argv[1], sys.argv[2]
H = "http://localhost:8000"
S = "ref_liveproof0001"
T = "wired-shop"
ok = fail = 0

def call(path, body=None, *, user=False, method=None):
    d = json.dumps(body).encode() if body is not None else None
    h = {"Authorization": "Bearer " + USR} if user else {"X-Internal-Token": INT}
    if d:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(H + path, data=d, method=method or ("POST" if d else "GET"),
                               headers=h)
    try:
        u = urllib.request.urlopen(r, timeout=25)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}

def check(label, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  \033[32m✔\033[0m {label}" + (f"  {detail}" if detail else ""))
    else:
        fail += 1
        print(f"  \033[31m✗\033[0m {label}  {detail}")

print("── the service is alive on its own digest ──────────────")
s, d = call("/internal/manifest")
check("manifest served", s == 200, f"{len(d.get('endpoints', []))} endpoints, "
      f"{len(d.get('admin_actions', []))} admin + {len(d.get('user_actions', []))} user actions")
check("capabilities advertised", set(d.get("capabilities", [])) ==
      {"loyalty.read", "loyalty.redeem", "loyalty.manage", "platform.loyalty"},
      str(d.get("capabilities")))

print()
print("── earning: the tree, and one entry per visit ──────────")
call("/api/v1/loyalty/settings/general", {"points": 5}, user=True, method="PUT")
call("/api/v1/loyalty/settings/service/oil", {"points": 45}, user=True, method="PUT")
s, d = call("/internal/loyalty/earn", {"tenant": T, "visit_id": "live-v1", "subject_ref": S,
                                       "service_ids": ["wash", "oil"]})
check("a visit earns", s == 200 and d.get("earned") == 50, str(d))
check("the level that decided is recorded", d.get("rule_level") == "service", str(d.get("rule_level")))
s, again = call("/internal/loyalty/earn", {"tenant": T, "visit_id": "live-v1", "subject_ref": S,
                                           "service_ids": ["wash", "oil"]})
check("a redelivered visit pays once", again.get("duplicate") is True and again.get("earned") == 0)

print()
print("── the field screen ────────────────────────────────────")
s, d = call("/api/v1/loyalty/rewards", {"name": "قهوة مجانية", "cost": 30, "type": "item"},
            user=True)
rid = d.get("id", "")
check("a reward is created", s == 200 and rid, str(d)[:80])
s, big = call("/api/v1/loyalty/rewards", {"name": "غسلة كاملة", "cost": 900, "type": "item"},
              user=True)
s, bal = call(f"/api/v1/loyalty/balance/{S}", user=True)
check("the balance reads", s == 200 and bal.get("points") == 50, str(bal.get("points")))
# A SET, not a list: this script has run before and the catalogue is real data that persists.
# Asserting an exact list made the proof fail on its second run for a reason that was not a defect.
check("only affordable rewards are offered",
      {r["name"] for r in bal.get("rewards", [])} == {"قهوة مجانية"}
      and all(r["cost"] <= bal["points"] for r in bal.get("rewards", [])),
      str([(r["name"], r["cost"]) for r in bal.get("rewards", [])]))
check("how far to the next reward", bal.get("to_next_reward") == 850,
      str(bal.get("to_next_reward")))
check("the expiry date is on the screen", bal.get("expires_at", 0) > 0)

print()
print("── redeeming ───────────────────────────────────────────")
s, d = call("/api/v1/loyalty/redeem",
            {"subject_ref": S, "reward_id": rid, "idempotency_key": "live-k1"}, user=True)
check("the operator spends", s == 200 and d.get("balance") == 20, str(d.get("balance")))
check("attributed to the account, not a PIN", d.get("redemption", {}).get("actor") == "emp-live",
      str(d.get("redemption", {}).get("actor")))
s, twice = call("/api/v1/loyalty/redeem",
                {"subject_ref": S, "reward_id": rid, "idempotency_key": "live-k1"}, user=True)
check("the same key twice spends once",
      twice.get("duplicate") is True and twice.get("balance") == 20, str(twice.get("balance")))

s, over = call("/api/v1/loyalty/redeem",
               {"subject_ref": S, "reward_id": big.get("id", ""),
                "idempotency_key": "live-k2"}, user=True)
check("an overdraft is refused, with a reason the operator can READ",
      s == 409 and "reason" in over, str(over)[:100])

print()
print("── the refusal reaches the owner (trap 4.25) ───────────")
s, d = call("/api/v1/loyalty/rewards", {"name": "قهوة\nمجانية", "cost": 10, "type": "item"},
            user=True)
check("a bad reward name names the rule", s == 400 and d.get("reason"), str(d)[:120])
s, d = call("/api/v1/loyalty/settings/mode", {"mode": "invoice", "points_per_riyal": 1},
            user=True, method="PUT")
check("invoice mode without a till says why, IN ARABIC",
      s == 400 and "الكاشير" in str(d.get("reason", "")),
      str(d)[:120])

print()
print("── the ledger is the truth ─────────────────────────────")
s, d = call(f"/api/v1/loyalty/history/{S}", user=True)
entries = d.get("entries", [])
check("every movement is on the record", s == 200 and len(entries) == 2,
      str([(e["reason"], e["delta"]) for e in entries]))
check("each entry carries the balance it produced",
      sorted(e["balance_after"] for e in entries) == [20, 50],
      str(sorted(e.get("balance_after", -1) for e in entries)))
s, d = call("/internal/loyalty/reconcile", {"tenant": T, "subject_ref": S})
check("reconcile agrees with the ledger", d.get("ledger") == 20 and d.get("repaired") is False,
      str(d))

print()
print("── the report the owner reads ──────────────────────────")
s, d = call("/api/v1/loyalty/report", user=True)
check("the outstanding obligation is named", s == 200 and d.get("outstanding") == 20, str(d)[:140])

print()
print("── the tick, and its schedule ──────────────────────────")
s, d = call("/internal/loyalty/tick", {"tenant": T})
check("the tick runs", s == 200, str(d))

print()
print("── erasure ─────────────────────────────────────────────")
s, d = call("/internal/privacy/erase", {"tenant": T, "subject": S})
check("the balance and the ledger go", s == 200 and d.get("erased"), str(d.get("erased")))
s, d = call("/internal/privacy/erase", {"tenant": T, "subject": S})
check("a retried DSAR succeeds", s == 200 and d.get("already_absent") is True)
s, bal = call(f"/api/v1/loyalty/balance/{S}", user=True)
check("nothing is left behind", bal.get("points") == 0)

print()
print(f"  {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
PY
