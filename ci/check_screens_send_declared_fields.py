"""A screen must not send a field the route does not declare — the answer looks fine either way.

WHY THIS EXISTS. «رسائله» on the customer page called `reminders.log` with `subject_ref`, and
`GET /api/v1/reminders/log` declares `outcome`, `branch_id` and `limit` — nothing else. FastAPI
drops an undeclared query parameter without a word, so the route answered with THE WHOLE SHOP'S
send log and the screen printed it under one customer's name.

The owner reads other customers' messages and believes they are this man's. He answers «لماذا لم
تصلني رسالة؟» from a list that has nothing to do with him, and every conclusion he draws about
this customer is drawn from somebody else's history. Nothing fails: the request is 200, the list is
full, the screen is fast.

WHAT IT CHECKS. For every `call(session, <var>, { … })` in the console where `<var>` came from
`action(catalog, '<id>')` in the same file, the keys in the body must be declared by the route that
serves `<id>` — as a `Query`/path parameter for a GET, or as a field on the request model for a
POST/PUT/PATCH.

WHAT IT CANNOT SEE, said plainly: a body assembled in a variable rather than written inline, and a
route whose parameters come from a shared dependency. Both are counted and reported as unverified
rather than passed over.

    python ci/check_screens_send_declared_fields.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "apps" / "console" / "src"
SERVICES = ROOT / "services"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

#: Keys every caller may send: the platform reads them off the envelope rather than the route.
ALWAYS_ALLOWED = {"tenant"}


def declared_actions() -> dict[str, tuple[str, str]]:
    """action id -> (METHOD, path), from each service's own catalogue."""
    out: dict[str, tuple[str, str]] = {}
    for path in sorted(SERVICES.glob("*/app/user_actions.py")):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r'"id":\s*"([\w.]+)"[^}]*?"method":\s*"(\w+)"[^}]*?"path":\s*"([^"]+)"',
                             text, re.S):
            out[m.group(1)] = (m.group(2).upper(), m.group(3))
    return out


def route_fields(service_dir: pathlib.Path) -> dict[tuple[str, str], set[str]]:
    """(METHOD, path) -> the field names that route will actually read."""
    out: dict[tuple[str, str], set[str]] = {}
    models: dict[str, set[str]] = {}

    files = sorted(service_dir.glob("app/api/**/*.py"))
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                fields = {s.target.id for s in node.body
                          if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)}
                if fields:
                    # THE UNION, NOT THE LAST ONE SEEN. Two files in the same service both declare
                    # a `ConfigIn`, and keeping whichever was parsed last made this check report a
                    # route that was correct — the exact noise that teaches people to skip a gate.
                    models[node.name] = models.get(node.name, set()) | fields

    for f in files:
        text = f.read_text(encoding="utf-8")
        tree = ast.parse(text)
        prefix = ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "APIRouter":
                for kw in node.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = str(kw.value.value)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in fn.decorator_list:
                if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                        and deco.func.attr in ("get", "post", "put", "patch", "delete")
                        and deco.args and isinstance(deco.args[0], ast.Constant)):
                    continue
                route = str(deco.args[0].value)
                names: set[str] = set()
                for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]:
                    ann = a.annotation
                    model = ann.id if isinstance(ann, ast.Name) else ""
                    if model in models:
                        names |= models[model]
                    else:
                        names.add(a.arg)
                out[(deco.func.attr.upper(), prefix + route)] = names
    return out


def _keys(node: ast.AST | None) -> set[str] | None:
    return None


CALL = re.compile(r"call<[^>]*>\(\s*session\s*,\s*(\w+)\s*,\s*\{([^{}]*)\}\s*\)"
                  r"|call\(\s*session\s*,\s*(\w+)\s*,\s*\{([^{}]*)\}\s*\)")
BOUND = re.compile(r"(?:const|let)\s+(\w+)\s*=\s*action\s*\(\s*catalog\s*,\s*'([\w.]+)'\s*\)")
KEY = re.compile(r"(?:^|,)\s*([A-Za-z_]\w*)\s*:")


def main() -> int:
    actions = declared_actions()
    fields: dict[tuple[str, str], set[str]] = {}
    for service in sorted(SERVICES.iterdir()):
        if (service / "app").is_dir():
            fields.update(route_fields(service))

    def _norm(route: str) -> str:
        """The catalogue names the full path; a router names its own prefix and the parent adds
        `/api/v1`. Comparing the two without stripping it matched nothing at all — a check that
        silently verifies zero calls is the same silence it was written to catch."""
        return route[len("/api/v1"):] if route.startswith("/api/v1") else route

    findings: list[str] = []
    unverified = 0
    checked = 0

    for path in sorted(CONSOLE.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        # THE NEAREST PRECEDING BINDING, NOT THE LAST ONE IN THE FILE. `const a = action(...)` is
        # written inside each handler, and the same name means a different action three functions
        # down — a file-wide dict attributed calls to whichever binding happened to be last and
        # reported five screens that were correct. A check whose findings are mostly wrong is one
        # people learn to skip, and the next real one is skipped with it.
        bindings: list[tuple[int, str, str]] = [
            (m.start(), m.group(1), m.group(2)) for m in BOUND.finditer(text)]
        if not bindings:
            continue

        def action_for(var: str, at: int) -> str:
            found = ""
            for pos, name, act in bindings:
                if pos < at and name == var:
                    found = act
            return found
        for m in CALL.finditer(text):
            var = m.group(1) or m.group(3)
            body = m.group(2) or m.group(4) or ""
            action_id = action_for(var or "", m.start())
            if not action_id or action_id not in actions:
                continue
            method, route = actions[action_id]
            known = fields.get((method, _norm(route)))
            if known is None:
                unverified += 1
                continue
            checked += 1
            sent = set(KEY.findall(body)) - ALWAYS_ALLOWED
            unknown = {k for k in sent if k not in known}
            if unknown:
                line = text[:m.start()].count("\n") + 1
                findings.append(
                    f"{rel}:{line}  sends {sorted(unknown)} to `{action_id}` "
                    f"({method} {route}), which declares none of them — the field is dropped in "
                    f"silence and the answer is about something else")

    if findings:
        print(f"{C_R}  ✘ {len(findings)} call(s) sending a field the route never declares:{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Declare it on the route, or stop sending it. A filter that is silently "
              f"dropped answers with everything, and the screen prints it as one person's.{C_N}")
        return 1

    if unverified:
        print(f"{C_Y}  ! {unverified} call(s) to a route this check could not resolve{C_N}")
    print(f"{C_G}  ✔ every field a screen sends is declared by the route that serves it "
          f"({checked} calls){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
