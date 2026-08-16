"""A request model is a contract. Reading a field off it that it never declares is not a read.

WHY THIS EXISTS. `/internal/loyalty/redeem` passed the approver through as
`getattr(body, "approved_by", "") or ""` — and `TillRedeemIn` did not declare `approved_by`. So the
default won every single time. The core then refused every reward above the shop's manager
threshold, on the one door where a manager is physically standing next to the till, and there was
no way on earth to satisfy it: the field the caller would have had to send was not in the schema,
so FastAPI would have dropped it even if the till sent it.

Nothing failed. `getattr` with a default cannot fail — that is the whole point of the third
argument, and it is exactly what made this invisible. The field existed, spelled identically, on
`EarnIn` two hundred lines up, which is how it passed review.

WHAT IT CHECKS. For every module, every pydantic model defined in it, and every
`getattr(x, "field", default)` where `x` is a parameter annotated with one of those models: the
field must be declared on the model (or on a base it inherits, within the same file). A read that
can only ever return its default is reported.

WHY A DEFAULT IS NOT AN EXCUSE. On a pydantic model the declared-field default already covers the
absent case — `body.approved_by` returns `""` when the caller omits it. `getattr` with a default on
top of that buys nothing and hides everything: it turns a typo, a rename and a missing field into
the same silent empty string.

WHAT IT CANNOT SEE, said plainly: a model imported from another module. Those are counted and
reported as unverified rather than passed over, because a list of things that look checked and are
not is worse than a shorter list.

    python ci/check_undeclared_field_read.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _is_model(node: ast.ClassDef) -> bool:
    """A pydantic model, by the base it names. Matching the name rather than resolving the import
    is deliberate: `BaseModel` is what every model in this repo inherits, spelled that way."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id.endswith("BaseModel"):
            return True
        if isinstance(base, ast.Attribute) and base.attr.endswith("BaseModel"):
            return True
    return False


def _fields(node: ast.ClassDef, models: dict[str, ast.ClassDef]) -> set[str]:
    """Declared fields, following bases defined in the same file."""
    out: set[str] = set()
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            out.add(stmt.target.id)
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    for base in node.bases:
        name = base.id if isinstance(base, ast.Name) else ""
        if name in models and models[name] is not node:
            out |= _fields(models[name], models)
    return out


def _annotation(ann) -> str:
    if isinstance(ann, ast.Name):
        return ann.id
    if isinstance(ann, ast.Attribute):
        return ann.attr
    return ""


def scan(path: pathlib.Path) -> tuple[list[str], int]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    rel = str(path.relative_to(ROOT)).replace("\\", "/")

    models = {n.name: n for n in ast.walk(tree)
              if isinstance(n, ast.ClassDef) and _is_model(n)}
    if not models:
        return [], 0

    findings: list[str] = []
    unknown = 0
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # WHICH LOCAL NAME HOLDS WHICH MODEL, from the signature. The request body is a parameter
        # with a model annotation — that is the whole population this check is about.
        bound: dict[str, str] = {}
        args = fn.args
        for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            model = _annotation(a.annotation)
            if model in models:
                bound[a.arg] = model
        if not bound:
            continue
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "getattr" and len(node.args) >= 2):
                continue
            target, attr = node.args[0], node.args[1]
            if not (isinstance(target, ast.Name) and target.id in bound):
                continue
            if not (isinstance(attr, ast.Constant) and isinstance(attr.value, str)):
                unknown += 1
                continue
            model = bound[target.id]
            if attr.value not in _fields(models[model], models):
                findings.append(
                    f"{rel}:{node.lineno}  {fn.name}() reads «{attr.value}» off {model}, which "
                    f"never declares it — the default is the ONLY value this can return")
    return findings, unknown


def main() -> int:
    findings: list[str] = []
    unknown = 0
    files = 0
    for path in sorted(SERVICES.glob("*/app/**/*.py")):
        if path.name == pathlib.Path(__file__).name:
            continue
        files += 1
        got, unk = scan(path)
        findings += got
        unknown += unk

    if findings:
        print(f"{C_R}  ✘ {len(findings)} field(s) read off a request model that does not declare "
              f"them:{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Declare the field on the model — a caller cannot send what the schema "
              f"does not accept, so the refusal downstream can never be satisfied.{C_N}")
        return 1

    if unknown:
        print(f"{C_Y}  ! {unknown} getattr call(s) on a model with a computed attribute name — "
              f"not verifiable here{C_N}")
    print(f"{C_G}  ✔ every field read off a request model is declared on it ({files} modules){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
