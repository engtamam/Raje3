#!/usr/bin/env python3
"""ONE FACT, ONE PLACE — AND THE PRODUCT'S TIMEZONE IS A FACT.

WHAT THIS FOUND. `config/product.json` declares `"timezone": "Asia/Riyadh"` and NO SERVICE READS
IT. Instead, `timezone(timedelta(hours=3))` is typed out in six files across four services:

    reminders/core/gate.py          — decides the quiet hours, so it decides when a real customer
                                      is messaged
    reminders/core/rendering.py     — the dates printed inside those messages
    campaigns/core/tick.py          — when a scheduled campaign is allowed to fire
    campaigns/api/v1/campaigns.py   — what the owner is shown before he presses send
    campaigns/adapters/peers        — the same arithmetic, a third time in one service
    operations/api/internal.py      — the busiest-hours grid

SIX, NOT SEVEN. The register listed `portal/core/render.py` too and it does not write the offset
any more — which is exactly why the list lives in code that runs rather than in a document: the
gate said so on its first run.

NO DEFECT TODAY, AND THAT IS THE POINT OF WRITING IT DOWN. Saudi Arabia has no daylight saving,
so `+3` is correct all year and every one of those six is right. The cost arrives the day the
number has to change — a second country, a tenant-level setting, anything — and it arrives as FIVE
of them changing and one not. Which one is not decidable from here; what IS decidable is that a
fact copied six times will eventually be five facts and a different one.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. No service source may construct a fixed UTC offset
inline. It comes from a named constant that a person can find, change once, and grep for.

THIS GATE DOES NOT UNPICK THE SIX. It stops the seventh, and it names the six every time it
runs so that «somebody should consolidate these» stays a sentence in front of a reader rather
than a note in a document nobody opens. Consolidating them touches four services' arithmetic and
is its own task, done deliberately and with its own tests — not smuggled into an unrelated change.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

# The six that exist today. Each is named with the file it lives in, so the list cannot quietly
# become seven: a NEW one is a failure, and removing one from here after consolidating it is a
# one-line change somebody makes on purpose.
KNOWN = {
    "services/reminders/app/core/gate.py",
    "services/reminders/app/core/rendering.py",
    "services/campaigns/app/core/tick.py",
    "services/campaigns/app/api/v1/campaigns.py",
    "services/campaigns/app/adapters/peers/__init__.py",
    "services/operations/app/api/internal.py",
}


def _hardcoded_offsets(tree: ast.AST) -> list[int]:
    """`timedelta(hours=<n>)` inside a `timezone(...)` call — a fixed UTC offset, written out."""
    out: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "timezone"):
            continue
        for arg in node.args:
            if not (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name)
                    and arg.func.id == "timedelta"):
                continue
            for kw in arg.keywords:
                if kw.arg == "hours" and isinstance(kw.value, ast.Constant):
                    out.append(kw.value.value)
    return out


def main() -> int:
    if not SERVICES.is_dir():
        print(f"{C_R}no services/ — this gate checked nothing, and an empty set is not "
              f"agreement{C_N}")
        return 1

    found: set[str] = set()
    unreadable: list[str] = []

    for path in sorted(SERVICES.rglob("*.py")):
        if "test" in path.parts or path.name.startswith("test_"):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            unreadable.append(f"{rel}: cannot read it — {exc}")
            continue
        if _hardcoded_offsets(tree):
            found.add(rel)

    if unreadable:
        print(f"{C_R}files this gate could not read — «could not tell» is not «nothing "
              f"found»{C_N}")
        for line in unreadable:
            print(f"  {line}")
        return 1

    new = sorted(found - KNOWN)
    if new:
        print(f"{C_R}the product's clock is written by hand in a new place{C_N}")
        for rel in new:
            print(f"  {rel}: a fixed UTC offset, typed out. It is right today and it is a copy of "
                  f"a fact that already lives in six other files — the day the number changes, "
                  f"the one nobody remembered is the one that keeps messaging people at 4am")
        print("\n  Import the constant. If there is genuinely no constant to import, that is the "
              "task to do first.")
        return 1

    stale = sorted(KNOWN - found)
    if stale:
        # NOT A FAILURE, AND SAID OUT LOUD ANYWAY. A file leaving this list is progress; a list
        # that quietly disagrees with the tree is how a gate stops meaning anything.
        print(f"{C_Y}  ~ these no longer write the clock by hand — remove them from KNOWN:{C_N}")
        for rel in stale:
            print(f"      {rel}")

    print(f"{C_G}ok{C_N}  no new hand-written clock; {len(found)} known copies remain "
          f"(ج-7 — one fact, six places, correct today)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
