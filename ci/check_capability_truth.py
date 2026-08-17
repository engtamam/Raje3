#!/usr/bin/env python3
"""The capability a route DECLARES is the capability its handler ENFORCES.

WHAT THIS CATCHES, AND WHY NOTHING ELSE DID. Our services declare each user-facing route as an
action carrying a capability, and the completeness gate checks two things about it: that the route
exists, and that the service advertises the capability. Both can be true while the number is wrong.

Every one of our six services declared its operator surface — secrets and runtime config — under
`platform.<service>`, while `api/v1/operator.py` requires `platform.secrets` and `platform.config`.
Thirty-six actions. The console renders each button for whoever holds the declared capability, and
the service answers 403 to every one of them. Nothing fails at build, nothing fails at boot, and
the person who finds it is an operator during an incident, at the moment they most need the button.

The declared capability is not documentation. It is what the console filters on, what an operator
is granted in order to do a job, and what a reviewer reads when asking who can reach what. A wrong
one is a wrong answer to all three.

HOW IT READS THE TRUTH. The handler's requirement is `require_capability("...")` bound to a module
level dependency and attached to a route via `dependencies=[Depends(_NAME)]`. This resolves that
binding statically — no imports, no app startup — so it runs anywhere and cannot be defeated by an
import that happens to fail.

WHAT IT DELIBERATELY DOES NOT DO. It does not check routes with no capability dependency at all;
those are public or internal, and a separate gate owns them. It reports only a MISMATCH, which is
the case with a right answer.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"
problems: list[str] = []
checked = 0


def enforced_by_route(service: Path) -> dict[tuple[str, str], str]:
    """(METHOD, path) -> the capability the handler actually requires.

    Read from the router source: the prefix on the APIRouter, the dependency names bound to
    require_capability(...), and which of those names each route lists.
    """
    out: dict[tuple[str, str], str] = {}
    # EVERY ROUTE FILE, NOT JUST `v1/`. This globbed `app/api/v1/*.py` and the routes that
    # matter most are not all there: `portal/app/api/page.py` serves the customer's own public
    # page and carries `Depends(rate_limit)` — the very shape this gate was written to guard —
    # and each service's `internal.py` sits outside too. A guard scoped by DIRECTORY rather than
    # by what it is guarding is a guard whose coverage depends on where somebody filed a file.
    for py in sorted((service / "app" / "api").rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue

        # NAME -> capability, from `_SECRETS = require_capability("platform.secrets")`
        bound: dict[str, str] = {}
        prefix = ""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            fn = node.value.func
            name = getattr(fn, "id", "") or getattr(fn, "attr", "")
            if name == "require_capability" and node.value.args:
                arg = node.value.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            bound[t.id] = arg.value
            elif name == "APIRouter":
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = str(kw.value.value)

        if not bound:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                fn = dec.func
                method = getattr(fn, "attr", "").upper()
                if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    continue
                path = ""
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    path = str(dec.args[0].value)
                cap = ""
                for kw in dec.keywords:
                    if kw.arg != "dependencies" or not isinstance(kw.value, ast.List):
                        continue
                    for el in kw.value.elts:
                        # Depends(_SECRETS)
                        if isinstance(el, ast.Call) and el.args:
                            inner = el.args[0]
                            if isinstance(inner, ast.Name) and inner.id in bound:
                                cap = bound[inner.id]
                # Also the `principal = Depends(_OWNER)` form, where the guard is an argument.
                if not cap:
                    for arg in list(node.args.args) + list(node.args.kwonlyargs):
                        pass
                    for default in list(node.args.defaults) + list(node.args.kw_defaults):
                        if isinstance(default, ast.Call) and default.args:
                            inner = default.args[0]
                            if isinstance(inner, ast.Name) and inner.id in bound:
                                cap = bound[inner.id]
                if cap:
                    # THE PREFIX IS SOMETIMES ALREADY ABSOLUTE. Some routers carry
                    # prefix="/api/v1/operator" and others carry "/subscription" under a parent that
                    # supplies /api/v1. Prepending unconditionally produced /api/v1/api/v1/... and
                    # matched nothing — so this check reported green over thirty-six real mismatches.
                    # A resolver that finds nothing and a system with nothing wrong print the same
                    # line, which is the failure mode every one of these gates has to avoid.
                    full = f"{prefix}{path}"
                    if not full.startswith("/api/v1"):
                        full = f"/api/v1{full}"
                    out[(method, full)] = cap
    return out


def declared_by_actions(service: Path) -> list[tuple[str, str, str, str]]:
    """(id, METHOD, path, capability) from admin_actions and user_actions."""
    out = []
    for name in ("admin_actions.py", "user_actions.py"):
        f = service / "app" / name
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8")
        for block in re.findall(r"\{[^{}]*?\"path\"[^{}]*?\}", src, re.S):
            def field(k: str) -> str:
                m = re.search(rf'"{k}":\s*"([^"]*)"', block)
                return m.group(1) if m else ""
            path, cap = field("path"), field("capability")
            if path and cap:
                out.append((field("id"), field("method").upper() or "GET", path, cap))
    return out


def normalise(path: str) -> str:
    """FastAPI's {name} and an action's {name} are the same slot under different names."""
    return re.sub(r"\{[^}]*\}", "{}", path)


for svc in sorted(p for p in SERVICES.iterdir() if (p / "app").is_dir()):
    enforced = {(m, normalise(p)): c for (m, p), c in enforced_by_route(svc).items()}
    for action_id, method, path, declared in declared_by_actions(svc):
        key = (method, normalise(path))
        actual = enforced.get(key)
        if actual is None:
            # No capability dependency on that route: public, internal, or guarded another way.
            # Not this check's business — a separate gate owns route coverage.
            continue
        checked += 1
        if actual != declared:
            problems.append(
                f"{svc.name}/{action_id}: declares `{declared}` and the handler enforces "
                f"`{actual}` — the console renders this for whoever holds the first, and the "
                f"service answers 403 to every one of them")

if problems:
    print(f"{C_R}  ✗ {len(problems)} capability mismatch(es):{C_N}")
    for p in problems:
        print(f"    {C_R}{p}{C_N}")
    sys.exit(1)
print(f"{C_G}  ✔ every declared capability is the one its handler enforces "
      f"({checked} action(s) checked against the routers){C_N}")
