"""A fleet that cannot RENDER its own messages cannot send a single one — and says nothing.

WHAT THIS WAS WRITTEN AFTER, AND IT IS THE MOST EXPENSIVE SILENCE THIS PRODUCT HAS PRODUCED.

Tamam opened a trigger's preview and read «لا توجد صيغة جاهزة لهذه الرسالة بعد». The library was
fine: 66 templates on the cluster, three of them for that exact trigger. All three failed to
render, with one sentence:

    RenderError: عنوان الموقع العام غير مضبوط (PUBLIC_BASE_URL) — لا تُرسَل رسالة برابطٍ لا يفتح.

Every service wording carries the mandatory tail — the customer's link, which is his right to stop
being messaged — and `render()` correctly refuses to build a message around a link that cannot
open. `PUBLIC_BASE_URL` was empty because the customer page had been switched off by decision.

THE SEND PATH USES THE SAME `render()`. So no reminder, no visit confirmation, nothing carrying the
tail could leave the building — and the failure lands at RENDER time, before anything reaches the
send log, so no screen in the product had a row to show. Two correct decisions, taken months apart,
that nobody put side by side: «switch the customer page off» and «every message carries a link to
it».

THE RULE. If the fleet ships a template whose body requires the public base — and every service
template does — then a deployment that leaves `PUBLIC_BASE_URL` empty is a deployment that can send
nothing. That is a build-time fact, readable from two files, and it must cost a red mark rather
than an owner's evening.

WHAT THIS DOES NOT DO: decide the repair. The link may come back with the customer page, or the
library may grow link-free wordings, or the base may point at a stop-only page. All three are
product decisions; this gate only refuses to let the fleet ship a configuration in which nothing
can be said to anybody.

    python ci/check_a_deployment_can_render_the_messages_it_ships.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALUES = ROOT / "deploy" / "services"
LIBRARY = ROOT / "services" / "operations" / "data"

#: The setting every message with a mandatory tail is built around.
BASE = re.compile(r'^\s+PUBLIC_BASE_URL:\s*"([^"]*)"', re.M)

#: THE MARKER IS THE FILL KIND, NOT A TOKEN IN THE BODY — and the first version of this gate looked
#: for tokens, found none, and reported green over the exact deployment that could not send.
#:
#: A body reads «... {{3}} 🎁»; nothing in it mentions a link. What decides is `fills`, the list
#: naming what each blank MEANS: a blank filled from `invite` is built by `core/invite.py`, which
#: builds a URL, which needs the base. So the gate reads the same field the renderer reads.
NEEDS_BASE = ("invite", "stop", "link", "page")


def main() -> int:
    values = VALUES / "reminders.values.yaml"
    if not values.is_file():
        print("deploy/services/reminders.values.yaml is missing — this gate cannot answer")
        return 1

    declared = BASE.search(values.read_text(encoding="utf-8"))
    if not declared:
        # NOT A PASS. A file that no longer declares the setting is a file this gate cannot judge,
        # and «cannot judge» has never been the same as «fine» in this repository.
        print("reminders declares no PUBLIC_BASE_URL at all — the mandatory tail's base is "
              "unreadable, so whether anything can render is unknown. Declare it, empty or not.")
        return 1

    base = declared.group(1).strip()
    if base:
        print(f"  \033[32m✔ the mandatory tail has a base to point at ({base}) — messages can "
              f"render\033[0m")
        return 0

    # EMPTY. Now the only question left is whether anything we ship actually needs it.
    needing: list[str] = []
    seed = LIBRARY / "templates.seed.json"
    if not seed.is_file():
        print("services/operations/data/templates.seed.json is missing — the library this gate "
              "judges is not where it was. Refusing to report a pass over nothing.")
        return 1
    rows = json.loads(seed.read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else rows.get("templates", [])
    if not rows:
        print("the shipped library is empty — nothing to judge, and that is its own problem")
        return 1
    for row in rows:
        if not row.get("active", True):
            continue
        if any(str(fill) in NEEDS_BASE for fill in (row.get("fills") or [])):
            needing.append(str(row.get("name") or row.get("type") or "?"))

    if not needing:
        print("  \033[32m✔ PUBLIC_BASE_URL is empty and nothing shipped requires it\033[0m")
        return 0

    print("  \033[31m✘ PUBLIC_BASE_URL is empty, and the library ships wordings built around it:"
          "\033[0m")
    # THE COUNT FIRST, AND A HANDFUL OF NAMES. Thirty-six red lines is a wall a reader scrolls
    # past; «36 wordings — among them …» is the same fact in a sentence he finishes.
    print(f"      \033[31m{len(needing)} wording(s) — among them {', '.join(needing[:3])}\033[0m")
    print("\n    Every one of those fails at RENDER — before the send log, before any screen — so "
          "the fleet\n    sends nothing and reports nothing. Give the tail a base, ship wordings "
          "that do not need one,\n    or point it at a page that only stops messages. Do not "
          "exempt it here.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
