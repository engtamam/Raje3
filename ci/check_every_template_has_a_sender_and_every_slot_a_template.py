"""A wording nothing can send, and a value nothing can carry, are the same defect twice.

WHAT THIS CATCHES, AND IT WAS FOUND BY COUNTING RATHER THAN BY READING.

  · SEVEN of the twenty-two wordings in the specification (parsed fresh by `gen_templates.parse` —
    no stored intermediate file since 2026-09-13) are named by no line of code anywhere — not a
    campaign goal, not a trigger, not a path. They are still submitted to Meta the moment a shop
    connects (#113 uploads the library whole), so each one waits in review and eats the shop's
    template allowance for a message nobody can ever send.

  · AND ONE OF THE SEVEN IS THE END OF A CHAIN WE BUILT ON PURPOSE. `mkt_coupon` is the only
    wording with a `code` blank. `tick.py` mints a unique coupon per customer, hands it to
    `campaign_slots`, and `rendering.py` fills `code` with it — into a template that cannot be
    selected. Every campaign carrying a coupon goes out through `mkt_offer`, which has no code
    blank at all, so the whole of #245 — a code unique to one person, spent once, that measures
    the campaign — reaches nobody. Nothing failed. Nothing was logged. The feature simply ends in
    the air one step before the customer.

TWO QUESTIONS, AND THE SECOND IS THE ONE THAT FOUND THE COUPON:

  1. does every wording have something that can send it?
  2. does every KIND OF BLANK the engine knows how to fill appear in some wording that can be
     sent? A `fills` entry the renderer computes and no live template declares is work done for a
     reader that does not exist.

NO EXEMPTIONS TABLE. A wording with no sender is either wired or deleted — this file will not
carry a list of ones we have decided to forgive, because that list is how the seven survived a
year of review.

    python ci/check_every_template_has_a_sender_and_every_slot_a_template.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_templates import build, parse  # noqa: E402

#: Where a wording could be named by something able to send it: the services' own code and the
#: console. NOT tests — a test naming a dead template is what «covered» looks like when nothing
#: ships it, and NOT the seed itself, which is the thing being checked.
SOURCES = (
    (ROOT / "services", "*.py"),
    (ROOT / "apps" / "console" / "src", "*.ts"),
    (ROOT / "apps" / "console" / "src", "*.tsx"),
)

#: Blanks whose value comes from the message's own subject rather than from a template's meaning:
#: every wording has a name and a shop, and a `stop_link` is the law on any marketing text. They
#: are not a feature that can be stranded, so their absence from a live template proves nothing.
UNIVERSAL_FILLS = {"system", "stop_link", "invite"}


def _sources() -> str:
    out: list[str] = []
    for root, pattern in SOURCES:
        if not root.is_dir():
            continue
        for path in root.rglob(pattern):
            text = path.as_posix()
            if "__pycache__" in text or "/tests/" in text:
                continue
            if path.name.endswith((".test.ts", ".test.tsx")):
                continue
            out.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(out)


def main() -> int:
    types, problems = parse()
    if problems:
        print(f"the specification itself has {len(problems)} problem(s) — run "
              f"`python ci/gen_templates.py` for detail")
        return 1
    seed = build(types)
    code = _sources()

    dead = [t["name"] for t in seed["types"] if t["name"] not in code]
    live = [t for t in seed["types"] if t["name"] in code]

    # WHAT A SENDABLE WORDING CAN ACTUALLY CARRY, which is the set the engine may usefully compute.
    carried = {fill for t in live for fill in (t.get("fills") or [])} | UNIVERSAL_FILLS
    stranded = sorted({fill for t in seed["types"] for fill in (t.get("fills") or [])} - carried)

    if dead or stranded:
        if dead:
            print("  \033[31m✘ wordings that nothing can send, and that Meta reviews anyway:\033[0m")
            for name in dead:
                print(f"      \033[31m{name}\033[0m")
        if stranded:
            print("  \033[31m✘ blanks the engine fills that no sendable wording declares:\033[0m")
            for fill in stranded:
                print(f"      \033[31m{fill}\033[0m")
        print("\n    Wire it to a goal or a trigger, or delete it from the seed. A wording with no"
              "\n    sender still costs the shop a template slot and a review; a blank with no"
              "\n    wording is a value computed for nobody — that is how the coupon in #245 came"
              "\n    to be minted per customer and delivered to none of them.")
        return 1

    print(f"  \033[32m✔ {len(live)} wordings each have a sender, and every blank has a wording"
          f"\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
