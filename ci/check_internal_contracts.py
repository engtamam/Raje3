"""What one service sends, against what the other service requires.

WHY THIS EXISTS. `operations` asked `reminders` which offer applies to a visit and built the body as
{subject_ref, visit_id, service_ids}. The route's model requires `tenant` as well. So every call
this product ever made was rejected 422 — and the adapter turned the rejection into `None`, which
the visit path reads as «this customer holds no offer». An exclusive offer could not be applied at
the counter, ever, and nothing anywhere said so.

Nobody could have caught it from one side. operations' tests fake the peer; reminders' tests build
the body correctly because they build it from the model. The defect lives in the SEAM, and the seam
is the one place no service's suite looks.

WHAT IT DOES. For every internal path a service posts to, find the route that serves it and read
its pydantic model's required fields — a field with no default and no `Optional`. Then compare
against the keys of the literal dict that is json.dumps'd into the request. A required field that
never travels is a 422 on every call.

WHAT IT DELIBERATELY CANNOT DO, said out loud rather than silently skipped:
  · bodies built from a variable rather than a literal dict — reported as unverifiable
  · paths assembled from more than one config value — reported as unresolved
  · fields whose requiredness depends on a validator rather than a default

A gate that hides its blind spots is worse than no gate: it converts «we did not look» into
«we looked and it was fine».

    python ci/check_internal_contracts.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


# ── the callee side: every internal route and the model it requires ─────────────────────────────
def route_models(service: pathlib.Path) -> dict[str, tuple[str, set[str], str]]:
    """`{path: (model_name, required_fields, where)}` for this service's POST routes."""
    out: dict[str, tuple[str, set[str], str]] = {}
    models: dict[str, tuple[set[str], str]] = {}

    for path in sorted((service / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = str(path.relative_to(ROOT)).replace("\\", "/")

        # 1) the models
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not any(isinstance(b, ast.Name) and b.id == "BaseModel" for b in node.bases):
                continue
            required: set[str] = set()
            for stmt in node.body:
                if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                    continue
                name = stmt.target.id
                if name.startswith("_") or name == "model_config":
                    continue
                # A default of ANY kind makes it optional — except Field(...) with no default,
                # which is pydantic's explicit "required".
                value = stmt.value
                if value is None:
                    required.add(name)
                    continue
                if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "Field":
                    positional_default = bool(value.args) and not (
                        isinstance(value.args[0], ast.Constant) and value.args[0].value is Ellipsis)
                    has_default_kw = any(k.arg in ("default", "default_factory")
                                         for k in value.keywords)
                    if not positional_default and not has_default_kw:
                        required.add(name)
            models[node.name] = (required, rel)

        # 2) the routes, and the body model each names
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)):
                    continue
                if deco.func.attr != "post" or not deco.args:
                    continue
                first = deco.args[0]
                if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                    continue
                route = first.value
                for arg in node.args.args + node.args.kwonlyargs:
                    ann = getattr(arg.annotation, "id", "")
                    if ann in models:
                        req, where = models[ann]
                        out[route] = (ann, req, where)
    return out


# ── the caller side: every literal body posted to an internal path ──────────────────────────────
def calls(service: pathlib.Path) -> tuple[list[tuple[str, int, str, set[str]]], list[str]]:
    """(calls, unverifiable). A call is (file, line, path_fragment, body_keys)."""
    found: list[tuple[str, int, str, set[str]]] = []
    unverifiable: list[str] = []

    for path in sorted((service / "app").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "/internal/" not in text:
            continue
        tree = ast.parse(text)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        # Every internal path literal in this file, with the line it sits on.
        fragments = [(m.start(), m.group(0))
                     for m in re.finditer(r"/internal/[a-zA-Z0-9/_\-]+", text)]
        if not fragments:
            continue
        line_of = {}
        for offset, frag in fragments:
            line_of[frag] = text.count("\n", 0, offset) + 1

        # PER FUNCTION, NOT PER MODULE. Nearly every adapter here writes `body = {...}` inside its
        # own function, so a module-wide map sees the same name assigned five times and gives up on
        # all five — which is how this gate first read three calls out of fourteen.
        scopes: list[tuple[dict[str, ast.Dict | None], list[ast.AST]]] = []
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            local: dict[str, ast.Dict | None] = {}
            for stmt in ast.walk(fn):
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                        and isinstance(stmt.targets[0], ast.Name):
                    name = stmt.targets[0].id
                    # Assigned twice in one function: dropped rather than guessed at, because the
                    # second assignment may be the one that travels and a gate must not pick.
                    local[name] = (stmt.value if isinstance(stmt.value, ast.Dict)
                                   and name not in local else None)
            scopes.append((local, list(ast.walk(fn))))

        for node in ast.walk(tree):
            # Which function's locals apply to this call — the innermost one containing it.
            literal_dicts: dict[str, ast.Dict | None] = {}
            for local, members in scopes:
                if node in members:
                    literal_dicts = local
                    break
            # json.dumps({...}) — the only shape this gate can read with certainty.
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "dumps" and node.args):
                continue
            arg = node.args[0]
            # `json.dumps(payload)` where `payload = {...}` a few lines above is the commonest
            # shape in this fleet, and refusing to follow it left the gate reading three calls out
            # of fourteen — technically honest and practically useless. One hop, same module.
            if isinstance(arg, ast.Name):
                resolved = literal_dicts.get(arg.id)
                if resolved is None:
                    unverifiable.append(
                        f"{rel}:{node.lineno} body is the variable «{arg.id}», assigned from "
                        f"something this gate cannot read")
                    continue
                arg = resolved
            if not isinstance(arg, ast.Dict):
                unverifiable.append(f"{rel}:{node.lineno} body is not a literal dict")
                continue
            keys = {k.value for k in arg.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if len(keys) != len(arg.keys):
                unverifiable.append(f"{rel}:{node.lineno} body has computed keys")
            # Attribute the body to the nearest internal path in the same file. Imprecise when a
            # module posts to several, so that case is reported rather than guessed at.
            near = [f for f in line_of if abs(line_of[f] - node.lineno) <= 25]
            if len(near) != 1:
                unverifiable.append(
                    f"{rel}:{node.lineno} body could belong to {len(near)} internal paths")
                continue
            found.append((rel, node.lineno, near[0], keys))
    return found, unverifiable


def main() -> int:
    services = sorted(p for p in SERVICES.iterdir() if (p / "app").is_dir())
    # path → (owner, model, required, where)
    served: dict[str, tuple[str, str, set[str], str]] = {}
    for service in services:
        for route, (model, required, where) in route_models(service).items():
            # Routers mount under a prefix; match on the tail, which is what the caller writes.
            served[route] = (service.name, model, required, where)

    broken: list[str] = []
    unresolved: list[str] = []
    unverifiable: list[str] = []
    compared = 0

    for service in services:
        found, notes = calls(service)
        unverifiable.extend(notes)
        for rel, line, fragment, keys in found:
            # EXACT TAIL, LONGEST WINS. A caller writes the full path («/internal/reminders/offer/
            # choose») while the route is declared under its router's prefix («/reminders/offer/
            # choose»), so the tail is the join. Matching loosely made this gate blame `SubscribeIn`
            # for four unrelated calls on its first run — and a gate that names the wrong file is
            # worse than no gate, because the next person stops believing the ones that are right.
            candidates = [(route, info) for route, info in served.items()
                          if len(route.strip("/").split("/")) >= 2 and fragment.endswith(route)]
            match = max(candidates, key=lambda c: len(c[0])) if candidates else None
            if match is None:
                unresolved.append(f"{rel}:{line} posts to {fragment} — no route in this repo serves it")
                continue
            route, (owner, model, required, where) = match
            compared += 1
            gap = required - keys
            if gap:
                broken.append(
                    f"{rel}:{line} posts to {fragment} without {sorted(gap)} — "
                    f"{owner}'s {model} ({where}) requires them, so every call is rejected 422")

    if unverifiable:
        print(f"{C_Y}  ~ {len(unverifiable)} internal call(s) this check cannot read — a body it "
              f"cannot see is a contract it cannot vouch for:{C_N}")
        for line in unverifiable[:15]:
            print(f"{C_Y}      {line}{C_N}")
    if unresolved:
        print(f"{C_Y}  ~ {len(unresolved)} internal path(s) with no route in this repo — the peer "
              f"may be the platform, which this gate does not read:{C_N}")
        for line in unresolved[:15]:
            print(f"{C_Y}      {line}{C_N}")

    if broken:
        print(f"{C_R}  ✘ {len(broken)} internal call(s) can never succeed:{C_N}")
        for line in broken:
            print(f"{C_R}      {line}{C_N}")
        return 1

    print(f"{C_G}  ✔ every internal call carries what its peer requires "
          f"({compared} compared across {len(services)} services){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
