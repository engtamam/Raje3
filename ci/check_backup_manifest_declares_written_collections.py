"""Every collection a service actually writes through its own DataStore port must appear in that
service's own `backup_manifest.py` — in `collections` (backed up) or `excluded` (skipped, with a
reason a person can challenge). There is no third state; the third state is a silent hole in a
restore, discovered only the day someone needs it.

WHY THIS EXISTS. `backup_manifest.py`'s own docstring, in every service, claims a
`safety:backup-coverage` gate already checks this — no such gate existed in this repo (fixed
2026-09-12, a real gap a QA audit found: portal's manifest declared `"collections": []` while
`app/core/runtime_config.py` was actively calling `self._s.put(_COLL, ...)` against a real
collection). This gate makes that docstring's claim true.

WHAT COUNTS AS "WRITTEN". A literal collection name reaching the first positional argument of a
`.put(...)` call anywhere under a service's `app/` tree — either the string literal itself, or a
module-level `NAME = "literal"` constant referenced by name (the `_COLL = "runtime_config"` style
this codebase already uses). A call whose first argument is not resolvable to a literal this way
(a loop variable, a parameter) is a generic mechanism operating on a collection named elsewhere —
exactly `core/backup.py`'s own restore/verify engine, which writes rows back under whatever name
the ARCHIVE names, not a collection this service originates — and is deliberately not counted,
because it does not tell us this service originates that collection; the archive's own producer
service is the one whose manifest must declare it.

WHAT THIS DOES NOT DO. It never touches the manifest's `excluded` reasons, `tenant_scoped` flags,
or `object_prefix` — a human decides those, this only checks that every written name is MENTIONED
somewhere in the declaration. It also never invents a collection, and never checks a name in the
manifest that nothing writes (a stale entry is not a coverage gap — nothing catches it here on
purpose, since removing a declaration is a separate, lower-stakes cleanup).

    python ci/check_backup_manifest_declares_written_collections.py
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


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    """`NAME = "literal"` at module scope, so `_COLL = "runtime_config"` resolves by name."""
    out: dict[str, str] = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            out[node.targets[0].id] = node.value.value
    return out


def _written_collections(app_dir: pathlib.Path) -> set[str]:
    written: set[str] = set()
    for f in sorted(app_dir.rglob("*.py")):
        if _is_excluded(f) or "test" in f.parts or f.name.startswith("test_"):
            continue
        if f.name == "backup.py" and f.parent.name == "core":
            # The generic restore/verify engine: it writes rows under whatever collection name the
            # ARCHIVE it is restoring names, at runtime — not a collection this service originates.
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue
        consts = _module_string_constants(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "put" and node.args):
                continue
            # `@router.put("/path", ...)` is a FastAPI route decorator, not a DataStore write —
            # its receiver is always a bare `router`/`app` name, never an attribute chain ending
            # in something a DataStore port would be held as.
            recv = node.func.value
            if isinstance(recv, ast.Name) and recv.id in ("router", "app"):
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                written.add(arg.value)
            elif isinstance(arg, ast.Name) and arg.id in consts:
                written.add(consts[arg.id])
    return written


def _declared_collections(manifest_path: pathlib.Path) -> set[str] | None:
    """Names in `collections` + `excluded`, or None if this service has no manifest at all."""
    if not manifest_path.is_file():
        return None
    try:
        tree = ast.parse(manifest_path.read_text(encoding="utf-8"), filename=str(manifest_path))
    except (SyntaxError, UnicodeDecodeError):
        return None
    for node in ast.walk(tree):
        # `BACKUP: dict[str, Any] = {...}` is an AnnAssign, not a plain Assign.
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target = node.target
        if not (isinstance(target, ast.Name) and target.id == "BACKUP"):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return None
        names: set[str] = set()
        for bucket in ("collections", "excluded"):
            for entry in value.get(bucket, []) or []:
                if isinstance(entry, dict) and "name" in entry:
                    names.add(entry["name"])
        return names
    return None


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    violations: list[str] = []
    services_checked = 0

    for svc_dir in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        app_dir = svc_dir / "app"
        manifest = app_dir / "backup_manifest.py"
        if not app_dir.is_dir() or not manifest.is_file():
            continue  # not onboarded to a datastore/manifest at all — not this gate's concern
        services_checked += 1

        written = _written_collections(app_dir)
        declared = _declared_collections(manifest)
        if declared is None:
            violations.append(f"{svc_dir.name}: backup_manifest.py's BACKUP dict could not be "
                              f"read as a literal — cannot verify coverage")
            continue

        missing = sorted(written - declared)
        if missing:
            violations.append(
                f"{svc_dir.name}: writes {missing} but backup_manifest.py declares neither in "
                f"'collections' nor 'excluded'")

    if violations:
        print(f"  ✘ {len(violations)} service(s) with an undeclared write "
              f"(across {services_checked} services checked):")
        for v in violations:
            print(f"      {v}")
        return 1

    print(f"  ✔ every collection each service writes is declared in its own backup_manifest.py "
          f"(across {services_checked} services)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
