"""Every route in a service's `app/api/internal.py` must require the internal token.

WHY THIS EXISTS. `/internal/*` is the ONE tier on this platform with no user identity behind it at
all — no capability check, no branch scope, nothing but `X-Internal-Token` standing between a
request and a peer's own data (see any internal.py's own header comment: "NOT user-facing.
Guarded by a shared token compared in CONSTANT TIME... Never a user JWT"). A route added to this
file without `Depends(require_internal_token)` is not locked tighter or looser than intended by a
mistake anyone would notice at review — FastAPI serves it exactly the same either way, the route
answers 200, and the only difference is which caller the answer was ever meant for.

Phase 4 of the multi-branch work (services/bookings/app/api/internal.py's `/bookings` and
`/bookings/nearest-real-slot`, services/operations/app/api/internal.py's `/branch-operators` and
`/customer-id-by-phone`) added FOUR of these in one sitting — a real customer_id and a real
booking write, guarded by nothing but this one dependency. This gate exists so the next four are
checked by a machine before a reviewer has to notice it by eye, the same posture
`check_a_route_with_no_token_is_open_at_the_door.py` already takes for the opposite direction (a
route that MEANT to be open, locked shut).

WHAT IT DOES. For every `@router.<verb>(...)` decorator in every service's `app/api/internal.py`,
require a `dependencies=[..., Depends(require_internal_token), ...]` keyword carrying that exact
call somewhere in the list — recognised by SHAPE (a `Depends(require_internal_token)` call
anywhere in the list), not by position, so a route that also depends on something else still
passes.

    python ci/check_an_internal_route_forgets_the_token.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

_VERBS = {"get", "post", "put", "patch", "delete"}
_GUARD_NAME = "require_internal_token"


def _is_router_route_decorator(dec: ast.expr) -> bool:
    return (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
            and dec.func.attr in _VERBS and isinstance(dec.func.value, ast.Name)
            and dec.func.value.id == "router")


def _carries_the_guard(dec: ast.Call) -> bool:
    for kw in dec.keywords:
        if kw.arg != "dependencies" or not isinstance(kw.value, ast.List):
            continue
        for elt in kw.value.elts:
            if (isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name)
                    and elt.func.id == "Depends" and elt.args
                    and isinstance(elt.args[0], ast.Name) and elt.args[0].id == _GUARD_NAME):
                return True
    return False


def _route_label(dec: ast.Call) -> str:
    if dec.args and isinstance(dec.args[0], ast.Constant):
        return f"{dec.func.attr.upper()} {dec.args[0].value}"    # type: ignore[union-attr]
    return f"{dec.func.attr.upper()} <path not a literal>"       # type: ignore[union-attr]


def main() -> int:
    files = sorted(SERVICES.glob("*/app/api/internal.py"))
    if not files:
        print("no service has app/api/internal.py — this gate needs re-pointing")
        return 1

    unguarded: list[str] = []
    checked = 0
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            print(f"cannot parse {rel}: {exc}")
            return 1
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                if not _is_router_route_decorator(dec):
                    continue
                checked += 1
                if not _carries_the_guard(dec):
                    unguarded.append(f"{rel}:{dec.lineno} {_route_label(dec)} ({node.name})")

    if unguarded:
        print(f"{C_R}An internal route with no token requirement — reachable by anyone who can "
              f"reach the service at all:{C_N}")
        for line in sorted(unguarded):
            print("  " + line)
        return 1
    print(f"{C_G}every internal route requires the internal token ({checked} routes across "
          f"{len(files)} services){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
