#!/usr/bin/env bash
# The retention sweep — against the running cluster.
#
#   ./deploy/prove-retention.sh
#
# WHY THIS EXISTS RATHER THAN ONLY UNIT TESTS. The sweep DELETES, and it deletes on nobody's
# instruction — no request, no operator, no ticket. Three things about it are facts about the
# deployment rather than about the code, and each one fails silently:
#
#   the CronJob exists and points at a route that answers. A cron aimed at a 404 is a retention
#   policy that never runs, and nothing anywhere reports it;
#
#   the route is reachable ONLY with the internal token;
#
#   and — the one that matters — a shop still inside its grace loses nothing. That is the assertion
#   this whole task is about, and it is made here against the real store, the real erasure code and
#   the real settings, not against fakes we wrote.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"

NS="${NS:-base-services}"

red(){ printf '  \e[31m%s\e[0m\n' "$*" >&2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^operations-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "operations is not running"; exit 1; }

INTERNAL=$(kubectl -n "$NS" get secret operations-secrets \
           -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$INTERNAL" ] || { red "no INTERNAL_SERVICE_TOKEN"; exit 1; }

fails=0

# ── the CronJob, which is the only thing that ever calls this ────────────────────────────────
CRON=$(kubectl -n "$NS" get cronjob -o name 2>/dev/null | grep -c 'operations-retention')
if [ "$CRON" -lt 1 ]; then
  red "! no retention CronJob — the policy is code that nothing runs"
  fails=1
else
  printf '  ok the retention CronJob exists\n'
fi

# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS.
kubectl -n "$NS" exec -i "$POD" -- python - "$INTERNAL" <<'PY'
import asyncio, json, sys, time, urllib.error, urllib.request
internal = sys.argv[1]
H = "http://localhost:8000"
SWEEP = "/internal/operations/retention/sweep"

def call(path, token=internal):
    h = {"X-Internal-Token": token} if token else {}
    r = urllib.request.Request(H + path, data=b"{}", method="POST", headers=h)
    r.add_header("Content-Type", "application/json")
    try:
        u = urllib.request.urlopen(r, timeout=120)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"_raw": e.read().decode()[:300]}

fails = []

s, out = call(SWEEP, token=None)
if s != 401:
    fails.append("the sweep answered " + str(s) + " WITHOUT a token — a deletion route open to the mesh")
else:
    print("  ok the sweep is internal-only")

s, out = call(SWEEP)
if s != 200:
    fails.append("the sweep answered " + str(s) + ": " + json.dumps(out)[:200])
else:
    print("  ok the sweep runs: " + json.dumps(out))

# ── THE ASSERTION THIS TASK IS ABOUT, against the real store ─────────────────────────────────
# A customer recorded TODAY, in a tenant that exists only for this check. Whatever the cluster
# believes about that tenant's subscription — and it believes nothing, because it has none — the
# sweep must leave the number alone. An establishment inside its grace loses nothing.
from app.main import app                        # noqa: E402
from app.core.models import CUSTOMERS           # noqa: E402
from app.core.pii import subject_ref            # noqa: E402
from app.config import get_settings             # noqa: E402

store = app.state.container.datastore
tenant = "prove-retention-" + str(int(time.time()))
phone = "0500000001"
row = {"id": "c1", "tenant": tenant, "phone": phone, "name": "اختبار",
       "subject_ref": subject_ref(get_settings().PII_SALT, tenant, phone),
       "last_visit": int(time.time()), "created": int(time.time())}
asyncio.get_event_loop().run_until_complete(store.put(CUSTOMERS, tenant + "|c1", row))

s, out = call(SWEEP)
back = asyncio.get_event_loop().run_until_complete(store.get(CUSTOMERS, tenant + "|c1")) or {}
if not back.get("phone"):
    fails.append("A CUSTOMER RECORDED TODAY WAS ERASED BY THE SWEEP: " + json.dumps(back, ensure_ascii=False))
else:
    print("  ok a customer of an establishment inside its grace is untouched")
asyncio.get_event_loop().run_until_complete(store.delete(CUSTOMERS, tenant + "|c1"))

print("")
for f in fails:
    print("  ! " + f)
if not fails:
    print("  the sweep runs, refuses the unauthenticated caller, and deletes nobody it should not")
sys.exit(1 if fails else 0)
PY
[ $? -eq 0 ] && [ "$fails" -eq 0 ]
