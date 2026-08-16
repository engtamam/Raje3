#!/usr/bin/env python3
"""EVERY BLANK IN A TEMPLATE SAYS WHO FILLS IT — the system, the catalogue, or the owner (ط-4).

A WhatsApp template body is a sentence with numbered blanks: «أهلاً {{1}}، من {{2}} لك خصم {{3}}
على {{4}}. ساري حتى {{5}}». The words are fixed — Meta approved them — so the ONLY thing a shop
decides is what goes in the blanks. `fills` is the list that says, per blank and in order, who
that is:

    system     we know it at send time: his name, the shop, a points balance, a receipt number.
    catalogue  a tap on the shop's own service list. Never typed, so it cannot be misspelled
               into a service that does not exist.
    amount     a typed value with a shape — «20%» or «50 ريال». Typed rather than free precisely
               so «خصم كبير», which promises nothing an operator at a counter can honour, cannot
               be sent to a customer.
    code       a coupon code.
    date       the day it stops.
    owner      the ONE free blank, where the message has nothing but the shop's own words to put
               there — «جديد في {{2}}: {{3}}». At most one per template.

WHAT WENT WRONG, AND IT WAS INVISIBLE FROM EVERY DIRECTION. The seed file declared no `fills` at
all, and the seeder did not send the field. So all twenty-two templates arrived declaring nothing,
and every reader downstream took the default:

  * `render_message` resolved each blank to «system», could not name one, and drew «…» — so a
    preview of an offer read «لك خصم … على …» and the owner had no way to know why;
  * `sanitise_owner_text(required=needs_text)` computed `needs_text` as False for every template,
    so the one screen that asks for a free line never required it AND never delivered it;
  * the campaign screen drew a free-text box for goals whose message has no free blank, so the
    owner typed a sentence that reached nobody.

Nothing failed anywhere. The library validates `fills` when it is present and had nothing to
validate — a check that is correct and silent about an empty input, which is how a missing
declaration outlives every test written about the thing it declares.

WHY A GATE. The seed is data, and data has no type checker. The day somebody adds the
twenty-third template, the failure mode is not an error — it is one more template quietly
declaring that everything in it is ours to fill.

NO EXCEPTIONS TABLE. A template whose blanks nobody can name is a template nobody can fill, and
there is no shape of one that is fine to ship.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEED = ROOT / "deploy" / "seed" / "templates.json"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The same six the library accepts (operations/core/templates.py FILLS). Named here rather than
# imported: this gate reads a data file and must not need a service's package on the path — but
# the two lists disagreeing is itself a defect, so the gate says so below.
KINDS = ("system", "catalogue", "owner", "amount", "code", "date")

# The blank the shop writes itself. One at most, and the library refuses a second — this gate
# catches it in the seed instead of at the far end of a deploy.
FREE = "owner"


def _slots(tones: dict) -> list[int]:
    """The distinct blank numbers used across this template's three tones.

    ACROSS ALL THREE, because they are one template to Meta: the same approved body in three
    voices, and a blank that exists in the warm tone and not the brief one is a template whose
    variable count depends on which voice the shop picked.
    """
    text = " ".join(str(v) for v in (tones or {}).values())
    return sorted({int(n) for n in re.findall(r"\{\{(\d+)\}\}", text)})


def main() -> int:
    bad: list[str] = []
    try:
        data = json.loads(SEED.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # REPORTED, NOT SKIPPED. An unreadable seed is the one state in which this gate would
        # otherwise print «ok» over a library nobody can fill.
        print(f"{C_R}cannot read {SEED.relative_to(ROOT).as_posix()}: {exc}{C_N}")
        return 1

    types = data.get("types") or []
    if not types:
        print(f"{C_R}no templates in the seed — this gate has nothing to check, which is not "
              f"the same as finding nothing wrong{C_N}")
        return 1

    for entry in types:
        name = str(entry.get("name") or "?")
        slots = _slots(entry.get("tones") or {})
        fills = list(entry.get("fills") or [])

        if not fills:
            bad.append(f"{name}: declares no fills — every blank in it defaults to «system», "
                       f"so nothing the shop types can reach the message")
            continue
        if len(fills) != len(slots):
            bad.append(f"{name}: {len(slots)} blanks in the body, {len(fills)} fills declared — "
                       f"the list is read BY POSITION, so one missing entry shifts every blank "
                       f"after it onto the wrong source")
            continue
        unknown = [f for f in fills if f not in KINDS]
        if unknown:
            bad.append(f"{name}: unknown fill kind {unknown} — the readers branch on these by "
                       f"name and treat anything else as «system»")
        if fills.count(FREE) > 1:
            bad.append(f"{name}: asks the owner to write {fills.count(FREE)} free blanks. One at "
                       f"most — two is a form he abandons halfway, and the customer never hears")

    if bad:
        print(f"{C_R}a template does not say who fills its blanks{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Declare `fills` beside `tones`: one kind per blank, in order, from")
        print(f"  {KINDS}.")
        return 1
    print(f"{C_G}ok{C_N}  {len(types)} templates — every blank says who fills it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
