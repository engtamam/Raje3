"""A door that records a visit must also run the seams (د-20).

WHAT WENT WRONG. `/operations/visits/by-ref` — the free wash a loyalty reward paid for — recorded
the visit and returned. It never called `seams.after_visit`. Nothing failed, nothing logged: the
reminder cycle was simply not restarted, so the customer was reminded to come in for the service he
had just been handed, and the plate index never learned he was here. The two older doors (the batch
and the field screen) both do it, which is exactly why the third one reads as complete.

WHY A GATE AND NOT A TEST. The defect is a MISSING line, and a missing line is invisible to every
test of what the route returns — the route returns the right thing. Only the shape catches it: a
function that records a visit and does not run the seams is wrong on its face, whatever it returns.

No exceptions table. Every caller of `record_visit` in this repo owes the seams, and the day one
legitimately does not, the honest move is to say so here in words rather than to add a row.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDER = "record_visit"
SEAM = "after_visit"


def _calls(node: ast.AST) -> set[str]:
    """Every name this function CALLS."""
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute):
                names.add(f.attr)
            elif isinstance(f, ast.Name):
                names.add(f.id)
    return names


def _mentions(node: ast.AST, name: str) -> bool:
    """Whether this function names it AT ALL — called or handed to somebody else.

    The field screen does not call the seam; it hands it to `background.add_task` so the worker's
    200 is not held up by it. That is running the seams, and a check that only counted direct calls
    would demand a rewrite of the one door that was always right.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == name:
            return True
        if isinstance(sub, ast.Name) and sub.id == name:
            return True
    return False


def main() -> int:
    bad = []
    for path in sorted((ROOT / "services").rglob("*.py")):
        if "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            # LOUD, NOT SKIPPED. A file this gate cannot read is a file it cannot vouch for, and a
            # gate that answers «fine» about a file it never opened is worse than no gate.
            bad.append(f"{path.relative_to(ROOT).as_posix()} · unreadable: {exc}")
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # No name-based skip: the field screen's route is itself called `record_visit`, and
            # skipping by name would blind the gate to the busiest door in the product.
            if RECORDER in _calls(fn) and not _mentions(fn, SEAM):
                bad.append(f"{path.relative_to(ROOT).as_posix()}:{fn.lineno} · {fn.name}")

    if bad:
        print("A door records a visit and never runs the seams:")
        for line in bad:
            print("  " + line)
        print("\nThe visit is durable and nothing follows it: the reminder cycle is not restarted")
        print("and the index does not learn about it. Call `seams.after_visit(result)`.")
        return 1
    print("every recorded visit runs the seams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
