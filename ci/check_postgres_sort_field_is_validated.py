"""Every service's Postgres `find()` must validate its sort field before splicing it into SQL.

WHY THIS EXISTS. `find(collection, where, *, sort=(field, direction))` binds every VALUE as a
`$n` parameter — Postgres has no placeholder syntax for an identifier or a JSON key, so `field`
is f-string-spliced directly into the `ORDER BY COALESCE(value->>'{field}', ...)` clause instead.
A QA pass (2026-09-12) found this unvalidated in `services/reminders/app/adapters/datastore/
postgres.py`, right beside an ALREADY-FIXED twin in `services/portal`'s own copy: portal validates
`direction` against `SORT_DIRECTIONS` and then, one line later, validates `field` against
`re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field)` — every OTHER service copied the `direction`
check and skipped the `field` one, in the identical file, at the identical call site. Today's only
callers all pass a hardcoded field name, so there is no live exploit path yet — but a future caller
forwarding a client-controlled sort field would have a real injection: a value containing a quote
breaks out of the JSON-key string literal it is embedded in, and nothing here would refuse it.

WHAT THIS CHECKS. Every `app/adapters/datastore/postgres.py` under `services/*` that defines a
`find` method unpacking `field, direction = sort` must ALSO, somewhere in that same method, call
`re.fullmatch` (or `re.match`) against a name bound from that unpacking — the exact shape of
portal's fix. A file with no such `find` method (a service with no Postgres adapter, or one that
does not support `sort` at all) is not flagged; only a `postgres.py` that unpacks `field` from
`sort` and never validates it before use.

WHAT THIS DELIBERATELY DOES NOT DO: it does not check that the regex is exactly right, or that the
validation actually runs before the SQL is built — a narrow presence check, mirroring this repo's
other gates, that is enough to catch "the fix was never copied here" without re-deriving portal's
whole reasoning in code.

    python ci/check_postgres_sort_field_is_validated.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
_EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}


def _is_excluded(path: pathlib.Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _unpacks_field_from_sort(fn: ast.AST) -> str | None:
    """If `fn`'s body contains `<field_name>, <direction_name> = sort` (the exact unpacking every
    copy of this adapter uses), returns `<field_name>`; else None."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Tuple) and len(target.elts) == 2):
            continue
        field_target, _direction_target = target.elts
        if not isinstance(field_target, ast.Name):
            continue
        value = node.value
        if isinstance(value, ast.Name) and value.id == "sort":
            return field_target.id
    return None


def _validates_field(fn: ast.AST, field_name: str) -> bool:
    """True if some `re.fullmatch(...)`/`re.match(...)` call anywhere in `fn` names `field_name`
    among its arguments — the shape of portal's fix, wherever exactly it is placed."""
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("fullmatch", "match")
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "re"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id == field_name:
                return True
    return False


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(SERVICES.glob("*/app/adapters/datastore/postgres.py"))

    violations: list[str] = []
    checked = 0

    for f in files:
        if _is_excluded(f):
            continue
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for fn in ast.walk(tree):
            if not (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name == "find"):
                continue
            field_name = _unpacks_field_from_sort(fn)
            if field_name is None:
                continue
            checked += 1
            if not _validates_field(fn, field_name):
                violations.append(
                    f"{f.relative_to(ROOT)}:{fn.lineno}: `find()` unpacks `{field_name}` from "
                    f"`sort` and splices it into SQL, but never validates it with "
                    f"`re.fullmatch`/`re.match` — see services/portal's fixed copy for the pattern")

    if violations:
        print(f"  ✘ {len(violations)} unvalidated sort-field(s) (of {checked} `find()` methods "
              f"checked):")
        for v in violations:
            print(f"      {v}")
        return 1

    print(f"  ✔ all {checked} `find()` method(s) that splice a sort field validate it first")
    return 0


if __name__ == "__main__":
    sys.exit(main())
