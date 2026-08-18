"""A schedule's natural key is built in ONE place, and every writer asks that place.

WHAT THIS IS, AND WHY A SECOND COPY IS NOT A STYLE PROBLEM. A schedule row is stored under a key
derived from what it is about — tenant, customer, car, service, kind — so that a second visit
COLLIDES with the pending row and updates it instead of adding another. The key IS the identity;
`id` is only for tracing.

So a writer that builds the key slightly differently does not write to the wrong place and fail.
It writes to a place NOTHING ELSE READS, and both rows survive: the original, untouched, and a
copy that looks authoritative and governs nothing.

MEASURED ON THE CLUSTER, NOT IMAGINED. Two rows, one schedule id, two keys:

    a76d…|sub_3de4…|ast_b0a6…|srv_149b…|reminder   state=pending     <- the tick reads this
    a76d…|sub_3de4…|srv_149b…|reminder             state=cancelled   <- the owner's press landed here

The owner pressed «أوقفها». The screen said done, the audit recorded it, `reason` reads «ألغاه
المالك» — and the reminder is still pending and will still be sent.

THE ASSET IS WHAT SPLIT THEM. `Schedule.key` grew a car segment when the cycle moved from the
customer to the car (#206). Two helpers did not follow, so every shop that services CARS — this
product's core market — has a cancel that cannot cancel, a new visit that cannot supersede last
month's reminder (spec 5.6), and a redeem-merge that duplicates instead of merging.

THE RULE. Only `core/models.py` may spell the key out. Everywhere else asks for it. A helper that
reformats the same fields is a second definition, and the second one is always the one that drifts
— this is its third round here, so it is a rule now rather than a habit.

    python ci/check_one_key_names_a_schedule.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REMINDERS = ROOT / "services" / "reminders" / "app"
MODELS = REMINDERS / "core" / "models.py"

#: THE SCHEDULE KEY'S OWN SHAPE, AND NOT ANY OTHER KEY. Every collection in this service builds
#: keys out of interpolated fields — rules, send log, settings, reason choices, watermarks — and
#: the first version of this pattern («a field, then a pipe») flagged twenty-nine innocent lines.
#: What identifies THIS key is the combination: the customer AND the kind of message, in one
#: expression. `kind` appears in no other key here.
SPELLS_A_KEY = re.compile(r"\{[^{}]*\bsubject_ref\b[^{}]*\}\s*\|")

#: READ OVER A WINDOW, NOT A LINE, because the real ones are written across three lines.
WINDOW = 240

#: COMMENTS AND DOCSTRINGS DESCRIBE THE KEY CONSTANTLY — «tenant|subject|service|kind» is how the
#: rule is explained, including in this file. Explaining is not building, so prose is stripped
#: before anything is looked for. A gate that cannot tell the two apart would be answered by
#: deleting the explanation, which is the worst outcome available.
COMMENT = re.compile(r"#.*$", re.M)
DOCSTRING = re.compile(r'("""|\'\'\')(?:.|\n)*?\1')


def _code_only(source: str) -> str:
    """Prose blanked OUT, never deleted — the line numbers have to still mean something.

    The first version removed it, and then reported line 90 of a file whose line 90 was a
    docstring three hundred characters earlier. A gate that points at the wrong line sends its
    reader looking for a defect that is not there, and the next person believes the gate less.
    """
    def blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return COMMENT.sub("", DOCSTRING.sub(blank, source))


def main() -> int:
    if not MODELS.is_file():
        print("services/reminders/app/core/models.py is missing — this gate cannot answer")
        return 1

    offenders: list[str] = []
    for path in sorted(REMINDERS.rglob("*.py")):
        if path == MODELS:
            continue  # the one place that may
        code = _code_only(path.read_text(encoding="utf-8"))
        for found in SPELLS_A_KEY.finditer(code):
            if "kind" not in code[found.start():found.start() + WINDOW]:
                continue
            number = code[:found.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(ROOT).as_posix()}:{number}")

    if offenders:
        print("  \033[31m✘ the schedule key is spelled out away from models.py:\033[0m")
        for offender in offenders:
            print(f"      \033[31m{offender}\033[0m")
        print("\n    A second spelling does not fail — it writes where nothing reads, and both "
              "rows live on.\n    The owner's «أوقفها» landed on one of them while the tick kept "
              "the other. Ask\n    `key_of(row)` instead. Do not exempt it here.")
        return 1

    print("  \033[32m✔ one place names a schedule, and every writer asks it\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
