#!/usr/bin/env bash
# insights, proven with real calls against the running image on its pinned digest.
#
# Five defects in this product were found ONLY by a live call and no test caught any of them: an
# event subscription never registered, a catch-up that could not bootstrap, an import that printed
# success while failing, a shop name blank in every message, and a peer route that existed in code
# and 404'd on the running image. This is the same exercise for this service.
set -uo pipefail
NS=base-services
P=$(kubectl -n $NS get pods --no-headers | awk '/^insights-/ && $3=="Running" {print $1; exit}')
[ -n "$P" ] || { echo "no insights pod"; exit 1; }
TOKEN=$(kubectl -n $NS get secret insights-secrets -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' | base64 -d)
kubectl -n $NS get secret identity-service-secrets -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' | base64 -d > /tmp/.k.pem
mint() {
  PLAN="$1" CAPS="$2" python3 -c '
import jwt, os, time
n = int(time.time())
print(jwt.encode({"sub": "owner-live", "tenant": "wired-shop", "plan": os.environ["PLAN"],
                  "caps": os.environ["CAPS"].split(), "iss": "raje3", "aud": "raje3",
                  "iat": n, "exp": n + 900},
                 open("/tmp/.k.pem").read(), algorithm="RS256"), end="")'
}
SMART=$(mint smart "insights.read")
PRO=$(mint pro "insights.read")
OPS=$(mint pro "insights.read platform.insights")
rm -f /tmp/.k.pem

kubectl -n $NS exec -i "$P" -- python - "$TOKEN" "$SMART" "$PRO" "$OPS" <<'PY'
import json, sys, urllib.error, urllib.request
INT, SMART, PRO, OPS = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
H = "http://localhost:8000"
T = "wired-shop"
ok = fail = 0

def call(path, body=None, *, tok=None, method=None):
    d = json.dumps(body).encode() if body is not None else None
    h = {"Authorization": "Bearer " + tok} if tok else {"X-Internal-Token": INT}
    if d:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(H + path, data=d, method=method or ("POST" if d else "GET"),
                               headers=h)
    try:
        u = urllib.request.urlopen(r, timeout=40)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()[:300]
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}

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
check("manifest served", s == 200,
      f"{len(d.get('endpoints', []))} endpoints, {len(d.get('admin_actions', []))} admin actions")
check("capabilities advertised",
      set(d.get("capabilities", [])) == {"insights.read", "platform.insights"},
      str(d.get("capabilities")))
check("it subscribes to no event, by design",
      d.get("events", {}).get("consumed") == [], str(d.get("events")))

print()
print("── a brand-new shop is never shown a blank ─────────────")
s, d = call("/api/v1/insights/dashboard", tok=SMART)
check("it says it is computing", s == 200 and (d.get("computing") is True or d.get("as_of", 0) > 0),
      str(d.get("message") or d.get("as_of")))

print()
print("── the sweep runs and reports ──────────────────────────")
s, d = call("/internal/insights/tick", {"tenant": T})
check("the tick runs", s == 200, str(d))
s, d = call("/internal/insights/tick", {})
check("the bootstrap pass reads every tenant from the data", s == 200, str(d))

print()
print("── the dashboard, and its as-of time ───────────────────")
s, d = call("/api/v1/insights/dashboard", tok=SMART)
if d.get("computing"):
    check("a shop with no visits still answers honestly", s == 200, "computing")
else:
    check("the dashboard reads", s == 200 and "values" in d, f"{d.get('visits')} visits")
    check("its age is always shown", "as_of_hours_ago" in d and "stale" in d,
          f"as_of_hours_ago={d.get('as_of_hours_ago')}")
    check("the entry plan does not see the engine",
          "associations" not in (d.get("values") or {}),
          str(sorted((d.get("values") or {}).keys())[:6]))

print()
print("── the plan gate, enforced at the route ────────────────")
s, d = call("/api/v1/insights/associations", tok=SMART)
check("the entry plan is refused, with a reason he can READ",
      s == 402 and d.get("reason"), str(d)[:110])
s, d = call("/api/v1/insights/bundles", tok=SMART)
check("the bundles page is gated too", s == 402, str(s))
s, d = call("/api/v1/insights/associations", tok=PRO)
check("a higher plan is served", s == 200, str(d)[:110])
if s == 200 and not d.get("learning"):
    check("no arithmetic ever leaves the service — the engine is ours",
          all("lift_basket" not in p and "lift_customer" not in p for p in d.get("pairs", [])),
          f"{len(d.get('pairs', []))} pairs")
else:
    check("the learning state is explicit, not a blank",
          d.get("learning") is True and d.get("need", 0) > 0,
          f"have={d.get('have')} need={d.get('need')}")

print()
print("── coverage names who owns the fix ─────────────────────")
s, d = call("/api/v1/insights/dashboard", tok=SMART)
blocked = {e["indicator"]: e for e in (d.get("not_enabled") or [])}
if blocked:
    check("a blocked indicator names its cause and its owner",
          all(e.get("why") and e.get("owner") for e in blocked.values()),
          str(list(blocked)))
else:
    check("nothing is blocked for this shop", True, "coverage is complete or there are no visits")

print()
print("── ours, and not the establishment's ───────────────────")
s, d = call("/api/v1/insights/platform/recompute", {"tenant": T}, tok=SMART)
check("an establishment cannot recompute anybody", s == 403, str(s))
s, d = call("/api/v1/insights/platform/recompute", {"tenant": T}, tok=OPS)
check("support can", s == 200, str(d))

print()
print("── the digest ──────────────────────────────────────────")
s, d = call("/api/v1/insights/digest", {"on": True}, tok=SMART, method="PUT")
check("a person subscribes themselves", s == 200 and d.get("subject") == "owner-live", str(d))
s, d = call("/internal/insights/digest", {"tenant": T})
check("the digest run reports rather than throwing", s == 200, str(d))

print()
print("── erasure ─────────────────────────────────────────────")
s, d = call("/internal/privacy/erase", {"tenant": T, "subject": "ref_nobody00000"})
check("an unknown subject is already absent", s == 200 and d.get("already_absent") is True,
      str(d.get("erased")))
check("and the retention is named rather than implied",
      bool(d.get("retained")), str(d.get("retained"))[:90])

print()
print(f"  {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
PY
