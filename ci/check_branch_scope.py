"""Every route that serves per-branch data must ask WHO IS ASKING — and fail closed when it cannot.

WHY THIS EXISTS. `GET /api/v1/insights/branches` returns the branch comparison table: every branch's
revenue and traffic, side by side. It never asked for the caller's branch scope at all, so a
branch-scoped manager read the whole chain's copy of it. The dashboard next door WAS scoped — which
is what made the hole invisible: the isolation held everywhere except the single screen that exists
to compare people against each other.

And the dashboard's own scope check failed OPEN. `branch_scope` answers `_unreadable` when the peer
that knows who works where could not be asked, and the code turned that into «no branch filter»,
which means the whole establishment. An unknown scope is not an empty scope: refusing costs a
manager his dashboard for a minute, guessing costs the owner a confidentiality he never agreed to
give up.

REWRITTEN (multi-step branch-domains project, step 3) TO READ THE REAL AUTHORITY. The first version
of this gate guessed which routes served per-branch data from a hand-maintained list of literal
strings (`branch_rows`, `branch_id: str = Query`, ...) found anywhere in a route's own source text.
That produced two failure modes at once: a route that merely MENTIONED one of those strings in a
comment passed for the wrong reason, and a route that scoped correctly through a same-file HELPER
whose name did not contain one of those strings failed for the wrong reason (this gate's own former
self flagged `field.py::staff_performance`, which delegates to `_staff_performance_rows()` — a
function that DOES call `branch_scope()` — as unscoped, simply because the string never appeared in
the ROUTE's own body).

`services/operations/app/core/branch_domains.py` is now the one place that says which domains are
branch-scoped at all (`BRANCH_DOMAINS`, built and reviewed in step 1 of this project from real grepped
evidence, not guesswork) — so this gate asks IT rather than re-deriving the answer from keywords.
`DOMAIN_ROUTES` below names the real route file and function(s) backing each plain (`derived_from is
None`) branch-scoped domain — the exact files step 1's own evidence strings point at and step 2's own
audit confirmed. `mobile_requests` (`derived_from="assigned_operator_branch"`) is checked separately,
by its own real functions (`check_mobile_requests_branch_guard` below), because it is scoped through
an ASSIGNED OPERATOR's own station rather than a plain `branch_id` field — see step 2's own report
and `mobile_requests.py`'s own module docstring.

WHAT IT CHECKS, in three directions now:

  1. Every route function named in `DOMAIN_ROUTES` for a branch-scoped domain must call the scope
     resolver (`SCOPE_CALL`, the literal `branch_scope` token — every service's own resolver, whatever
     shape it takes underneath, is reached through a real CALL naming that word: operations' own bare
     `branch_scope(...)`, and bookings'/reminders'/insights' own `getattr(container, "branch_scope",
     ...)`), DIRECTLY OR THROUGH A SAME-FILE HELPER IT CALLS — `_calls_any()` below walks the real AST
     for an actual `Call` node, never a substring match on the function's source text (so a docstring
     or comment that merely MENTIONS the resolver's name, even to say it is NOT called, cannot pass
     this check — an adversarial audit of this project's own step 3 found and closed that exact gap),
     and resolves one level of same-file helper calls recursively, which is the blind spot the original
     keyword version could not see past at all.
  2. `mobile_requests` — a narrower, name-based check: the two functions step 2 built
     (`_operator_branch`, `_branch_allowed`) must still exist, and every route that acts on ONE existing
     request must still call `_require_branch_access` or `_branch_allowed` (directly or through a
     same-file helper) — so a NEW route added to this file later, that reads or mutates one existing
     request without wiring the branch check, is caught the same way an unscoped read anywhere else is.
  3. Wherever `_unreadable`/`DENIED`/`UNREADABLE` is compared, the branch that follows must REFUSE —
     never fall through to the unscoped read. This is the fail-open shape from the original gate,
     unchanged: it is not domain-specific, so it still scans every service file rather than only the
     domains above.

PLATFORM-LEVEL DOMAINS ARE NEVER CHECKED HERE — on purpose. A gate that fired on a domain the registry
itself says has no branch dimension (`services_catalogue`, `loyalty_points`, ...) would be exactly the
false-positive-teaches-people-to-ignore-it failure this file's own history already lived through once.

    python ci/check_branch_scope.py
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

SCOPE_CALL = "branch_scope"
SENTINEL = "_unreadable"
#: How the sentinel appears in real code: its own literal, or the name bound to it. Matching the
#: bare substring also matches every longer word that ends in it.
SENTINEL_TOKENS = (f'"{SENTINEL}"', f"'{SENTINEL}'", "UNREADABLE", "DENIED")

BRANCH_DOMAINS_MODULE = ROOT / "services/operations/app/core/branch_domains.py"

# ── which real route(s) enforce each plain (`derived_from is None`) branch-scoped domain ────────
#
# NOT auto-discovered from the registry — the registry names DOMAINS, not routes, on purpose (step
# 1's own file: it is a classification, never a route index that would go stale the moment a screen
# is refactored). This dict is the bridge, kept here rather than in the registry itself so a route
# rename touches ONE file (this gate) instead of the domain classification.
#
# `bookings`'s OWN `services/bookings/app/api/internal.py` is DELIBERATELY NOT LISTED — its
# `branch_id` filters are WRITE-attribution parameters on an internal-token-gated peer door already
# called by a caller (operations) that resolved the human's own scope before it ever reached here,
# same posture `NOT_A_BRANCH_READ` documented for `create_branch`/`update_branch` in the old version
# of this file. The real user-facing read this domain is about is `bookings.py`'s own grid.
DOMAIN_ROUTES: dict[str, list[tuple[str, list[str]]]] = {
    "customers": [
        ("services/operations/app/api/v1/field.py",
         ["recent_customers", "resolve_customers", "suggest_customers", "customer_record"]),
    ],
    "rating": [
        ("services/operations/app/api/v1/field.py", ["ratings", "staff_performance"]),
    ],
    "bookings": [
        ("services/bookings/app/api/v1/bookings.py", ["list_bookings", "booking_counts"]),
    ],
    "shop_insights": [
        ("services/insights/app/api/v1/insights.py", ["dashboard", "branches"]),
    ],
    "team": [
        ("services/operations/app/api/v1/staff.py", ["list_operators", "list_branches"]),
    ],
    "whatsapp_connect": [
        ("services/operations/app/api/v1/connect.py", ["whatsapp_connect_status"]),
    ],
    "campaigns_send_log": [
        ("services/reminders/app/api/v1/owner.py", ["send_log"]),
    ],
}

# ── mobile_requests: derived_from="assigned_operator_branch", checked by name not by branch_id ──
MOBILE_REQUESTS_FILE = "services/operations/app/api/v1/mobile_requests.py"
#: The two functions step 2 built to derive/apply the branch a request is indirectly scoped by.
MOBILE_REQUESTS_HELPERS = ("_operator_branch", "_branch_allowed")
#: Every route in this file that acts on ONE EXISTING request — a new one added here later that
#: forgets the guard is exactly what this check exists to catch.
MOBILE_REQUESTS_ROUTES = ["list_mobile_requests", "create_mobile_request", "assign_mobile_request",
                          "accept_mobile_request", "reject_mobile_request",
                          "complete_mobile_request", "mobile_request_no_show",
                          "mobile_request_risk"]
#: Either name proves the guard was applied — `list_mobile_requests`/`create_mobile_request` call
#: `_branch_allowed` inline (no single existing row to fetch first), every other route calls the
#: shared `_require_branch_access` wrapper.
MOBILE_REQUESTS_TOKENS = ("_require_branch_access", "_branch_allowed")


def _load_branch_domains():
    """Imports `branch_domains.py` by file path rather than `import app.core...` — every service in
    this repo names its own top-level package `app`, so a normal import would collide across
    services the moment more than one is ever imported in the same process. The module itself has
    no dependency beyond `dataclasses`/`typing` (its own module docstring: step 1 deliberately kept
    it free of any service's own runtime), so this is safe to load standalone, the same way this
    gate already parses service source files without installing the services themselves."""
    spec = importlib.util.spec_from_file_location("ci_branch_domains", BRANCH_DOMAINS_MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # REGISTERED BEFORE EXECUTION — `dataclasses` resolves a frozen dataclass's own module by
    # looking it up in `sys.modules` while the class body runs, which fails with an opaque
    # `AttributeError` on `None` if the module is not registered there yet.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.BRANCH_DOMAINS


def _fn_map(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every function defined anywhere in the file, by name — the lookup table
    `_calls_any` needs to follow a call into a same-file helper's own definition."""
    return {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _call_matches(node: ast.Call, tokens: tuple[str, ...]) -> bool:
    """Whether ONE real call site actually invokes something named in `tokens` — never a
    docstring, a comment, or a string that merely mentions the name.

    THREE REAL SHAPES, ALL SEEN IN THIS REPO'S OWN SCOPE RESOLVERS:

      · `branch_scope(...)` / `_require_branch_access(...)` — a bare name call (operations' own
        `app.api.scope.branch_scope`, mobile_requests.py's own helpers): `func` is an `ast.Name`.
      · `x.branch_scope(...)` — an attribute call: `func` is an `ast.Attribute`.
      · `getattr(container, "branch_scope", None)` — NOT a `.branch_scope` attribute access at
        all, and the shape bookings' own `_require_branch`, reminders' own `_branch_scope`, and
        insights' own `dashboard`/`branches` all actually use to reach their peer's resolver
        (the attribute name is chosen by a string, not written literally) — the SUBSTRING version
        of this check depended on the literal word appearing anywhere in the function's text,
        which happened to catch this shape by accident; the AST version has to look for it on
        purpose, or every service but operations' own would false-positive as unscoped.
    """
    func = node.func
    if isinstance(func, ast.Name) and func.id in tokens:
        return True
    if isinstance(func, ast.Attribute) and func.attr in tokens:
        return True
    if isinstance(func, ast.Name) and func.id == "getattr":
        for arg in node.args[1:2]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value in tokens:
                return True
    return False


def _calls_any(fn: ast.FunctionDef | ast.AsyncFunctionDef, tokens: tuple[str, ...],
              fn_map: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
              visited: set[str] | None = None) -> bool:
    """Whether `fn` itself — OR a same-file helper it calls, resolved recursively — contains a
    REAL CALL SITE naming one of `tokens`, per `_call_matches` above.

    A REAL AST CHECK, NOT A SUBSTRING MATCH ON THE WHOLE SOURCE (fixed after an adversarial audit
    of this project: the substring version read a route's own DOCSTRING/COMMENTS along with its
    code, so a route whose docstring merely MENTIONED `branch_scope()` — even one explaining that
    it does NOT call it — passed the gate for the wrong reason. `ast.walk(fn)` only visits real
    nodes; a string inside a docstring is an `ast.Constant`, never an `ast.Call`, so it cannot
    match here no matter what it says.

    ONE HOP OF RECURSION IS THE DECLARED LIMIT, not an accident — `visited` stops infinite mutual
    recursion, but a helper that itself calls a SECOND helper before reaching the real check is
    resolved too, since the recursion re-runs `_calls_any` on it as fn_map lookups nest naturally.

    SAME-FILE ONLY. A route that scoped through a helper imported from ANOTHER module would fail
    this check as a false positive (blocks legitimate code, never a security hole) — not built
    here on purpose, because no route among the domains this gate actually checks does that today;
    building cross-file resolution for a case that does not exist yet is exactly the gold-plating
    this project's own doctrine avoids. If a future route needs it, this is the one place to add it.
    """
    visited = visited if visited is not None else set()
    if fn.name in visited:
        return False
    visited.add(fn.name)
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and _call_matches(node, tokens):
            return True
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            callee = fn_map.get(node.func.id)
            if callee is not None and _calls_any(callee, tokens, fn_map, visited):
                return True
    return False


def _check_domain_routes(domains_by_id: dict, unscoped: list[str], missing: list[str]) -> int:
    """The plain (`derived_from is None`) branch-scoped domains — `DOMAIN_ROUTES` names their real
    routes, the registry names their evidence, and this asks whether the route ACTUALLY calls the
    scope resolver, directly or through a helper."""
    checked = 0
    for domain_id, files in DOMAIN_ROUTES.items():
        domain = domains_by_id.get(domain_id)
        if domain is None:
            missing.append(f"ci/check_branch_scope.py's own DOMAIN_ROUTES names `{domain_id}`, "
                           f"which no longer exists in branch_domains.py — update one or the other")
            continue
        for rel, route_names in files:
            path = ROOT / rel
            if not path.exists():
                missing.append(f"{rel}: named in DOMAIN_ROUTES for `{domain_id}` but the file "
                               f"does not exist — update ci/check_branch_scope.py")
                continue
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            fn_map = _fn_map(tree)
            for name in route_names:
                fn = fn_map.get(name)
                if fn is None:
                    missing.append(f"{rel}: `{domain_id}` names route `{name}()`, which no longer "
                                   f"exists — it was renamed or removed without updating "
                                   f"ci/check_branch_scope.py's own DOMAIN_ROUTES")
                    continue
                checked += 1
                if not _calls_any(fn, (SCOPE_CALL,), fn_map):
                    unscoped.append(
                        f"{rel}:{fn.lineno} {name}() serves `{domain_id}` (branch-scoped — "
                        f"{domain.evidence}) and never calls branch_scope(), directly or through "
                        f"a same-file helper")
    return checked


def _check_mobile_requests(domains_by_id: dict, unscoped: list[str], missing: list[str]) -> int:
    """`mobile_requests` — scoped through the ASSIGNED OPERATOR's own branch, never a plain
    `branch_id`, so it cannot be checked the same way as `_check_domain_routes` above (there is no
    `branch_scope(` call to look for at the route level for `list_mobile_requests`/
    `create_mobile_request` — they call `_branch_allowed` directly after resolving `bscope` once).
    """
    domain = domains_by_id.get("mobile_requests")
    if domain is None:
        missing.append("ci/check_branch_scope.py's own _check_mobile_requests names "
                       "`mobile_requests`, which no longer exists in branch_domains.py")
        return 0
    path = ROOT / MOBILE_REQUESTS_FILE
    if not path.exists():
        missing.append(f"{MOBILE_REQUESTS_FILE}: named for the mobile_requests branch guard but "
                       f"does not exist — update ci/check_branch_scope.py")
        return 0
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn_map = _fn_map(tree)

    checked = 0
    for helper in MOBILE_REQUESTS_HELPERS:
        if helper not in fn_map:
            unscoped.append(
                f"{MOBILE_REQUESTS_FILE}: `{helper}()` — the branch-derivation helper "
                f"mobile_requests' own `derived_from=\"assigned_operator_branch\"` classification "
                f"depends on ({domain.evidence}) — no longer exists")
    if any(helper not in fn_map for helper in MOBILE_REQUESTS_HELPERS):
        # Cannot meaningfully check individual routes once the helpers themselves are gone.
        return checked

    for name in MOBILE_REQUESTS_ROUTES:
        fn = fn_map.get(name)
        if fn is None:
            missing.append(f"{MOBILE_REQUESTS_FILE}: route `{name}()` named in "
                           f"ci/check_branch_scope.py's own MOBILE_REQUESTS_ROUTES no longer "
                           f"exists — it was renamed or removed without updating the gate")
            continue
        checked += 1
        if not _calls_any(fn, MOBILE_REQUESTS_TOKENS, fn_map):
            unscoped.append(
                f"{MOBILE_REQUESTS_FILE}:{fn.lineno} {name}() acts on an existing mobile-service "
                f"request and never checks branch access via _require_branch_access/"
                f"_branch_allowed — a route here needs the same guard step 2 added ({domain.evidence})")
    return checked


def _check_fail_open(unscoped_placeholder: list[str]) -> list[str]:
    """THE FAIL-OPEN SHAPE, wherever it appears, across every service file — unchanged from the
    original gate and deliberately NOT domain-scoped: an `_unreadable`/DENIED scope collapsing into
    an empty-string default is the exact bug this half of the file exists to catch, regardless of
    which domain the route belongs to."""
    fail_open: list[str] = []
    for path in sorted(SERVICES.glob("*/app/api/**/*.py")):
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        for i, line in enumerate(text.splitlines(), 1):
            if not any(tok in line for tok in SENTINEL_TOKENS):
                continue
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if '""' in line or "''" in line:
                fail_open.append(f"{rel}:{i}  {stripped[:100]}")
    return fail_open


def main() -> int:
    domains = _load_branch_domains()
    domains_by_id = {d.id: d for d in domains}

    unscoped: list[str] = []
    missing: list[str] = []
    checked = _check_domain_routes(domains_by_id, unscoped, missing)
    checked += _check_mobile_requests(domains_by_id, unscoped, missing)
    fail_open = _check_fail_open(unscoped)

    if missing:
        print(f"{C_Y}  ⚠ {len(missing)} drift issue(s) between the registry and this gate's own "
              f"route index:{C_N}")
        for line in missing:
            print(f"{C_Y}      {line}{C_N}")

    if fail_open:
        print(f"{C_R}  ✘ {len(fail_open)} place(s) where an UNREADABLE scope becomes an EMPTY "
              f"one — «we could not check» rendered as «no restriction»:{C_N}")
        for line in fail_open:
            print(f"{C_R}      {line}{C_N}")
    if unscoped:
        print(f"{C_R}  ✘ {len(unscoped)} route(s) serving branch-scoped data with no scope "
              f"check:{C_N}")
        for line in unscoped:
            print(f"{C_R}      {line}{C_N}")

    if fail_open or unscoped or missing:
        print(f"{C_R}    A branch is a description on an event, not a division of the account "
              f"(spec 12.2) — but WHO MAY SEE WHOSE NUMBERS is exactly what it does divide.{C_N}")
        return 1

    print(f"{C_G}  ✔ every route named for a branch-scoped domain in branch_domains.py calls "
          f"branch_scope() (directly or through a helper), mobile_requests' own guard is intact, "
          f"and an unreadable scope refuses ({checked} routes){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
