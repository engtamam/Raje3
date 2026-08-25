"""Work that arrives from a cash register says which branch it happened in, or it is refused.

WHAT THIS PREVENTS, IN THE OWNER'S WORDS. «لا تقدر تقارن فروعك» — a whole indicator switched off,
permanently, for the shops that most need it, because `branch_id` was optional on the till door and
most tills simply never sent it. Every branch's visits piled into one heap, and no report written
afterwards can take them apart again: nothing in the record says where any of it happened.

WHY OPTIONAL WAS THE ORIGINAL ANSWER, AND WHY IT IS NOT ANY MORE. The field was optional so that an
already-installed register would not start failing the day we tightened the rule — a real concern
once shops depend on it, and not a concern at all today: «احنا لساع في
التطوير، مافي شي شابك — نطوّر ونختبر». There is no installed base to protect, so the field becomes
mandatory now, while making it mandatory costs one line in a document instead of an outage.

THE RULE, WITH NO EXCEPTIONS TABLE. Every request model in the till API that records work carries a
`branch_id` the caller must supply. Not `default=""` — a default is exactly the shape that let a
register file thousands of visits without ever mentioning a place.

WHAT THIS DOES NOT COVER, said plainly:
  · our own field screen, which does not take the branch from the request at all — it reads the
    operator's own row, and that is a stronger answer than anything a device can claim
    (core/operations.py `_branch_for`). A rule about what a REQUEST must carry has nothing to say
    about a door that ignores the request;
  · whether the id names a branch this shop really has. That is a value check at the door, and it
    lives with the door;
  · whether the visit is finally STORED with a branch. That is what the crossing test proves, and
    a source check cannot.

    python ci/check_the_till_cannot_file_work_in_a_place_it_did_not_name.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOOR = ROOT / "services/operations/app/api/v1/till.py"

#: A branch field the caller may leave out. `default=` is the whole tell: with one, an omitted
#: field is silently an empty string; without one, the request is refused before it reaches us.
OPTIONAL_BRANCH = re.compile(r"^\s*branch_id\s*:\s*str\s*=\s*Field\((?P<args>[^)]*)\)")


def main() -> int:
    if not DOOR.is_file():
        # SILENCE IS NOT AGREEMENT. Nothing read is not the same as nothing wrong, and a check that
        # passes because its subject moved is worse than no check: it reports safety it never saw.
        print(f"FAIL: {DOOR.relative_to(ROOT)} is missing — this gate read nothing")
        return 1

    optional: list[str] = []
    found = 0
    for n, line in enumerate(DOOR.read_text(encoding="utf-8").splitlines(), 1):
        m = OPTIONAL_BRANCH.match(line)
        if not m:
            continue
        found += 1
        if "default" in m.group("args"):
            optional.append(f"  till.py:{n}: {line.strip()}")

    if not found:
        print("FAIL: no branch_id field found on the till door at all — either the door moved or "
              "the field was dropped, and in both cases this gate is asserting nothing")
        return 1

    if optional:
        print(f"FAIL: {len(optional)} till field(s) let a register file work with no branch:")
        for p in optional:
            print(p)
        print("\n  Drop the default so the request is refused with a message the integrator can "
              "act on. A visit recorded in no place cannot be put back into one later.")
        return 1

    print(f"OK: all {found} branch field(s) on the till door are required")
    return 0


if __name__ == "__main__":
    sys.exit(main())
