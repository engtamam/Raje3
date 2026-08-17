"""What the screen accepted, the send must accept — the same pattern and the same cap everywhere.

WHAT IS DUPLICATED, AND THE COMMENT THAT ASSERTS IT. `services/campaigns/app/core/preview.py`
and `services/reminders/app/core/rendering.py` each carry a regex for what an offer may say —
«20%» or «50 ريال» — and they are character-for-character identical. The campaigns copy even says
so in prose: «The same shape the send validates (reminders/core/rendering.py)». That sentence is
the only thing holding them equal, and a sentence holds nothing.

WHAT DRIFT COSTS, AND IT IS THE EXPENSIVE DIRECTION. The two are not read at the same moment.
campaigns judges the value while the owner is TYPING it, reminders judges it at SEND. So if
campaigns ever loosens — a new form somebody adds for a promotion — the owner sees his offer
accepted, the preview renders, the launch button works, the campaign starts, and then every single
message fails to render at the send. He is told his campaign is running. Nothing arrives. The
reverse drift is merely rude: a value refused at a screen that had just shown it as valid.

WHY THERE IS NO ONE PLACE TO PUT IT. These are separate deployables with no shared package in
this repository, which is a deliberate shape, not an oversight. A constant cannot be shared without
inventing a library and a release for it, so what CAN be shared is the requirement that they agree
— checked here, on every push, in the place where both are visible at once.

DISCOVERED BY WHAT THE PATTERN CONTAINS, NOT BY A LIST OF THE TWO FILES. Any regex in any service
that spells the currency is in scope, so a third service that grows its own copy next month is
compared the day it lands rather than the day it diverges. A list of two filenames here would be
the same kind of promise as the comment this gate exists to replace.

AND THE LENGTH CAP ON HIS OWN SENTENCE, WHICH IS THE SAME TWIN UNDER A SECOND NAME. `campaigns`
calls it `MAX_OWNER_TEXT`, `reminders` calls it `MAX_OWNER_FIELD`, both are 60, both guard the
same free line he writes, and both raise the same sentence — «النص أطول من 60 حرفاً». Two names
for one number is worse than two copies of it: nothing that greps for the name finds the pair, and
this one nearly stayed open for that reason alone. So the rule is scoped by the PREFIX every such
cap already shares rather than by the two names, and a rename cannot quietly leave the group.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

#: THE CURRENCY IS WHAT MAKES A REGEX ONE OF THESE. A pattern that spells «ريال» is deciding what
#: an amount of money may look like; there is no other reason for that word to be inside one.
CURRENCY = "ريال"

#: `NAME = re.compile(r"…")` on one line, which is how both of them are written. A pattern split
#: across lines would not be found — and that is why an empty result FAILS below rather than
#: passing quietly, which is the failure this repository has already paid for twice.
ASSIGNED = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*=\s*re\.compile\(\s*r?(\"[^\"]*\"|'[^']*')",
                      re.M)

#: THE CAP ON HIS OWN SENTENCE, MATCHED BY PREFIX BECAUSE THE TWO NAMES DISAGREE. `MAX_OWNER_TEXT`
#: in campaigns and `MAX_OWNER_FIELD` in reminders are one number under two names — which is why no
#: search for either name ever turned up the pair. Reading the prefix means a third spelling
#: (`MAX_OWNER_LINE`, say) joins the comparison instead of escaping it.
A_CAP = re.compile(r"^(MAX_OWNER[A-Z0-9_]*)\s*=\s*(\d+)", re.M)


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    found: list[tuple[str, str, str]] = []      # (pattern, "service/path", NAME)
    caps: list[tuple[int, str, str]] = []       # (value, "service/path", NAME)
    for path in sorted(SERVICES.rglob("*.py")):
        if "/tests/" in path.as_posix():
            # SCOPE, NOT PATTERN. A test may deliberately hold a WRONG value to prove the
            # production one refuses it; comparing those would make this gate wrong about most of
            # its hits, which is how a gate teaches people to scroll past it.
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT checked")
            return 1
        for name, literal in ASSIGNED.findall(text):
            pattern = literal[1:-1]
            if CURRENCY in pattern:
                found.append((pattern, path.relative_to(ROOT).as_posix(), name))
        for name, value in A_CAP.findall(text):
            caps.append((int(value), path.relative_to(ROOT).as_posix(), name))

    if len(found) < 2:
        # SILENCE IS NOT AGREEMENT. One copy means the sweep stopped seeing the other, not that
        # the duplication was resolved — resolving it would take a shared package, and there is
        # none. Either way the answer is «re-point this gate», never «green».
        print(f"found {len(found)} money-value pattern(s) under services/, expected at least 2 — "
              f"either the offer validators moved or they are no longer written as a one-line "
              f"`NAME = re.compile(r\"…\")`. This gate is reading for a shape that changed and "
              f"will not guess.")
        return 1

    if len(caps) < 2:
        print(f"found {len(caps)} owner-text cap(s) under services/, expected at least 2 — the "
              f"`MAX_OWNER…` caps moved or were renamed past this gate's reading. It will not "
              f"assume they agree.")
        return 1

    if len({v for v, _, _ in caps}) > 1:
        print(f"{len(caps)} services cap the owner's own sentence, at DIFFERENT lengths:")
        for value, rel, name in sorted(caps):
            print(f"  {rel}  {name} = {value}")
        print("\nHe writes one line and two services measure it. The screen accepts what the send")
        print("will cut, so the sentence he approved is not the sentence that arrives — and the")
        print("first he hears of it is a customer reading half a promise.")
        return 1

    patterns = {p for p, _, _ in found}
    if len(patterns) > 1:
        print(f"{len(found)} services judge a money-off value, and they do NOT agree:")
        for pattern, rel, name in found:
            print(f"  {rel}  {name}")
            print(f"      {pattern}")
        print("\nThese are read at different moments: one while the owner is typing his offer, one")
        print("at the send. When the typing side is the looser of the two, he is told the campaign")
        print("launched and not one message renders — the failure is silent, and it is total.")
        return 1

    print(f"{len(found)} money-value validators across services/: all judge by the same pattern; "
          f"{len(caps)} owner-text caps: all {caps[0][0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
