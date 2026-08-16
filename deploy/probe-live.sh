#!/usr/bin/env bash
# ==================================================================================================
#  probe-live.sh — "the endpoint exists" and "the endpoint works" are different claims.
# --------------------------------------------------------------------------------------------------
#  Everything in ci/check_deploy_wiring.py reads FILES. This calls the running cluster, because the
#  failure class it catches leaves every file correct and every probe green:
#
#    * thirteen services gained a backup export endpoint and three of seventeen could produce an
#      archive. The rest answered a bare 503 for a missing shared secret. The fleet looked covered
#      while most of it could not produce anything restorable.
#    * webhook-service's erasure endpoint returned 500 on EVERY request — it had never worked once
#      — and nothing in any file said so.
#    * a monitoring stack installed its dashboards, missed its exporter, and watched nothing. Green
#      everywhere.
#
#  So this asks each service, in turn, to actually do the thing it claims. It is the check that
#  belongs AFTER a rollout, next to verify-pinned.sh: that one proves the right bytes are running,
#  this one proves they answer.
#
#  Usage:  sudo bash deploy/probe-live.sh
# ==================================================================================================
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
NS="${NS:-base-services}"

C_G=$'\e[32m'; C_R=$'\e[31m'; C_D=$'\e[2m'; C_N=$'\e[0m'
pass=0; fail=0

# Run from INSIDE a pod: these are internal-tier endpoints on a default-deny network, and reaching
# them from the host would prove something about the host rather than about the cluster.
POD="$(kubectl -n "$NS" get pod -l app.kubernetes.io/name=backup-service -o name 2>/dev/null | head -1)"
[ -n "$POD" ] || { echo "no backup-service pod to probe from"; exit 2; }
TOKEN="$(kubectl -n "$NS" get secret backup-service-secrets -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' | base64 -d)"

# Every service that answers an internal contract. Derived from the values directory rather than a
# hand-kept list, so a service added tomorrow is probed without anyone remembering to add it.
mapfile -t SERVICES < <(ls "$(dirname "$0")"/services/*.values.yaml 2>/dev/null \
  | xargs -r -n1 basename | sed 's/\.values\.yaml$//' | grep -v '^api-gateway$')

cat > /tmp/_probe.py <<'PY'
import json, os, sys, urllib.error, urllib.request

TOKEN = os.environ["TOKEN"]
SERVICES = os.environ["SERVICES"].split()

def call(host, path, body):
    req = urllib.request.Request(
        f"http://{host}:8000{path}", data=json.dumps(body).encode(),
        headers={"X-Internal-Token": TOKEN, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0

# Two contracts, and both were broken in production while every file was correct.
#
# 404 is a PASS, not a failure: it means the service does not implement this contract, which is a
# legitimate answer (search-service is a declared backup exemption — a derived index holds no
# durable data). What this catches is a service that CLAIMS the contract and cannot honour it.
for label, path, body in (
    ("backup export", "/internal/backup/export", {}),
    ("privacy erase", "/internal/privacy/erase", {"tenant": "probe", "subject": "probe-subject"}),
):
    ok, broken, absent = [], [], []
    for svc in SERVICES:
        code = call(svc, path, body)
        if code == 200:
            ok.append(svc)
        elif code in (404, 405):
            absent.append(svc)
        else:
            broken.append(f"{svc}:{code}")
    print(f"{label}|{len(ok)}|{len(SERVICES)}|{','.join(broken)}|{','.join(absent)}")
PY

kubectl -n "$NS" cp /tmp/_probe.py "${POD#pod/}:/tmp/_probe.py" >/dev/null 2>&1 \
  || { kubectl -n "$NS" exec -i "$POD" -- sh -c 'cat > /tmp/_probe.py' < /tmp/_probe.py; }

OUT="$(kubectl -n "$NS" exec "$POD" -- env TOKEN="$TOKEN" SERVICES="${SERVICES[*]}" \
      python3 /tmp/_probe.py 2>/dev/null)"

while IFS='|' read -r label n total broken absent; do
  [ -n "$label" ] || continue
  if [ -z "$broken" ]; then
    echo -e "  ${C_G}✔ ${label}: ${n} answering, $(echo "$absent" | tr ',' ' ' | wc -w) not implementing${C_N}"
    pass=$((pass+1))
  else
    # NAMED, with the status code. "some services are failing" sends an operator reading logs;
    # "wallet:503" sends them to the shared secret in one step.
    echo -e "  ${C_R}✗ ${label}: ${n}/${total} answering — BROKEN: ${broken}${C_N}"
    fail=$((fail+1))
  fi
done <<< "$OUT"

echo
if [ $fail -eq 0 ]; then
  echo -e "  ${C_G}every declared contract answers on the running cluster${C_N}"
else
  echo -e "  ${C_R}${fail} contract(s) claimed and not honoured — a file check cannot see this${C_N}"
fi
exit $fail
