#!/usr/bin/env python3
"""ONE FACT, ONE PLACE — AND THE PRODUCT'S TIMEZONE IS A FACT (ج-7).

WHAT THIS FOUND. `config/product.json` declares `"timezone": "Asia/Riyadh"` and NO SERVICE READ IT.
Instead `timezone(timedelta(hours=3))` was typed out in EIGHT files across four services:

    reminders/core/gate.py          — decides the quiet hours, so it decides when a real customer
                                      is messaged
    reminders/core/rendering.py     — the dates printed inside those messages
    campaigns/core/tick.py          — when a scheduled campaign is allowed to fire
    campaigns/api/v1/campaigns.py   — what the owner is shown before he presses send
    campaigns/adapters/peers        — the same arithmetic, a third time in one service
    operations/api/internal.py      — the busiest-hours grid
    portal/core/render.py           — the timestamps on the customer's own page
    operations/core/riyadh.py       — the one that was already a named constant

EIGHT, NOT SIX. THIS GATE USED TO SAY SIX, and it was wrong in both directions: it listed
`portal/core/render.py` as no longer writing the offset — it did, in a local variable the gate's
own AST check saw perfectly well — and it did not count `operations/core/riyadh.py`. The number in
a register drifts from the number in the tree; that is why the register was replaced by this.

NO DEFECT EXISTED AT ANY POINT, AND THAT IS THE POINT. Saudi Arabia has no daylight saving, so `+3`
is correct all year and all eight agreed. The cost arrives the day the number has to change — a
second country, a per-tenant setting — and it arrives as SEVEN changing and one not. Which one is
not predictable; that a fact copied eight times eventually becomes seven facts and a different one
is.

THE RULE NOW HAS NO EXCEPTIONS TABLE, because the exceptions are gone. A fixed UTC offset may be
constructed in exactly one file per service — `app/core/riyadh.py` — and everywhere else imports
it. The previous version of this gate carried a `KNOWN` set of six paths, which is a table of
exceptions by another name: it stopped the seventh while blessing the six, and a list that must be
edited by hand to stay true is a list that stops being true.

AND THE DECLARATION IS LOAD-BEARING AT LAST. This gate reads `config/product.json` and refuses any
service whose constant disagrees with the timezone declared there. Before, that file could have
said `Europe/Berlin` and nothing in the product would have noticed.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
PRODUCT = ROOT / "config" / "product.json"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

#: The one file per service that may construct the offset. Not an exception list: it is the RULE's
#: subject, and it is the same name in every service so «where does the clock live» has one answer.
HOME = "riyadh.py"

#: The timezones this product knows how to be, and the offset each one means. A name here without
#: an offset is a deployment nobody has thought through, and is refused rather than assumed.
OFFSETS = {"Asia/Riyadh": 3}


def _hardcoded_offsets(tree: ast.AST) -> list[int]:
    """`timedelta(hours=<n>)` inside a `timezone(...)` call — a fixed UTC offset, written out.

    Reads the CALL, not the text, so a docstring quoting the broken expression — and every file
    changed by this task quotes it — cannot be mistaken for one.
    """
    def _named(fn: ast.AST, name: str) -> bool:
        # BOTH SPELLINGS. `timezone(...)` and `datetime.timezone(...)` are the same call, and the
        # first version of this gate read only the bare Name — so `_dt.timezone(_dt.timedelta(
        # hours=3))`, which is how the consolidated constant is actually written, was invisible to
        # it. A gate blind to the import style a file happens to use is a gate with a silent
        # exception in it.
        return ((isinstance(fn, ast.Name) and fn.id == name)
                or (isinstance(fn, ast.Attribute) and fn.attr == name))

    out: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _named(node.func, "timezone")):
            continue
        for arg in node.args:
            if not (isinstance(arg, ast.Call) and _named(arg.func, "timedelta")):
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
    if not PRODUCT.is_file():
        # A GATE THAT CANNOT READ ITS AUTHORITY MUST FAIL LOUDLY.
        print(f"{C_R}config/product.json is missing — the timezone the code must agree with has "
              f"no declaration, so this gate cannot answer{C_N}")
        return 1

    try:
        # `locale.timezone`, NOT a top-level key — and reading the wrong path is how a gate
        # reports «declares «»» about a file that declares it plainly. Missing is an error rather
        # than a default: a product whose timezone is unstated has no answer for this gate to
        # enforce, and inventing one here would put the fact in a THIRD place.
        declared = json.loads(PRODUCT.read_text(encoding="utf-8")).get("locale", {}).get(
            "timezone", "")
    except (OSError, ValueError) as exc:
        print(f"{C_R}cannot read config/product.json: {exc}{C_N}")
        return 1
    if declared not in OFFSETS:
        print(f"{C_R}config/product.json declares «{declared}», which this gate has no offset "
              f"for{C_N}")
        print(f"  Add it to OFFSETS — deliberately, in a diff somebody reviews. Guessing the "
              f"offset of a timezone is how a product messages people at 4am.")
        return 1
    expected = OFFSETS[declared]

    stray: list[str] = []
    homes: dict[str, int] = {}
    unreadable: list[str] = []

    for path in sorted(SERVICES.rglob("*.py")):
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            unreadable.append(f"{rel}: cannot read it — {exc}")
            continue
        offsets = _hardcoded_offsets(tree)
        if not offsets:
            continue
        if path.name == HOME and path.parent.name == "core":
            homes[rel] = offsets[0]
            if len(set(offsets)) > 1:
                stray.append(f"{rel}: writes more than one offset ({sorted(set(offsets))})")
        else:
            stray.append(f"{rel}: a fixed UTC offset, typed out")

    if unreadable:
        print(f"{C_R}files this gate could not read — «could not tell» is not «nothing "
              f"found»{C_N}")
        for line in unreadable:
            print(f"  {line}")
        return 1

    if not homes:
        # SILENCE IS NOT AGREEMENT: no home and no strays would print «ok» for a product that has
        # lost its clock entirely.
        print(f"{C_R}no service defines the clock at all — no app/core/{HOME} constructs an "
              f"offset, so this gate is guarding a rule nothing implements{C_N}")
        return 1

    if stray:
        print(f"{C_R}the product's clock is written by hand outside app/core/{HOME}{C_N}")
        for line in stray:
            print(f"  {line}")
        print(f"\n  It is right today and it is a copy of a fact that already has a home. The day")
        print(f"  the number changes, the copy nobody remembered is the one that keeps messaging")
        print(f"  people at 4am. Import RIYADH from your service's app/core/{HOME}.")
        return 1

    wrong = {rel: n for rel, n in homes.items() if n != expected}
    if wrong:
        print(f"{C_R}a service's clock disagrees with config/product.json «{declared}» "
              f"(UTC+{expected}){C_N}")
        for rel, n in sorted(wrong.items()):
            print(f"  {rel}: UTC+{n}")
        print("\n  The declaration is the product's answer, and a service that quietly differs")
        print("  from it sends at a different hour than every other service in the same shop.")
        return 1

    print(f"{C_G}ok{C_N}  {len(homes)} service clock(s), all UTC+{expected} as "
          f"config/product.json declares, and nothing writes an offset anywhere else")
    return 0


if __name__ == "__main__":
    sys.exit(main())
