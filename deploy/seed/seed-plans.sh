#!/usr/bin/env bash
# Seed the price list into billing-service.
#
#   ./deploy/seed/seed-plans.sh              # create what is missing, correct what has drifted
#   ./deploy/seed/seed-plans.sh --dry-run    # print the differences, change nothing
#
# WHY A SCRIPT AND NOT A MIGRATION — the same reason as roles and templates. Pricing is content:
# somebody wants a different message allowance on a Tuesday because a customer asked. A migration
# makes that a deploy, and a price that needs a deploy is a price nobody changes.
#
# AND THIS ONE CORRECTS RATHER THAN SKIPS, which is the opposite of seed-roles.sh — deliberately.
# A role is customised in the console by design, so overwriting one destroys somebody's work. A
# plan is not: the file IS the price list, and a plan on the cluster that disagrees with it is
# drift, not a customisation. Correcting it is the point of running this again.
#
# NOBODY WHO ALREADY BOUGHT IS REPRICED. billing snapshots price and limits onto the subscription
# at signup and GRANDFATHER defaults to on, so changing a plan here changes what NEW subscribers
# get. Moving an existing customer is a separate, deliberate act (migrate_terms) — as it should be:
# silently changing what somebody already agreed to pay is the failure customers escalate rather
# than report.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

FILE="$HERE/plans.json"
[ -f "$FILE" ] || { red "no $FILE"; exit 2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^billing-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "billing-service is not running"; exit 1; }

# A SIGNED TOKEN, NOT THE INTERNAL ONE. /api/v1/plans is a user-tier route: the internal token
# authenticates a service, and creating the price list is administration.
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.seed-key.pem
chmod 600 /tmp/.seed-key.pem
TOKEN=$(python3 -c '
import jwt, time
now = int(time.time())
print(jwt.encode({"sub": "seed-plans", "tenant": "_platform",
                  "caps": ["platform.billing", "billing.manage"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  # SHORT. It can rewrite the price list; it lives for one run.
                  "exp": now + 300},
                 open("/tmp/.seed-key.pem").read(), algorithm="RS256"), end="")')
rm -f /tmp/.seed-key.pem
case "$TOKEN" in
  ey*) : ;;
  *) red "minting failed; got a ${#TOKEN}-character value that is not a JWT"; exit 1 ;;
esac

echo "seeding plans.json into billing-service"
# NO BACKTICKS AND NO COMMAND SUBSTITUTION ANYWHERE BELOW THIS LINE, INCLUDING IN COMMENTS.
# The heredoc is unquoted because it interpolates the file, so the SHELL evaluates any it finds
# before python ever sees it. This has happened, mid-seed, from a word in a comment.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$DRY" <<PY
import json, sys, urllib.error, urllib.request
token, dry = sys.argv[1], sys.argv[2] == "1"
H = "http://localhost:8000"
LIB = json.loads('''$(cat "$FILE")''')
CURRENCY = LIB["currency"]

def call(path, body=None, method=None):
    d = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(H + path, data=d, method=method or ("POST" if d else "GET"),
                               headers={"Authorization": "Bearer " + token})
    if d:
        r.add_header("Content-Type", "application/json")
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

def pack_limits(pack):
    """A pack carries ONE key and nothing else.

    Everything the plan grants — seats, branches, features — must come from the plan alone. A pack
    that also carried feature.campaigns would silently grant it for as long as the pack existed,
    which is a 50-riyal upgrade to a plan he did not buy.
    """
    return {"messages.monthly": {"kind": "counter", "limit": int(pack["messages"]),
                                 "period": "billing_period", "overage": "block"}}


def price_of(plan, interval="month"):
    # ONE PRICE PER PRODUCT, VAT-INCLUSIVE. No yearly interval exists anywhere in this file
    # and that is a decision, not an omission: annual billing was deferred until we want to sell
    # it, and a year price sitting unused in the price list is a year price somebody eventually
    # subscribes somebody to by accident.
    return [{"interval": interval, "amount_minor": plan["amount"], "currency": CURRENCY,
             "type": "flat", "includes_tax": True}]

s, out = call("/api/v1/billing/plans?include_hidden=true")
if s >= 400:
    print("  ! could not read the current plans:", s, out)
    sys.exit(1)
have = {p.get("name"): p for p in (out.get("plans") or [])}

created = corrected = same = failed = 0
# PLANS AND PACKS ARE THE SAME KIND OF ROW, which is the point of the design rather than a
# shortcut. A pack is a subscription with interval once carrying only messages.monthly, and
# billing's entitlement is the union of every billable subscription — so the pack's messages add
# to the plan's with no arithmetic of ours and no branch in the sending code. Proven against the
# running service by deploy/prove-packs.sh: a plan of 2 plus a pack of 3 answers 5, and what he
# already sent stays counted.
#
# The panel tells them apart by the price's interval, not by a flag we invent: month is a plan,
# once is a pack. A flag would be a second source of truth for something the price already says.
PRODUCTS = ([dict(p, _kind="plan") for p in LIB["plans"]]
            + [dict(p, _kind="pack") for p in LIB.get("packs") or []])

for plan in PRODUCTS:
    name = plan["name"]
    is_pack = plan["_kind"] == "pack"
    want = {"name": name,
            "prices": price_of(plan, interval="once" if is_pack else "month"),
            "limits": pack_limits(plan) if is_pack else plan["limits"],
            "trial_days": 0 if is_pack else plan.get("trial_days", 0)}
    cur = have.get(name)
    if cur is None:
        if dry:
            print("  + " + name + " would be created")
            created += 1
            continue
        s, res = call("/api/v1/billing/plans", want)
        if s < 400:
            print("  + " + name + " created " + str(res.get("id", "")))
            created += 1
            # A hidden plan is hidden in a SECOND call: create takes no availability, by design —
            # listed is an operator decision rather than a property of the price list.
            if plan.get("listed") is False:
                s2, _ = call("/api/v1/billing/plans/" + res["id"] + "/availability", {"listed": False})
                print("    " + ("unlisted" if s2 < 400 else "COULD NOT UNLIST: " + str(s2)))
        else:
            print("  ! " + name + " " + str(s) + " " + str(res))
            failed += 1
        continue

    # DRIFT IS COMPARED FIELD BY FIELD rather than by re-sending blindly, so a run that changes
    # nothing says so. A seeder that reports "4 updated" every time it runs is a seeder whose
    # output nobody reads.
    drift = []
    if (cur.get("limits") or {}) != plan["limits"]:
        drift.append("limits")
    if (cur.get("prices") or []) != want["prices"]:
        drift.append("price")
    if int(cur.get("trial_days") or 0) != int(want["trial_days"]):
        drift.append("trial")
    if not drift:
        print("  = " + name + " matches the file")
        same += 1
        continue
    if dry:
        print("  ~ " + name + " differs: " + ", ".join(drift))
        corrected += 1
        continue
    s, res = call("/api/v1/billing/plans/" + cur["id"],
                  {"prices": want["prices"], "limits": want["limits"],
                   "trial_days": want["trial_days"]}, method="PATCH")
    if s < 400:
        print("  ^ " + name + " corrected: " + ", ".join(drift))
        corrected += 1
    else:
        print("  ! " + name + " " + str(s) + " " + str(res))
        failed += 1

print("")
print("created=" + str(created) + " corrected=" + str(corrected)
      + " unchanged=" + str(same) + " failed=" + str(failed))
sys.exit(1 if failed else 0)
PY
