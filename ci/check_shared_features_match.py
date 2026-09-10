#!/usr/bin/env python3
# =============================================================================
# check_shared_features_match.py — a "shared feature" is ONE feature, enforced, not hoped for.
#
# WHY THIS EXISTS. `services/reminders/app/core/features.py`'s own docstring explains the
# constraint this works around: services in this fleet do not import each other's code, so a
# feature genuinely granted by more than one app (today: reminders' own adaptive/engagement
# engine, granted through both تسجيل زيارة and الحجوزات) cannot be ONE Python object shared by
# import. Each consuming service keeps its own literal copy of the same id/title/detail/icon/tone
# — and a literal copy that nobody checks is a literal copy that silently drifts the first time
# either card's wording is edited without remembering the other one exists.
#
# THIS GATE IS THE THING THAT MAKES THEM ONE FEATURE ANYWAY: `services/reminders/app/core/
# features.py`'s `SHARED_FEATURES` is the canonical text (reminders owns the real code); every
# other service's own copy of the same `id` — wherever it appears, as a `Feature(...)`/
# `SharedFeature(...)` call or a plain dict literal, this file reads both shapes — must match it
# byte for byte on title/detail/icon/tone. A single edited word in one file and not the other
# fails the build immediately, rather than shipping two cards that quietly say different things
# about the identical capability.
# =============================================================================
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CANONICAL_FILE = ROOT / "services/reminders/app/core/features.py"
CANONICAL_LIST_NAME = "SHARED_FEATURES"

# Every OTHER file that may carry its own copy of a shared feature's id. A new consumer joins by
# adding its own file here — the same one-line-per-consumer shape `ci/check_entitlements.py` and
# friends already use throughout this fleet.
CONSUMER_FILES = (
    ROOT / "services/bookings/app/core/features.py",
    ROOT / "services/operations/app/core/apps.py",
)

FIELDS = ("title", "detail", "icon", "tone")


def _module_constants(tree: ast.AST) -> dict[str, object]:
    """Module-level `NAME = "literal"` assignments — a file is allowed to write
    `tone=TONE_ROSE` instead of `tone="rose"` (bookings' own `core/features.py` does exactly
    that, for a reason its own comment states: readable named categories, not repeated strings),
    and this gate must resolve that reference the same way a human reading the file does."""
    out: dict[str, object] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            val = _literal(node.value)
            if val is not None:
                out[node.targets[0].id] = val
    return out


def _literal(node: ast.AST, constants: dict[str, object] | None = None) -> object:
    if constants and isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    try:
        return ast.literal_eval(node)
    except Exception:                                                       # noqa: BLE001
        return None


def _entries_from(tree: ast.AST) -> dict[str, dict[str, object]]:
    """Every `{id, title, detail, icon, tone}`-shaped thing in a file, however it is written —
    a `Feature(...)`/`SharedFeature(...)` call with keyword args, or a plain dict literal. Reads
    the AST directly; never imports or executes the file (same discipline `admin_actions.py`'s own
    `ast.literal_eval` convention holds elsewhere in this fleet — a CI script must not need a
    service's own dependencies installed to run)."""
    constants = _module_constants(tree)
    out: dict[str, dict[str, object]] = {}
    for node in ast.walk(tree):
        row: dict[str, object] = {}
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg in ("id", *FIELDS):
                    row[kw.arg] = _literal(kw.value, constants)
        elif isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                key = _literal(k, constants) if k is not None else None
                if key in ("id", *FIELDS):
                    row[str(key)] = _literal(v, constants)
        fid = row.get("id")
        if isinstance(fid, str) and all(f in row for f in FIELDS):
            out[fid] = row
    return out


def main() -> int:
    canonical_tree = ast.parse(CANONICAL_FILE.read_text(encoding="utf-8"))
    canonical = _entries_from(canonical_tree)
    if not canonical:
        print(f"  ✗ {CANONICAL_FILE} declares no {CANONICAL_LIST_NAME} entries readable by this "
             "gate — nothing to check against, which means it silently checks nothing")
        return 1

    problems: list[str] = []
    for path in CONSUMER_FILES:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fid, row in _entries_from(tree).items():
            truth = canonical.get(fid)
            if truth is None:
                continue   # this id is not a shared feature at all — not this gate's business
            for field in FIELDS:
                if row.get(field) != truth.get(field):
                    problems.append(
                        f"{path.relative_to(ROOT)}: {fid!r}.{field} = {row.get(field)!r} "
                        f"!= canonical {truth.get(field)!r} ({CANONICAL_FILE.relative_to(ROOT)})")

    if problems:
        print(f"  ✗ {len(problems)} shared-feature mismatch(es):")
        for p in problems:
            print(f"    {p}")
        return 1

    print("  ✔ every shared feature reads identically everywhere it is granted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
