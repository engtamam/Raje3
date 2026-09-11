#!/usr/bin/env bash
# Seed the price list into billing-service.
#
#   ./deploy/seed/seed-plans.sh                 # create what is missing ONLY — never touches
#                                                # a plan already on the cluster, matched or not
#   ./deploy/seed/seed-plans.sh --sync          # ALSO correct any existing plan that has drifted
#                                                # from the file (prices/limits/trial/etc.)
#   ./deploy/seed/seed-plans.sh --dry-run       # preview a create-only pass, change nothing
#   ./deploy/seed/seed-plans.sh --sync --dry-run  # preview a create+correct pass, change nothing
#   ./deploy/seed/seed-plans.sh --retire-strays # ALSO unlist a listed plan the file no longer
#                                                # names (independent of --sync; nothing deleted)
#
# WHY A SCRIPT AND NOT A MIGRATION — the same reason as roles and templates. Pricing is content:
# somebody wants a different message allowance on a Tuesday because a customer asked. A migration
# makes that a deploy, and a price that needs a deploy is a price nobody changes.
#
# --sync IS OPT-IN NOW, AND THAT IS A REVERSAL — the owner's own report (2026-09-11): the console
# grew a real live-edit path for a plan's price/limits/trial/credit_percent_of_price
# (apps/console/src/admin/PlanCards.tsx's own edit drawer, built well after this script's original
# "the file IS the price list, correcting is the point" reasoning) — so a plan the cluster
# disagrees with the file on is no longer reliably drift; it might be exactly the live edit an
# operator just made through the console, and the DEFAULT bare run used to silently revert it on
# the next seed. The default is now the safe half only (create what plans.json adds that the
# cluster has never heard of at all — a genuinely new plan is never a live edit, there is nothing
# to conflict with); reconciling plans.json back onto the cluster is now a deliberate act, behind
# its own flag, exactly so nobody's live pricing tweak gets quietly overwritten by running this
# for an unrelated reason (a new plan, a stray retirement).
#
# NOBODY WHO ALREADY BOUGHT IS REPRICED, either pass. billing snapshots price and limits onto the
# subscription at signup and GRANDFATHER defaults to on, so changing a plan here changes what NEW
# subscribers get. Moving an existing customer is a separate, deliberate act (migrate_terms) — as
# it should be: silently changing what somebody already agreed to pay is the failure customers
# escalate rather than report.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

HERE="$(cd "$(dirname "$0")" && pwd)"
NS="${NS:-base-services}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

DRY=0
SYNC=0
RETIRE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --sync) SYNC=1 ;;
    # UNLIST WHAT WE NO LONGER SELL. Separate from --sync and never implied by it: a listed plan
    # is a thing a shop can still buy, and hiding one is a commercial decision — so it is its own
    # flag, not a side effect of correcting a price. It UNLISTS and never deletes: an
    # establishment already subscribed keeps its plan, its limits and its invoice; it simply
    # stops being on offer.
    --retire-strays) RETIRE=1 ;;
    *) red "unknown argument: $arg (expected --dry-run / --sync / --retire-strays)"; exit 2 ;;
  esac
done

FILE="$HERE/plans.json"
[ -f "$FILE" ] || { red "no $FILE"; exit 2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^billing-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "billing-service is not running"; exit 1; }

# A SIGNED TOKEN, NOT THE INTERNAL ONE. /api/v1/plans is a user-tier route: the internal token
# authenticates a service, and creating the price list is administration.
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > "$HERE/.seed-key.pem"
chmod 600 "$HERE/.seed-key.pem"
# THE kid HEADER — see seed-roles.sh's own note on this exact fix. A token minted with none is
# rejected by every JWKS verifier on this fleet (PyJWKClient has no single-key fallback, whatever
# the driver's own comment assumes); this thumbprints the SAME key it signs with, matching
# identity-service's own kid derivation (signing_keyring.py's `public_jwk`), so it works across a
# rotation with no code change.
TOKEN=$(python3 -c '
import base64, hashlib, json, jwt, sys, time
from jwt.algorithms import RSAAlgorithm
now = int(time.time())
private_pem = open(sys.argv[1]).read()
key_obj = RSAAlgorithm(RSAAlgorithm.SHA256).prepare_key(private_pem)
jwk = json.loads(RSAAlgorithm.to_jwk(key_obj))
canonical = json.dumps({"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]},
                       separators=(",", ":"), sort_keys=True).encode("ascii")
kid = base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode("ascii")
print(jwt.encode({"sub": "seed-plans", "tenant": "_platform",
                  "caps": ["platform.billing", "billing.manage"],
                  "iss": "raje3", "aud": "raje3", "iat": now,
                  # SHORT. It can rewrite the price list; it lives for one run.
                  "exp": now + 300},
                 private_pem, algorithm="RS256", headers={"kid": kid}), end="")' "$HERE/.seed-key.pem")
rm -f "$HERE/.seed-key.pem"
case "$TOKEN" in
  ey*) : ;;
  *) red "minting failed; got a ${#TOKEN}-character value that is not a JWT"; exit 1 ;;
esac

echo "seeding plans.json into billing-service"
# NO BACKTICKS AND NO COMMAND SUBSTITUTION ANYWHERE BELOW THIS LINE, INCLUDING IN COMMENTS.
# The heredoc is unquoted because it interpolates the file, so the SHELL evaluates any it finds
# before python ever sees it. This has happened, mid-seed, from a word in a comment.
kubectl -n "$NS" exec -i "$POD" -- python - "$TOKEN" "$DRY" "$RETIRE" "$SYNC" <<PY
import json, sys, urllib.error, urllib.request
token, dry, retire, sync = sys.argv[1], sys.argv[2] == "1", sys.argv[3] == "1", sys.argv[4] == "1"
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
for plan in LIB["plans"]:
    name = plan["name"]
    # OPT-IN, NOT DEFAULTED — `credit_percent_of_price` (billing-service v0.19.20) turns on the
    # percent-of-price included-allowance grant for THIS plan only; a plan that never sets it
    # keeps its previous behaviour (a static `credits` limit, or none) untouched. Read as `False`
    # for every plan that has never named it, so an old row with no opinion never drifts.
    want = {"name": name, "prices": price_of(plan), "limits": plan["limits"],
            "trial_days": plan.get("trial_days", 0),
            "credit_percent_of_price": bool(plan.get("credit_percent_of_price", False))}
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
    if (cur.get("limits") or {}) != want["limits"]:
        drift.append("limits")
    if (cur.get("prices") or []) != want["prices"]:
        drift.append("price")
    if int(cur.get("trial_days") or 0) != int(want["trial_days"]):
        drift.append("trial")
    if bool(cur.get("credit_percent_of_price", False)) != want["credit_percent_of_price"]:
        drift.append("credit_percent_of_price")
    if not drift:
        print("  = " + name + " matches the file")
        same += 1
        continue
    # WITHOUT --sync, A DRIFTED PLAN IS ONLY NAMED, NEVER TOUCHED — it might be a live console
    # edit (PlanCards.tsx), not a stale file. See this script's own header on why the default
    # stopped correcting existing plans.
    if not sync:
        print("  ? " + name + " differs: " + ", ".join(drift) + " — left as-is (run --sync to correct)")
        continue
    if dry:
        print("  ~ " + name + " differs: " + ", ".join(drift))
        corrected += 1
        continue
    s, res = call("/api/v1/billing/plans/" + cur["id"],
                  {"prices": want["prices"], "limits": want["limits"],
                   "trial_days": want["trial_days"],
                   "credit_percent_of_price": want["credit_percent_of_price"]}, method="PATCH")
    if s < 400:
        print("  ^ " + name + " corrected: " + ", ".join(drift))
        corrected += 1
    else:
        print("  ! " + name + " " + str(s) + " " + str(res))
        failed += 1

# ── WHAT IS ON THE PRICING PAGE THAT IS NOT IN THIS FILE ─────────────────────────────────────
# Reported, never retired. Two different things end up listed and subscribable without being in
# the price list, and they need opposite treatment:
#
#   leftovers  - the platform's bootstrap plans (starter, pro_smart) and anything a proof script
#                created and forgot to retire. Four of these were live and subscribable on the
#                public pricing page beside our three, and nobody had looked.
#   deliberate - a plan negotiated for one customer (16.4.1). Those are UNLISTED, which is why
#                this only looks at listed ones.
#
# It is a report because retiring a plan somebody is subscribed to is not a thing a seed script
# may decide.
KNOWN = {p["name"] for p in LIB["plans"]}
stray = [p for p in have.values()
         if p.get("active") and p.get("listed") and p.get("name") not in KNOWN]
if stray:
    print("")
    print("  ON THE PUBLIC PRICING PAGE AND NOT IN plans.json:")
    for p in stray:
        print("    ? " + str(p.get("name")) + "  (" + str(p.get("id")) + ")")
    if not retire:
        print("    Retire what is a leftover; a negotiated plan should be unlisted, not listed.")
        print("    Run with --retire-strays to unlist them (nothing is deleted).")
    for p in stray:
        if not retire:
            break
        if dry:
            print("    - " + str(p.get("name")) + " would be unlisted")
            continue
        s, _ = call("/api/v1/billing/plans/" + str(p.get("id")) + "/availability",
                    {"listed": False})
        if s < 300:
            print("    - " + str(p.get("name")) + " unlisted")
            corrected += 1
        else:
            print("    ! " + str(p.get("name")) + " could not be unlisted: " + str(s))
            failed += 1

print("")
print("created=" + str(created) + " corrected=" + str(corrected)
      + " unchanged=" + str(same) + " failed=" + str(failed))
sys.exit(1 if failed else 0)
PY
