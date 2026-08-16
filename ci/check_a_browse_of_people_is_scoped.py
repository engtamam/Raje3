"""A route that hands back MANY people must narrow them to the reader's branch (و-8).

WHAT WENT WRONG, TWICE. `Customer.public()` carries the name, the phone and `last_branch_id`. The
strip along the top of the field screen returned every branch's customers through it, ten at a
time, and a manager scoped to Jeddah read Riyadh's people by name and number without asking for
anything. When that was fixed, its twin — `customers/resolve`, the join behind «من تأخّر» — was
left doing the same thing two hundred at a time.

WHY THE EXISTING GATE MISSED BOTH. `check_branch_scope.py` reads the route's SOURCE TEXT for
branch-ish tokens. Neither route mentions a branch at all: the leaking field rides inside
`public()`. A check that greps for the word cannot see a leak whose word is somewhere else.

THE RULE HERE IS ABOUT SHAPE, NOT VOCABULARY: if a route builds a LIST of people out of `.public()`
(a comprehension — «all of them»), it must also narrow that list by the reader's branch.

AND A TARGETED LOOKUP IS DELIBERATELY NOT A BROWSE. `by-phone` and the customer record return ONE
person the operator already has in front of him, and the customer is shared across the chain
(§12.4) — one person, one balance. What narrows is the BROWSE and the HISTORY. The comprehension is
exactly that line: one `.public()` is a lookup, a list of them is a browse.

No exceptions table. A route that legitimately browses people across every branch does not exist in
this product; the day one does, it argues its case here in words rather than by adding a row.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUBLIC = "public"
#: `visible` AND NOTHING ELSE. Accepting `branch_scope` too was the first version's mistake, and a
#: deliberate sabotage walked straight past it: computing the reader's scope and then not applying it
#: is EXACTLY the shape this gate exists to catch. The narrowing is the call that drops rows.
NARROWERS = ("visible",)


def _is_public_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == PUBLIC)


#: WHICH ANSWERS ARE PEOPLE — read off the key the route returns them under, because that is the
#: one place a route says what it is handing back. Branches and services are listed the same way and
#: are not people: the branch picker carries no numbers, and a service is a price, not a person.
#: Naming them here instead of exempting them keeps the rule readable — this is the list of what the
#: check is ABOUT, not a list of what escapes it.
PEOPLE_KEYS = ("customers", "operators", "staff", "people", "members")


def _is_browse(value: ast.AST) -> bool:
    """A comprehension whose element is `x.public()` — «hand back all of them»."""
    if not isinstance(value, (ast.ListComp, ast.GeneratorExp)):
        return False
    if _is_public_call(value.elt):
        return True
    # `{**c.public(), ...}` counts too: the dict is still the row, with more on it.
    if isinstance(value.elt, ast.Dict):
        return any(v is not None and _is_public_call(v) for v in value.elt.values)
    return False


def _browses_people(fn: ast.AST) -> bool:
    """Does this route hand back a LIST of PEOPLE?

    Both halves matter. A list of branches is not a leak of anybody, and a single person is a
    lookup the operator already has in front of him — the customer is shared across the chain
    (§12.4). What narrows is the browse.
    """
    for sub in ast.walk(fn):
        if not isinstance(sub, ast.Dict):
            continue
        for key, value in zip(sub.keys, sub.values):
            if (isinstance(key, ast.Constant) and key.value in PEOPLE_KEYS
                    and _is_browse(value)):
                return True
        # `return {"customers": kept}` — the comprehension was bound to a name first. Follow the
        # only thing that could have built it: any browse anywhere in a route that answers with a
        # people key.
        for key in sub.keys:
            if isinstance(key, ast.Constant) and key.value in PEOPLE_KEYS:
                for inner in ast.walk(fn):
                    if _is_browse(inner):
                        return True
    return False


def _narrows(fn: ast.AST) -> bool:
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call):
            f = sub.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in NARROWERS:
                return True
    return False


def main() -> int:
    bad = []
    api = ROOT / "services" / "operations" / "app" / "api"
    for path in sorted(api.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            bad.append(f"{path.relative_to(ROOT).as_posix()} · unreadable: {exc}")
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if _browses_people(fn) and not _narrows(fn):
                bad.append(f"{path.relative_to(ROOT).as_posix()}:{fn.lineno} · {fn.name}")

    if bad:
        print("A route hands back a LIST of people without narrowing it to the reader's branch:")
        for line in bad:
            print("  " + line)
        print("\n`public()` carries the name, the phone and `last_branch_id`. Narrow it:")
        print("  scope = await branch_scope(...); SCOPE.visible(rows, scope, field=\"last_branch_id\")")
        return 1
    print("every browse of people is scoped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
