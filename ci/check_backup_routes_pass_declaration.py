"""Every call to `core.backup.import_archive`/`verify_restore` must pass its own service's
`declaration=` (the service's `backup_manifest.py::BACKUP`) — never call either with the default
`declaration=None`.

WHY THIS EXISTS. Found live (2026-09-28), across a 13-service audit: `import_archive`/
`verify_restore` both resolve a per-collection restore KEY from `declaration` (`core/backup.py::
_key_templates` — default template `"{id}"` when a collection has no declared `key`, or when
`declaration` itself is `None`). Two services (bookings, loyalty) route calls that never passed
`declaration=BACKUP` at all — silently falling back to `"{id}"` for EVERY collection. loyalty's own
`loyalty_balances` has no `id` field at all (keyed by `Balance.key`, a `tenant|subject_ref`
composite) — so restoring it raised `KeyError('id')` on the very first row, aborting the WHOLE
restore. bookings' own `booking_slots` carries the same shape (`backup_manifest.py`'s own `"key":
"{tenant}|{branch_id}|{bucket}|{booking_id}"`). Seven more services (campaigns, coworking,
error-collector, operations, portal, referrals, reminders) had the identical gap latent — no
composite-keyed collection YET, so the missing `declaration=` cost nothing today, but the day any
of them adds one (exactly how loyalty/bookings got here) a restore silently breaks again with
nothing here to catch it before it ships.

WHAT THIS DOES NOT DO. It never checks the CONTENTS of a `declaration` (that is
`check_backup_manifest_declares_written_collections.py`'s job) — only that a real, non-None
`declaration=` keyword is present on every call site, so an omission can never again resolve to the
default template silently.

    python ci/check_backup_routes_pass_declaration.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
_EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}
_WATCHED_CALLS = {"import_archive", "verify_restore"}


def _is_excluded(path: pathlib.Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _called_name(node: ast.Call) -> str | None:
    """The bare function/attribute name a call targets — `import_archive(...)` or
    `_backup.import_archive(...)` both resolve to `"import_archive"`."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _has_real_declaration(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg == "declaration":
            # `declaration=None` is the same gap as omitting it outright — a caller that writes
            # this explicitly is not making the mistake this gate exists for, but it is worth
            # catching too since it produces the identical silent fallback.
            return not (isinstance(kw.value, ast.Constant) and kw.value.value is None)
    return False


def find_problems() -> list[str]:
    problems: list[str] = []
    for path in sorted(SERVICES.glob("*/app/**/*.py")):
        if _is_excluded(path):
            continue
        # The engine's own definitions are not call sites.
        if path.name == "backup.py" and path.parent.name == "core":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _called_name(node)
            if name not in _WATCHED_CALLS:
                continue
            if not _has_real_declaration(node):
                rel = path.relative_to(ROOT)
                problems.append(f"{rel}:{node.lineno}: {name}(...) has no real `declaration=` — "
                                f"every collection restores under the default \"{{id}}\" template")
    return problems


def main() -> int:
    problems = find_problems()
    if problems:
        print("\033[31m  ✗ backup routes missing declaration=:\033[0m")
        for p in problems:
            print(f"\033[31m    ✗\033[0m  {p}")
        print(f"\n\033[31m  ✗ {len(problems)} call site(s) would restore every collection under "
              f"the default \"{{id}}\" template, silently ignoring any composite key a manifest "
              f"declares\033[0m")
        return 1
    print("\033[32m  ✔ every import_archive/verify_restore call passes a real declaration=\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
