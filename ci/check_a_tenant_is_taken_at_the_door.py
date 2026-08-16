#!/usr/bin/env python3
"""A REQUEST'S TENANT IS ESTABLISHED AT THE DOOR, OR THE REQUEST IS REFUSED.

`Principal.tenant` is `str | None`. It is None whenever the bearer token carries no tenant claim —
a platform-level token, an operator's token, a machine token minted for the fleet rather than for
one shop. And `require_capability` checks CAPABILITIES ONLY: it has never looked at the tenant, so
such a token reaches any tenant surface whose capability it happens to hold.

WHAT THAT COSTS, MEASURED RATHER THAN ASSUMED. Both datastores fail CLOSED on a read: a memory
`find` with `{"tenant": None}` matches nothing, and postgres turns it into `value @> '{"tenant":
null}'`, which matches only rows whose tenant is literally null. So this is not a cross-tenant read.

It is worse in a quieter way. The same None flows into the WRITE side:

    key = f"{principal.tenant}|{campaign_id}"     ->  "None|c1"
    Campaign(tenant=principal.tenant, ...)        ->  a row whose tenant is None

That row is real, it is stored, and it belongs to nobody. No tenant-scoped read will ever return
it, no owner will ever see it, no export will carry it, and — the part that matters — no erasure
will ever reach it, because an erasure fans out per tenant. It is data we hold on somebody with no
establishment attached and no path to deletion. Every audit line for that call names no shop
either, so the ledger cannot answer «who did this, and to whom».

Nothing fails while this happens. That is the whole reason it needs a gate rather than a fix: the
defect leaves no error, no empty screen and no failing test — only a row nobody can reach.

────────────────────────────────────────────────────────────────────────────────────────────────
THE RULE, AND WHY IT NEEDS NO EXCEPTIONS TABLE

A handler may read `.tenant` off a principal only inside a function that REFUSES when it is
absent. The guard is recognised by its SHAPE, not by its name and not by a list kept here: a
function that reads `.tenant` and also raises is establishing the tenant; one that reads it and
cannot raise is assuming it.

That is what makes the rule total. The guard each service already has — `_tenant(p)`, four lines,
`raise HTTPException(403, "NO_TENANT")` — passes on its own merits. So does any future one, in any
service, under any name, as long as it can say no. And a handler that wants the raw value has
exactly one honest way to get it, which is to ask a function that can refuse.

`context.py::tenant_scope` returns `principal.tenant` deliberately and may be None — it is the
datastore SCOPE, and scoping a query to None is the fail-closed direction. It passes this gate for
the same structural reason everything else does: see below, it is a return of the attribute rather
than a use of it in a key, a filter or a record. A gate that banned it would be banning the one
place the value is allowed to be absent.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The attribute that carries a request's establishment.
FIELD = "tenant"


def _accounted_for(tree: ast.AST) -> set[int]:
    """Every `principal.tenant` whose ABSENCE the surrounding code has visibly reckoned with.

    Three shapes, and all three are structural — there is no list of blessed callers here, which
    is what keeps this rule total:

      returned          `return principal.tenant` hands the unknown onward AS unknown. That is
                        `context.py::tenant_scope`, the datastore scope seam: a query scoped to
                        None matches nothing, which is the fail-closed direction.
      reported          a value in a dict literal — `{"tenant": principal.tenant}` in `whoami`.
                        The route's whole job is to say who the caller is; answering «no tenant»
                        is the true answer, not an assumption about one.
      defaulted aloud   `principal.tenant or X`. The writer SAW that it can be absent and wrote
                        down what to do — `operator.py` derives an audit pseudonym and platform
                        staff genuinely have no shop, with `principal.subject` carrying identity.
                        Written-down is the opposite of assumed, which is all this gate asks.
    """
    safe: set[int] = set()
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Attribute):
            if sub.value.attr == FIELD:
                safe.add(id(sub.value))
        elif isinstance(sub, ast.Dict):
            for value in sub.values:
                if isinstance(value, ast.Attribute) and value.attr == FIELD:
                    safe.add(id(value))
        elif isinstance(sub, ast.BoolOp) and isinstance(sub.op, ast.Or):
            for value in sub.values:
                if isinstance(value, ast.Attribute) and value.attr == FIELD:
                    safe.add(id(value))
    return safe


def _reads_tenant(node: ast.AST, safe: set[int]) -> list[int]:
    """Lines where the request's tenant is USED without its absence being reckoned with.

    A use is a key, a filter, a constructor argument, an audit field — anywhere None silently
    becomes part of a row. `self.tenant` and `row.tenant` are a stored row's own field and are
    not the request's, so the receiver is named.
    """
    used: list[int] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == FIELD and id(sub) not in safe:
            if isinstance(sub.value, ast.Name) and sub.value.id in ("principal", "p"):
                used.append(sub.lineno)
    return used


def _can_refuse(fn: ast.AST) -> bool:
    """Does this function stop when the tenant is absent? A guard is one that can say no.

    TWO SHAPES OF NO, AND BOTH ARE THIS REPOSITORY'S. A guard may raise — `_tenant(p)` in
    field.py and staff.py, four lines and a 403. Or it may RETURN a refusal, which the till
    routes do on purpose and say why: the platform strips a raised exception's detail on the way
    out, so a till that is not bound to a shop reads a bare 500 instead of an answer it can show
    at the counter. `{"found": False}` is a refusal that survives the trip.

    So the test is: a branch that tests the tenant's absence and, inside it, leaves the function.
    Deliberately blind to WHAT is raised or returned — demanding `HTTPException(403)` by name
    would be a list of approved spellings, which is an exceptions table wearing a different coat.
    What matters is that the path exists where the request stops.
    """
    for sub in ast.walk(fn):
        if not isinstance(sub, ast.If):
            continue
        test = sub.test
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            test = test.operand
        if isinstance(test, ast.Compare):
            test = test.left
        if not (isinstance(test, ast.Attribute) and test.attr == FIELD):
            continue
        if any(isinstance(leaf, (ast.Raise, ast.Return)) for leaf in ast.walk(sub)):
            return True
    return False


def main() -> int:
    bad: list[str] = []
    checked = 0
    for service in sorted((ROOT / "services").iterdir()):
        api = service / "app" / "api"
        if not api.is_dir():
            continue
        for path in sorted(api.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, OSError) as exc:
                # REPORTED, NEVER SKIPPED. A file this gate cannot parse is the one file where the
                # defect could live forever with the build printing «ok» over it.
                bad.append(f"{rel}: unreadable ({exc})")
                continue
            checked += 1
            safe = _accounted_for(tree)
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if _can_refuse(fn):
                    continue
                for line in _reads_tenant(fn, safe):
                    bad.append(f"{rel}:{line}: `{fn.name}` uses the request's tenant without "
                               f"establishing it — None here becomes a row nobody owns")

    if bad:
        print(f"{C_R}a request's tenant is being assumed rather than established{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Take it through a guard that refuses when it is absent — the four-line")
        print("  `_tenant(principal)` each service already has, or one like it.")
        return 1
    print(f"{C_G}ok{C_N}  {checked} files — every tenant is established at the door")
    return 0


if __name__ == "__main__":
    sys.exit(main())
