"""A cap that counts and then writes is not a cap.

WHY THIS EXISTS. `guard_and_report` asks billing «may this establishment add one more?» and is
given a `current` the caller counted a line earlier. Between that count and the insert there is an
await — an entitlement read over HTTP, tens of milliseconds — and any number of other requests may
pass through the same door in it. Two managers on a plan of five, both opening «إضافة موظف» at the
same moment, both count four, both are told yes, and both insert. The shop has six seats on a cap
of five, we bill for five, and no screen anywhere is red.

That is not a rare interleaving to be tightened later: it is the ONLY case a hard cap was bought
for. A shop that never has two people adding at once was never going to cross the line.

WHAT IT CHECKS. Every call to `guard_and_report(` must appear lexically inside an `async with`
block that opens `claiming(` — the establishment's serialised lane (core/seats.py). Indentation is
the test, which is exactly right for a rule about a lexical scope: a guard that has been lifted out
of the lane, or a lane closed before the write, changes the indentation and is caught.

WHAT IT CANNOT SEE, said plainly:
  · a lane opened and released BEFORE the write, if the write is also inside the `async with` of
    some other block at the same depth. The count and the guard are covered; a write moved out of
    the lane by a later edit is not — that is what the race test in
    services/operations/tests/unit/test_two_managers_cannot_take_the_same_last_seat.py holds down.
  · a NEW read-then-write cap that does not go through `guard_and_report` at all. This gate knows
    one function's name, not the shape of every check in the codebase.

THERE IS NO EXCEPTIONS TABLE, and there is no reading under which one would be justified: a call
site that may skip the lane is a call site where the cap does not hold.

    python ci/check_a_seat_is_claimed_before_it_is_counted.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GUARD = re.compile(r"\bguard_and_report\s*\(")
OPENS_LANE = re.compile(r"^\s*async with\s.*\bclaiming\s*\(")
# The definition and its own docstring live here; a file may not both define the rule and be
# checked by it. Scoped by PATH — never by a list of allowed offenders.
DEFINITION = "app/core/seats.py"


def _lane_depth(lines: list[str], index: int) -> int | None:
    """The indent of the `async with ... claiming(` this line sits inside, or None."""
    indent = len(lines[index]) - len(lines[index].lstrip())
    for back in range(index - 1, -1, -1):
        line = lines[back]
        if not line.strip():
            continue
        here = len(line) - len(line.lstrip())
        if here >= indent:
            continue
        if OPENS_LANE.match(line):
            return here
        indent = here
    return None


def main() -> int:
    bad: list[str] = []
    seen = 0
    for path in sorted(ROOT.glob("services/*/app/**/*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.endswith(DEFINITION):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not GUARD.search(line) or line.lstrip().startswith("#"):
                continue
            seen += 1
            if _lane_depth(lines, i) is None:
                bad.append(f"{rel}:{i + 1}: guard_and_report outside any claiming() lane")

    # SILENCE IS NOT AGREEMENT. If the call this gate is named after has been renamed away, an
    # empty sweep would report success while checking nothing at all.
    if seen == 0:
        print("FAIL: no guard_and_report call found anywhere — this gate is checking nothing")
        return 1

    if bad:
        print(f"FAIL: {len(bad)} seat guard(s) outside the lane, of {seen} checked")
        for line in bad:
            print("  " + line)
        return 1
    print(f"OK: {seen} seat guard(s), every one inside an establishment's claiming() lane")
    return 0


if __name__ == "__main__":
    sys.exit(main())
