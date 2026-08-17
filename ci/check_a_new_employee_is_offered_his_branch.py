"""Both ways of adding an employee carry his branch.

WHAT HAPPENED. «فريقي» adds two kinds of person: one with a login («حساب يدخل به») and one with a
four-digit code on a shared tablet («رمز على الجهاز»). The branch picker was written INSIDE the
login block, and the PIN call sent `{name, pin, role}` — so the man on the shared tablet, who is
most of a workshop's staff, could not be given a branch from any screen in the product.

AND A VISIT TAKES ITS BRANCH FROM THE PERSON RECORDING IT (`core/operations.py` `_branch_for`). So
every visit he took landed in «غير محدَّد». An owner with three branches opened his comparison
table, read three near-empty rows and one enormous unnamed one, and had nothing anywhere to tell
him why. The server accepted `branch_id` on both routes the whole time; only the screen was silent.

WHAT THIS CHECKS. In `Team.tsx`, every call that creates an employee passes `branch_id`. Written
against the CALL rather than against the form, because a picker that renders and is not sent is the
same defect with a nicer screenshot.

NO EXCEPTIONS TABLE. «This kind of employee has no branch» is not a design somebody chose — it is
this defect, and the empty option in the picker («كل الفروع») is already how a person says so.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEAM = ROOT / "apps" / "console" / "src" / "screens" / "Team.tsx"
# EVERY `call(session, …, { … })` IN THE FILE, and the employee ones are picked out by their
# PAYLOAD rather than by the variable holding the action.
#
# The first version of this gate keyed on the names `add` / `hire`, and `add` is reused by the
# BRANCH form in the same file — so it demanded a `branch_id` on the call that creates a branch,
# which is nonsense, and it was red on correct code. A check that reads a variable name is reading
# the author's shorthand, not the act.
CALL = re.compile(r"call\(session,\s*\w+,\s*\{(?P<body>[^}]*)\}", re.S)
# What makes a payload an EMPLOYEE: a credential only a person is given.
CREDENTIAL = ("pin,", "pin:", "password")


def main() -> int:
    if not TEAM.exists():
        print(f"cannot find {TEAM.relative_to(ROOT).as_posix()} — this gate needs re-pointing")
        return 1
    try:
        text = TEAM.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"cannot read {TEAM.relative_to(ROOT).as_posix()}: {exc}")
        return 1

    calls = [m for m in CALL.finditer(text)
             if any(c in m.group("body") for c in CREDENTIAL)]
    if len(calls) < 2:
        # SILENCE IS NOT AGREEMENT. Two ways of adding a person exist; finding fewer means the
        # shape changed and this check is no longer looking at the thing it names.
        print(f"expected both employee-creating calls in {TEAM.relative_to(ROOT).as_posix()}, "
              f"found {len(calls)} — this gate needs re-pointing")
        return 1

    bad = [text[:m.start()].count("\n") + 1 for m in calls if "branch_id" not in m.group("body")]
    if bad:
        print("An employee can be created with no branch from the screen:")
        for line in bad:
            print(f"  Team.tsx:{line} · this call does not send `branch_id`")
        print("\nA visit takes its branch from whoever recorded it, so his work lands in "
              "«غير محدَّد» for ever — and the owner's branch table quietly stops adding up.")
        return 1
    print(f"{len(calls)} way(s) of adding an employee, each carrying his branch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
