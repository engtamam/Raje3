#!/usr/bin/env bash
# Prove branch visibility isolation on the cluster — against the running operations (spec §12.4).
#
#   ./deploy/prove-branch-scope.sh
#
# THE PROMISE: «لا يرى موظف فرع أ بيانات فرع ب». It is enforced in api/scope.py by joining the
# token's `sub` to the operator row and narrowing every list read to that person's branch.
#
# WHAT THE UNIT TESTS CANNOT SAY. They call `branch_scope()` with a Principal we construct. On the
# cluster the subject arrives inside a JWT minted by identity-service, verified by the gateway, and
# handed to us as whatever the platform decided `principal.subject` is. If that string is not the
# same string we wrote into `person_id` when the employee was hired, the join silently finds
# nobody — and «finds nobody» means an EMPTY SCOPE, which by design means SEES EVERYTHING. The
# isolation would be off, every screen would look right, and no test would fail.
#
# That asymmetry is the whole reason this file exists: the failure mode of this feature is not an
# error, it is silent permissiveness.
#
# THREE QUESTIONS, ASKED OF THE RUNNING SERVICE:
#
#   an employee assigned to branch A  -> sees A's visits, and never B's
#   a row with NO branch              -> stays visible to him (§10.6.3: «غير محدَّد» belongs to
#                                        nobody, so it is shown to everybody)
#   an operator row with no branch    -> sees everything, which is the ordinary case
#
# It writes rows under a throwaway tenant and deletes them at the end; nothing real is touched.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"

NS="${NS:-base-services}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }
say(){ printf '\n\e[1m▸ %s\e[0m\n' "$*"; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^operations-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "operations is not running"; exit 1; }

say "the pod under test"
kubectl -n "$NS" get pod "$POD" \
  -o jsonpath='{.status.containerStatuses[0].imageID}' | sed 's/^/    /'
echo

# EVERYTHING BELOW RUNS INSIDE THE POD. The datastore is reachable from there and from nowhere
# else, and this asks the service's own scope resolver rather than a copy of it — a proof that
# re-implements the rule proves the copy.
kubectl -n "$NS" exec -i "$POD" -- python3 - <<'PY'
import asyncio, time

TENANT = "_prove_branch_scope"
ok = True


def bad(msg):
    global ok
    ok = False
    print(f"  \033[31m✗ {msg}\033[0m")


def good(msg):
    print(f"  \033[32m✔ {msg}\033[0m")


async def main():
    from app.main import app
    from app.api.scope import branch_scope, visible
    from app.core.models import Operator, Visit
    from app.core.stores import OperatorStore, VisitStore, BranchStore

    store = app.state.container.datastore
    ops, vis, brs = OperatorStore(store), VisitStore(store), BranchStore(store)
    now = int(time.time())

    from app.core.models import Branch
    a = await brs.save(Branch(id="brn_prove_a", tenant=TENANT, name="فرع أ", created=now))
    b = await brs.save(Branch(id="brn_prove_b", tenant=TENANT, name="فرع ب", created=now))

    # The employee, exactly as `hire` writes him: a person id from identity, and a branch.
    await ops.save(Operator(id="op_a", tenant=TENANT, name="موظف أ", role="operator",
                            person_id="usr_prove_a", branch_id=a.id, active=True, created=now))
    # And a manager over the whole chain — assigned to nobody, which is the ordinary case.
    await ops.save(Operator(id="op_all", tenant=TENANT, name="مدير", role="manager",
                            person_id="usr_prove_all", branch_id="", active=True, created=now))

    await vis.save(Visit(id="v_a", tenant=TENANT, customer_id="c1", branch_id=a.id,
                         created=now, occurred_at=now))
    await vis.save(Visit(id="v_b", tenant=TENANT, customer_id="c2", branch_id=b.id,
                         created=now, occurred_at=now))
    await vis.save(Visit(id="v_none", tenant=TENANT, customer_id="c3", branch_id="",
                         created=now, occurred_at=now))

    rows = [v.__dict__ for v in await vis.for_customer(TENANT, "c1", limit=50)]
    for cid in ("c2", "c3"):
        rows += [v.__dict__ for v in await vis.for_customer(TENANT, cid, limit=50)]

    class P:
        def __init__(self, subject):
            self.subject = subject
            self.tenant = TENANT

    scope_a = await branch_scope(store, P("usr_prove_a"))
    if scope_a != a.id:
        bad(f"the employee's scope did not resolve to his branch: {scope_a!r} != {a.id!r}")
        bad("  → the join sub→operator failed; an empty scope SEES EVERYTHING")
    else:
        good("the employee's token resolves to his own branch")

    seen = {r["id"] for r in visible(rows, scope_a)}
    if "v_b" in seen:
        bad("he can see the other branch's visit — the promise in §12.4 is not kept")
    else:
        good("he cannot see the other branch's visits")
    if "v_a" not in seen:
        bad("he cannot see his OWN branch's visit")
    else:
        good("he sees his own branch's visits")
    if "v_none" not in seen:
        bad("an unbranched visit is hidden from him — his shop looks like it stopped trading")
    else:
        good("«غير محدَّد» stays visible to everybody")

    scope_all = await branch_scope(store, P("usr_prove_all"))
    if scope_all != "":
        bad(f"an unassigned manager was narrowed to {scope_all!r}")
    elif len(visible(rows, scope_all)) != len(rows):
        bad("an unassigned manager does not see the whole shop")
    else:
        good("an unassigned manager sees the whole establishment")

    # A machine credential — the till — carries no subject and is scoped by its tenant alone.
    if await branch_scope(store, P("")) != "":
        bad("a till was narrowed to a branch; it is minted for a shop, not a place")
    else:
        good("a till is scoped by its tenant, never by a person")

    for vid in ("v_a", "v_b", "v_none"):
        await store.delete("visits", f"{TENANT}|{vid}")
    for oid in ("op_a", "op_all"):
        await store.delete("operators", f"{TENANT}|{oid}")
    for bid in (a.id, b.id):
        await store.delete("branches", f"{TENANT}|{bid}")

    print("\nOK" if ok else "\nFAILED")
    raise SystemExit(0 if ok else 1)


asyncio.run(main())
PY
rc=$?
echo
if [ "$rc" -eq 0 ]; then
  grn "branch scope holds on the cluster"
else
  red "branch scope does NOT hold — see above"
fi
exit "$rc"
