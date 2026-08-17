"""The sentence a customer is shown must be the sentence we store as their consent.

WHAT THIS PROTECTS. reminders records marketing consent as an append-only row carrying the exact
statement text and its version (services/reminders/app/core/consent.py). portal renders that
statement on the one screen where a customer grants it (services/portal/app/core/onescreen.py).
Two services, two images, no shared package — so the text is written twice.

THE DAY THEY DIVERGE, nothing breaks and nothing is logged. The screen says one thing, the record
attests to another, and the failure is only discovered by whoever asks us to produce the consent —
at which point the answer is that we have a record of words the customer never read. That is worse
than having no record: an inaccurate one is affirmatively misleading, and it is the document the
regulator reads first.

Editing either file is easy and reasonable — "four messages a month" becomes "three", a comma
moves. The edit is correct in the file it happens in and silently wrong across the pair.

THE RULE, WITH NO EXCEPTIONS TABLE. The STATEMENT literal in the two files is byte-identical, and
so is the fallback used when the shop's name is unknown. Wording changes to a consent statement are
a deliberate act — with STATEMENT_VERSION bumped, so a grant made under the old words is never
re-read as agreement to the new ones — and this check makes the pair move together.

WHAT IT CANNOT SEE, said plainly:
  · a THIRD copy in a file this gate does not name. The two paths below are the whole search;
  · whether the sentence is TRUE — that four is really the monthly cap is a product fact, checked
    by the sending gate, not by string comparison;
  · a version bumped in one file and not the other. That is checked here too, for the same reason.

    python ci/check_the_consent_sentence_shown_is_the_sentence_recorded.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

RECORDED = ROOT / "services" / "reminders" / "app" / "core" / "consent.py"
SHOWN = ROOT / "services" / "portal" / "app" / "core" / "onescreen.py"

# The fallback subject, for a grant recorded when the shop's name could not be read. It is part of
# the sentence, so a mismatch here is the same defect one word along.
FALLBACK = "المنشأة"


def _literal(path: pathlib.Path, name: str) -> str | None:
    """The value of a module-level `name = "..."`, read from the SOURCE rather than by importing.

    Importing would mean running one service's code inside another's dependency set, and a gate
    that needs the product installed to run is a gate that stops running.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    value = ast.literal_eval(node.value)
                except ValueError:
                    return None
                return value if isinstance(value, str) else None
    return None


def main() -> int:
    problems: list[str] = []

    for path in (RECORDED, SHOWN):
        if not path.is_file():
            # SILENCE IS NOT AGREEMENT. A missing file makes every comparison below vacuous, and a
            # gate that passes because it found nothing to compare is the defect it is checking for.
            print(f"FAIL: {path.relative_to(ROOT).as_posix()} is missing — this gate compared "
                  f"nothing, which is not the same as the two sentences agreeing")
            return 1

    recorded = _literal(RECORDED, "STATEMENT")
    shown = _literal(SHOWN, "STATEMENT")
    if recorded is None or shown is None:
        missing = RECORDED if recorded is None else SHOWN
        print(f"FAIL: no module-level STATEMENT literal in "
              f"{missing.relative_to(ROOT).as_posix()} — either the statement moved, or it stopped "
              f"being a literal this gate can read. Both leave the pair unchecked.")
        return 1

    if recorded != shown:
        problems.append("the two statements differ:\n"
                        f"    recorded (reminders): {recorded!r}\n"
                        f"    shown    (portal):    {shown!r}")

    # The fallback is part of the sentence whenever tenant-service could not be read, which is
    # precisely when nobody is watching. Both must reach for the same word.
    for path in (RECORDED, SHOWN):
        if FALLBACK not in path.read_text(encoding="utf-8"):
            problems.append(f"{path.relative_to(ROOT).as_posix()} no longer falls back to "
                            f"{FALLBACK!r} when the shop's name is unknown — so the two files "
                            f"name a different sender in the one case nobody sees")

    if problems:
        print("FAIL: the consent sentence shown is not the consent sentence recorded")
        for p in problems:
            print(f"  {p}")
        print("\n  Change both, and bump STATEMENT_VERSION in reminders — a grant made under the "
              "old wording must never be read as agreement to the new one.")
        return 1

    print(f"OK: the consent statement is identical in both services ({len(recorded)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
