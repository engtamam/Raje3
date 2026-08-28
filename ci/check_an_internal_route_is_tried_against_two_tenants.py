"""Every internal route whose body requires `tenant` must be CALLED, in this service's own test
suite, with at least two DIFFERENT tenant values — proof the suite actually exercises isolation,
not just the happy path of one shop.

WHY THIS EXISTS. `/internal/*` takes `tenant` as a plain field in a JSON body, not off a verified
token (see any internal.py's own header comment — this tier trusts the internal token alone, never
a claim). That means EVERY internal route is, structurally, one dict key away from leaking one
shop's rows into a request that named a different one — and a test suite that only ever posts a
single tenant string can go fully green while never once proving that a second tenant's data stays
out. Phase 4 of the multi-branch work added four such routes in one sitting
(services/bookings/app/api/internal.py's `/bookings` and `/bookings/nearest-real-slot`,
services/operations/app/api/internal.py's `/branch-operators` and `/customer-id-by-phone`) — every
one of them keyed on a `tenant` a caller supplies, none of them re-checked against anything but
that string.

WHAT IT CANNOT PROVE, said plainly, same posture as `check_branch_scope.py`'s own "what it cannot
see": calling a route with two different tenant literals does not by itself prove the ROUTE
refuses to leak — a test could call it twice and never assert non-overlap. What this gate CAN
prove, mechanically, is the necessary half: a route this suite has NEVER called with more than one
tenant literal has certainly never had its isolation demonstrated, whatever else the test does.
This is the same "detectable by shape, not by promise" trade every gate in this family makes.

WHAT IT DELIBERATELY CANNOT SEE, and does not fail on, same rule `check_internal_contracts.py`
already draws for the caller side: a request body built from a variable, a fixture, or a helper
function rather than an inline `json={...}` literal is invisible to this AST walk. Most of this
platform's existing internal-route tests are written that way — real isolation tests the gate
simply cannot read. Those routes are reported SEPARATELY, in yellow, as unverifiable rather than
failed: a gate that fails fifty routes it cannot actually vouch for teaches everyone to ignore it,
which is worse than not existing. Only a route this gate COULD read, and read as posted with
exactly one tenant literal, fails — that is a real, structurally provable gap, not a guess.

    python ci/check_an_internal_route_is_tried_against_two_tenants.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _tenant_required_routes(internal_py: pathlib.Path) -> dict[str, int]:
    """`{route_path: lineno}` for every POST route in this ONE file whose body model requires
    `tenant` (a field with no default at all — pydantic's own definition of required)."""
    tree = ast.parse(internal_py.read_text(encoding="utf-8"))

    models_requiring_tenant: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(isinstance(b, ast.Name) and b.id == "BaseModel" for b in node.bases):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            if stmt.target.id != "tenant":
                continue
            value = stmt.value
            required = value is None
            if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "Field":
                positional_default = bool(value.args) and not (
                    isinstance(value.args[0], ast.Constant) and value.args[0].value is Ellipsis)
                has_default_kw = any(k.arg in ("default", "default_factory")
                                     for k in value.keywords)
                required = not positional_default and not has_default_kw
            if required:
                models_requiring_tenant.add(node.name)

    out: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for deco in node.decorator_list:
            if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                    and deco.func.attr == "post" and deco.args):
                continue
            first = deco.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            for arg in node.args.args + node.args.kwonlyargs:
                ann = getattr(arg.annotation, "id", "")
                if ann in models_requiring_tenant:
                    out["/internal" + first.value] = deco.lineno
    return out


def _tenant_literals_posted(tests_dir: pathlib.Path) -> dict[str, set[str]]:
    """`{route_path: {tenant literals this suite posted to it}}` across every test file."""
    out: dict[str, set[str]] = {}
    if not tests_dir.exists():
        return out
    for path in sorted(tests_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "post"):
                continue
            path_arg = node.args[0] if node.args else None
            route = None
            if isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
                route = path_arg.value
            json_dict = None
            for kw in node.keywords:
                if kw.arg == "json" and isinstance(kw.value, ast.Dict):
                    json_dict = kw.value
            if route is None or json_dict is None:
                continue
            for k, v in zip(json_dict.keys, json_dict.values):
                if (isinstance(k, ast.Constant) and k.value == "tenant"
                        and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                    out.setdefault(route, set()).add(v.value)
    return out


def main() -> int:
    files = sorted(SERVICES.glob("*/app/api/internal.py"))
    if not files:
        print("no service has app/api/internal.py — this gate needs re-pointing")
        return 1

    proven_single_tenant: list[str] = []
    unverifiable: list[str] = []
    proven_ok = 0
    for internal_py in files:
        service = internal_py.parent.parent.parent
        rel = internal_py.relative_to(ROOT).as_posix()
        required = _tenant_required_routes(internal_py)
        if not required:
            continue
        posted = _tenant_literals_posted(service / "tests")
        for route, lineno in sorted(required.items()):
            literals = posted.get(route, set())
            if len(literals) >= 2:
                proven_ok += 1
            elif len(literals) == 1:
                # A REAL, PROVABLE GAP — this gate COULD read the call, and read exactly one
                # tenant, ever, in the whole suite.
                proven_single_tenant.append(f"{rel}:{lineno} {route} — only {sorted(literals)}")
            else:
                # Never seen as an inline `json={...}` literal at all — almost certainly a real
                # test exists, built a way this gate cannot read (see module docstring).
                unverifiable.append(f"{rel}:{lineno} {route}")

    if unverifiable:
        print(f"{C_Y}  ~ {len(unverifiable)} tenant-scoped route(s) this check cannot read — a "
              f"body built from a variable or fixture is a call it cannot vouch for:{C_N}")
        for line in unverifiable:
            print("      " + line)

    if proven_single_tenant:
        print(f"{C_R}An internal route requiring `tenant`, posted with exactly ONE tenant value "
              f"in its own test suite — isolation was never actually demonstrated:{C_N}")
        for line in proven_single_tenant:
            print("  " + line)
        return 1
    print(f"{C_G}every tenant-scoped internal route this check could read was posted with 2+ "
          f"distinct tenants ({proven_ok} proven, {len(unverifiable)} unverifiable, "
          f"{len(files)} services){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
