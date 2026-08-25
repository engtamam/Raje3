#!/usr/bin/env bash
# Bring EXISTING establishments' roles up to the current definitions.
#
#   ./deploy/seed/repair-roles.sh              # every tenant
#   ./deploy/seed/repair-roles.sh --tenant t-1 # one
#   ./deploy/seed/repair-roles.sh --dry-run
#
# WHY THIS IS NOT seed-roles.sh. That script CREATES a tenant's roles and skips any that already
# exist — loudly, and rightly: force-writing every role on every run would silently undo whatever
# an owner customised from the console. It is a seeder, and a seeder must not be a migration.
#
# But a capability ADDED to a role after tenants exist reaches nobody. `compliance.self` was the
# case that made this necessary: not one seeded role had it, so GET /me/legal/outstanding answered
# 403 for every human on the platform and the legal gate could not record a single acceptance. New
# shops get it from the updated seed; the ones already open needed somebody to say so.
#
# SO THIS ADDS, AND NEVER REMOVES. A capability an operator granted by hand survives; one the file
# gained is added. That is the only merge rule that is safe to run unattended — a replace would
# make this the very migration seed-roles.sh refuses to be.
#
# COVERS OUR OWN `_platform` ROLES TOO, NOT ONLY ESTABLISHMENTS'. `operator-roles.json`'s
# `platform-owner` shipped for phases without `members:read`/`members:write` at all (found the same
# way `compliance.self` was: a live account that could add/edit/suspend/remove a member yet never
# list one) — the exact "a capability added after the role already exists reaches nobody" defect
# this script exists for, just on our own tenant instead of a shop's. `roles.json` and
# `operator-roles.json` name their roles from disjoint sets ("owner" vs "platform-owner", …), so
# merging both into one WANT map below is safe with no name collision to arbitrate.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
NS="${NS:-base-services}"

TENANT=""
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tenant) TENANT="${2:-}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) shift ;;
  esac
done

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^authz-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "authz-service is not running"; exit 1; }

TOKEN=$(kubectl -n "$NS" get secret authz-service-secrets \
        -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$TOKEN" ] || { red "no internal token in authz-service-secrets"; exit 1; }

ROLES_JSON=$(python3 -c '
import json, sys
shop = json.load(open(sys.argv[1]))["roles"]
platform = json.load(open(sys.argv[2]))["roles"]
print(json.dumps({"roles": shop + platform}))
' "$ROOT/deploy/seed/roles.json" "$ROOT/deploy/seed/operator-roles.json")

# INSIDE THE POD, over the internal tier. The role store is reachable from there and from nowhere
# else, and `bootstrap` is the one door the platform opened for exactly this trust boundary.
kubectl -n "$NS" exec -i "$POD" -- env TOKEN="$TOKEN" ONLY="$TENANT" DRY="$DRY" \
  ROLES="$ROLES_JSON" python3 - <<'PY'
import asyncio, json, os

TOKEN, ONLY, DRY = os.environ["TOKEN"], os.environ.get("ONLY", ""), os.environ.get("DRY") == "1"
WANT = {r["name"]: set(r["capabilities"]) for r in json.loads(os.environ["ROLES"])["roles"]}


async def main() -> int:
    from app.config import get_settings
    from app.container import build_container

    # THE DATASTORE DIRECTLY, not through RoleStore. The store exposes no bulk write and should
    # not grow one for a repair — a method that rewrites every role is a method somebody reuses.
    c = build_container(get_settings())

    # Every role row, whatever tenant it belongs to. A bounded scan: roles are a handful per shop.
    rows = await c.datastore.scan_all("roles", 20_000)
    # THE SHADOWS FROM THE FIRST ATTEMPT. Rows written under `tenant|id` are unreachable by every
    # reader, so they are noise that makes the next scan lie about what is repaired.
    shadows = 0
    for row in rows:
        rid = row.get("id", "")
        if rid and await c.datastore.get("roles", rid) is None:
            await c.datastore.delete("roles", f"{row.get('tenant','')}|{rid}")
            shadows += 1
    if shadows:
        print(f"  removed {shadows} unreachable row(s) written by an earlier attempt")
        rows = await c.datastore.scan_all("roles", 20_000)

    touched = missing = 0
    for row in rows:
        tenant, name = row.get("tenant", ""), row.get("name", "")
        if ONLY and tenant != ONLY:
            continue
        want = WANT.get(name)
        if want is None:
            continue
        have = set(row.get("capabilities") or [])
        # ADD ONLY — see the header. An operator's hand-granted capability is not ours to remove.
        add = want - have
        if not add:
            continue
        missing += len(add)
        touched += 1
        print(f"  {tenant} · {name}: + {', '.join(sorted(add))}")
        if not DRY:
            row["capabilities"] = sorted(have | want)
            # THE KEY IS THE ROLE ID ALONE — `RoleStore.create` does `put(_ROLES, r.id, …)`, with
            # no tenant prefix. This was written as `f"{tenant}|{id}"` from memory, and the result
            # was the worst kind of wrong: a SHADOW row under a key nothing reads. A scan reported
            # every role repaired, `effective` kept answering from the original, and the 403 stayed
            # — with the evidence saying it was fixed. Guessing a key is guessing a schema.
            await c.datastore.put("roles", row["id"], row)

    print(f"\n  {touched} role(s) updated, {missing} capabilit(ies) added"
          + ("  [dry run — nothing written]" if DRY else ""))
    return 0


raise SystemExit(asyncio.run(main()))
PY
rc=$?
[ $rc -eq 0 ] && grn "existing establishments now hold what the definitions say" \
              || red "the repair did not complete — see above"
exit $rc
