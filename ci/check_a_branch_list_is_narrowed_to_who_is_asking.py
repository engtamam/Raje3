"""A list of branches handed to a person carries only the branches that person may see.

WHAT WAS TRUE UNTIL THIS GATE. `GET /api/v1/branches` read every row of the establishment and
returned all of them, to anybody holding `operations.list_branches`. The visit lists, the customer
lists and the dashboards were all narrowed by `api/scope.branch_scope` — this one read was not.
So a manager granted one branch could not read Jeddah's numbers, and could read Jeddah's NAME, its
id, and how many places the chain has. §12.4 says «لا يرى موظف فرع أ بيانات فرع ب»; the names of
the other branches are that shop's data too.

AND IT IS ABOUT TO MATTER MORE THAN A LEAK. The branch switcher moves out of «محلّي» and into the
sidebar, where it becomes a choice that scopes every screen — and it is built from this list. A
switcher built from an unnarrowed list offers a manager a branch he may not read: he taps it, the
server correctly refuses or returns nothing, and the product looks broken to a person who did
nothing wrong. The rule for that control is «يُضيِّق ولا يوسّع أبداً», and it can only hold if the
list it is built from was narrowed first.

THE RULE, WITH NO EXCEPTIONS TABLE: every handler under `api/v1` that answers with a `branches`
key resolves the caller's scope and filters through it. Not «the one we know about» — the key is
what this checks for, so a second such route added next year is covered on the day it is written.

WHAT THIS CANNOT SEE, said plainly:
  · `api/internal.py`, deliberately. Those doors are service-to-service and carry no person at
    all — narrowing them by a scope that does not exist would be theatre. They are guarded by the
    internal token instead;
  · whether the scope itself is RIGHT. `branch_scope` decides that, and its own tests do;
  · a handler that resolves the scope and then ignores the result. The call and the filter are
    both required here, which is as close as a source check gets.

    python ci/check_a_branch_list_is_narrowed_to_who_is_asking.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Where a person's own requests land. `internal.py` is excluded by living outside this directory
#: rather than by an exemption — see the note above on why that is a different kind of door.
V1 = ROOT / "services/operations/app/api/v1"

#: A response that hands back a list of branches. The KEY is the subject of the rule: whatever the
#: function is called, an answer shaped like this is a branch list in front of somebody.
ANSWERS_WITH_BRANCHES = re.compile(r'return\s*\{\s*"branches"|"branches":\s*\[')

#: The two halves, and both are needed. Resolving the scope and not filtering by it is the shape
#: of a fix that was started and abandoned, and it reads as protection to anyone who greps.
RESOLVES = re.compile(r"branch_scope\s*\(")
FILTERS = re.compile(r"\.visible\s*\(|\bvisible\s*\(")


def handlers_answering_with_branches(path: pathlib.Path) -> list[tuple[str, bool, bool]]:
    """Every function in this file that answers with a branch list, and what it does about scope.

    Split on `def ` rather than parsed: a full parse would be a bigger thing than the rule, and a
    handler is a contiguous block of text between one `def` and the next in every file here.
    """
    text = path.read_text(encoding="utf-8")
    out: list[tuple[str, bool, bool]] = []
    blocks = re.split(r"\n(?=(?:async )?def )", text)
    for block in blocks:
        if not ANSWERS_WITH_BRANCHES.search(block):
            continue
        name = re.match(r"(?:async )?def (\w+)", block.lstrip())
        out.append((name.group(1) if name else "?",
                    bool(RESOLVES.search(block)), bool(FILTERS.search(block))))
    return out


def main() -> int:
    if not V1.is_dir():
        # SILENCE IS NOT AGREEMENT. A moved directory makes this vacuous, and a gate that passes
        # for having read nothing is the failure it exists to prevent.
        print(f"FAIL: {V1.relative_to(ROOT)} is missing — this gate read nothing")
        return 1

    found = 0
    problems: list[str] = []
    for path in sorted(V1.glob("*.py")):
        for name, resolves, filters in handlers_answering_with_branches(path):
            found += 1
            if resolves and filters:
                continue
            missing = []
            if not resolves:
                missing.append("does not resolve `branch_scope`")
            if not filters:
                missing.append("does not filter through `visible`")
            problems.append(f"  {path.name}:{name} — {', and '.join(missing)}")

    if not found:
        print("FAIL: no handler under api/v1 answers with a `branches` key — either the route "
              "moved or the shape changed, and in both cases this gate is asserting nothing")
        return 1

    if problems:
        print(f"FAIL: {len(problems)} branch list(s) reach a person unnarrowed:")
        for p in problems:
            print(p)
        print("\n  §12.4: «لا يرى موظف فرع أ بيانات فرع ب» — and the names of the other branches "
              "are that shop's data too. Resolve the caller's scope and filter the rows through "
              "it, the way every other read in this service already does.")
        return 1

    print(f"OK: {found} branch list(s) under api/v1, every one narrowed to who is asking")
    return 0


if __name__ == "__main__":
    sys.exit(main())
