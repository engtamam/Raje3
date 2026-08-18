"""A route that writes either requires a live subscription or declares that it must not.

WHAT THIS GUARDS. `feature.base` is the 99-a-month product — the visit register — and until this
gate it was enforced NOWHERE, while the four smaller apps around it each had a licence. That is
not a coincidence: the other four were each caught by a human noticing one route. Reading every
handler body to the end to find out which ones ask is not a review anybody repeats, so the
question moved onto the decorator, where one line answers it.

THE RULE. Every `@router.post/put/patch/delete` in the services below must name exactly one of

    Depends(subscribed_write)          this write needs the month paid
    Depends(no_subscription_needed)    this write works while it is lapsed, deliberately

in its own `dependencies=[…]` list. Naming neither is the defect this exists for; naming both is
a contradiction and refused too.

AND THE EXEMPTIONS LIVE IN THE ROUTE, NOT HERE. There is no list of blessed paths in this file.
Paying us, signing up, and the customer's PDPL rights must keep working when the month lapses —
each of those routes says so itself, in the code that governs it, where the next person to edit it
will see the decision they are changing.

    python ci/check_every_write_says_whether_it_needs_a_subscription.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: WHERE THE OWNER'S OWN WRITES LIVE. `internal.py` routers are peer-to-peer behind an internal
#: token — a service asking another service to do a thing the OWNER already asked for. Charging
#: the licence twice on one intention would refuse the second half of an accepted request.
SCOPES = (
    ROOT / "services" / "operations" / "app" / "api" / "v1",
    ROOT / "services" / "reminders" / "app" / "api" / "v1",
)

WRITES = re.compile(r"@router\.(post|put|patch|delete)\(", re.M)
REQUIRES = "subscribed_write"
EXEMPT = "no_subscription_needed"

COMMENT = re.compile(r"#.*$", re.M)
DOCSTRING = re.compile(r'("""|\'\'\')(?:.|\n)*?\1')


def _code_only(source: str) -> str:
    """Prose blanked, never deleted — line numbers have to keep meaning something."""
    def blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return COMMENT.sub("", DOCSTRING.sub(blank, source))


def _decorator(code: str, start: int) -> str:
    """The decorator call's own text — from `@router.` to the matching close paren.

    READ BY DEPTH, NOT BY LINE. A decorator spans as many lines as its arguments need, and the
    `dependencies=[…]` list is usually on the second or third. Counting parens is the only way to
    stop exactly at the end of THIS call and never read the next route's answer as this one's.
    """
    depth = 0
    for index in range(start, len(code)):
        char = code[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return code[start:index + 1]
    return code[start:]


def main() -> int:
    missing: list[str] = []
    both: list[str] = []
    checked = 0

    for scope in SCOPES:
        if not scope.is_dir():
            print(f"  {scope.relative_to(ROOT).as_posix()} is missing — this gate cannot answer")
            return 1
        for path in sorted(scope.glob("*.py")):
            code = _code_only(path.read_text(encoding="utf-8"))
            for found in WRITES.finditer(code):
                checked += 1
                text = _decorator(code, code.index("(", found.start()))
                number = code[:found.start()].count("\n") + 1
                where = f"{path.relative_to(ROOT).as_posix()}:{number}"
                requires, exempt = REQUIRES in text, EXEMPT in text
                if requires and exempt:
                    both.append(where)
                elif not requires and not exempt:
                    missing.append(where)

    if missing or both:
        if missing:
            print("  \033[31m✘ a write that never says whether the month has to be paid:\033[0m")
            for where in missing:
                print(f"      \033[31m{where}\033[0m")
        if both:
            print("  \033[31m✘ a write that both requires a subscription and does not:\033[0m")
            for where in both:
                print(f"      \033[31m{where}\033[0m")
        print("\n    Add `Depends(subscribed_write)` to the route's own `dependencies=[…]`, or"
              "\n    `Depends(no_subscription_needed)` if it must keep working while the month is"
              "\n    lapsed — paying us, signing up, or the customer's PDPL rights. Say it on the"
              "\n    route. Do not add a path to this file.")
        return 1

    print(f"  \033[32m✔ {checked} writes each say whether they need a live subscription\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
