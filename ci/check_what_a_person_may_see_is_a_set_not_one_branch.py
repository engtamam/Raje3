"""What a person may SEE is a set of branches; where he WORKS is one. They are not the same field.

WHAT THIS PROTECTS. `operations/app/api/scope.py` answers «which branch may this caller read», and
it answers it with `op.branch_id` — the row that says where the man is STATIONED. So the two facts
are one field, and the product cannot express the ordinary thing an owner asks for: a supervisor
who works out of the Malaz branch and watches four. Today the only two settings are «one branch» and
«everything», and «everything» is what you get by leaving the field empty — which is also what a
new employee gets before anybody assigns him.

THE SHAPE THE ANSWER HAS TO TAKE. A set. One branch is a set of one, the whole establishment is the
empty set meaning «unrestricted», and a regional manager is a set of four — the same vocabulary for
all three, so no reader has a special case. That is why this gate hunts EQUALITY: `row.branch ==
scope` is correct for exactly as long as a person can see exactly one branch, and it does not fail
loudly when that stops being true — it silently hides three branches from the man hired to watch
them, and every screen looks like it is working.

NO EXCEPTIONS TABLE. A reader that compares the visibility answer with `==` is either wrong now or
wrong the day the second branch is granted; there is no version of it worth keeping.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Where the answer is produced and where it is consumed. Scoped to the files that actually hold
#: the concept — NOT to a directory, because «services/» is a place and this is a risk.
WATCHED = [
    ROOT / "services" / "reminders" / "app" / "api" / "v1" / "owner.py",
    ROOT / "services" / "insights" / "app" / "api" / "v1" / "insights.py",
    ROOT / "services" / "loyalty" / "app" / "api" / "internal.py",
    ROOT / "services" / "operations" / "app" / "api" / "scope.py",
]

#: The names a visibility answer travels under. A comparison against any of them is the defect.
NAMES = ("scope", "visible", "visible_branches", "branch_scope")

EQUALITY = re.compile(
    r"[!=]=\s*(?:" + "|".join(NAMES) + r")\b"
    r"|\b(?:" + "|".join(NAMES) + r")\s*[!=]=(?!=)"
)

#: `scope in DENIED` and `scope not in DENIED` ask whether the answer ARRIVED, which is a different
#: question and stays correct whatever shape it has.
MEMBERSHIP = re.compile(r"\b(?:not\s+)?in\s+DENIED\b")


def main() -> int:
    if not WATCHED:
        print("no visibility readers declared — this gate needs re-pointing")
        return 1

    bad: list[str] = []
    read = 0
    for path in WATCHED:
        if not path.exists():
            print(f"cannot find {path.relative_to(ROOT).as_posix()} — this gate needs re-pointing")
            return 1
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        read += 1
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if MEMBERSHIP.search(line):
                continue
            if EQUALITY.search(line):
                bad.append(
                    f"{path.relative_to(ROOT).as_posix()}:{line_no} · what this person may see is "
                    "compared with `==`, so it can only ever be ONE branch — a supervisor over four "
                    "silently sees one, and nothing fails"
                )

    if not read:
        print("read no visibility readers — this gate needs re-pointing")
        return 1
    if bad:
        print("Visibility is treated as one branch rather than a set:")
        for line in bad:
            print("  " + line)
        print("\nAsk whether the branch is IN what he may see. One branch is a set of one.")
        return 1
    print(f"{read} visibility reader(s): each asks membership, not equality")
    return 0


if __name__ == "__main__":
    sys.exit(main())
