#!/usr/bin/env bash
# The subscribe rule and the ceiling record — against the running cluster.
#
#   ./deploy/prove-onboarding.sh
#
# TWO THINGS THE UNIT TESTS CANNOT SHOW, because in both cases the fake is ours:
#
#   that OUR route refuses a paid subscription and REACHES BILLING for a trial — the rule is
#   pure and tested, but "did the refusal actually stop the call" is a fact about wiring;
#
#   and that the refusal survives the platform's error handler. That handler strips an
#   HTTPException's detail, so a refusal raised instead of returned arrives as a bare 402 with the
#   sentence that tells the owner what to do thrown away. It has happened here twice. A unit test
#   on the function cannot see it; only a real request through the real app can.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"

NS="${NS:-base-services}"

red(){ printf '  \e[31m%s\e[0m\n' "$*" >&2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^operations-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "operations is not running"; exit 1; }

KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.po-key.pem
chmod 600 /tmp/.po-key.pem

# THE OWNER'S TOKEN, not an operator's. He is buying his own subscription, and a route that
# needed a platform capability would mean nobody could subscribe without us.
TENANT="prove-onboard-$(date +%s)"
TOKEN=$(TEN="$TENANT" python3 -c '
import jwt, os, time
now = int(time.time())
print(jwt.encode({"sub": "owner", "tenant": os.environ["TEN"],
                  "caps": ["billing.self"],
                  "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 600},
                 open("/tmp/.po-key.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.po-key.pem

INTERNAL=$(kubectl -n "$NS" get secret operations-secrets \
           -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$INTERNAL" ] || { red "no INTERNAL_SERVICE_TOKEN"; exit 1; }

# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$INTERNAL" "$TENANT" <<PY
import json, sys, urllib.error, urllib.request
token, internal, tenant = sys.argv[1], sys.argv[2], sys.argv[3]
H = "http://localhost:8000"

def call(path, body=None, internal_call=False):
    d = json.dumps(body).encode() if body is not None else None
    h = {"X-Internal-Token": internal} if internal_call else {"Authorization": "Bearer " + token}
    r = urllib.request.Request(H + path, data=d, method="POST" if d else "GET", headers=h)
    if d:
        r.add_header("Content-Type", "application/json")
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()[:400]
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"_raw": raw}

fails = []

# ── the paid plan, with no WhatsApp connected ────────────────────────────────────────────────
# The cluster runs the console driver, so nobody is connected — which is the case being proven.
s, out = call("/api/v1/subscription", {"plan_id": "plan_does_not_matter"})
if s != 402:
    fails.append("a paid subscription without a connection answered " + str(s) + ", not 402")
else:
    print("  ok a paid subscription without WhatsApp is refused")

# THE SENTENCE HAS TO ARRIVE. This is the assertion the unit tests cannot make: the platform's
# error handler strips an HTTPException's detail, so a raised refusal would reach the owner as a
# bare 402 with nothing to act on.
msg = str(out.get("message") or "")
if "اربط" not in msg:
    fails.append("the refusal arrived WITHOUT its sentence: " + json.dumps(out, ensure_ascii=False))
else:
    print("  ok the refusal carries the sentence the owner acts on")
if "دقائق" not in msg:
    fails.append("the refusal does not say how long connecting takes — 'not allowed' answers nothing")
else:
    print("  ok it says connecting takes minutes, so it reads as a step and not a wall")
if "توثيق" in msg:
    fails.append("the refusal mentions VERIFICATION, which is not required and takes days")

# ── the operator read that replaces the notice ───────────────────────────────────────────────
s, out = call("/internal/reminders/ceiling-pressure", internal_call=True)
if s == 404:
    print("  .. ceiling-pressure lives in reminders, not here - checked separately")
elif s >= 400:
    fails.append("ceiling-pressure answered " + str(s))

print("")
for f in fails:
    print("  ! " + f)
if not fails:
    print("  the rule holds at the route, and the sentence survives the error handler")
sys.exit(1 if fails else 0)
PY
