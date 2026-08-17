"""A numeric box on a screen must FOLD what he typed, never silently delete it.

WHAT THE SCREENS DID, AND IT IS WORSE THAN A WRONG VALUE ARRIVING. Seven inputs in the console
filtered the typed string with `/\\D/g` or `/[^0-9]/g`. In JavaScript both mean exactly `0-9`, so a
keyboard set to Arabic produced characters that were deleted between the key and the state. The
operator types and the field STAYS EMPTY. There is no error to read, nothing to correct, and no
reason offered — the screen simply does not respond to him.

WHERE THAT LANDS. `WhoIsSaving` is the PIN prompt on the field screen, entered with a customer
standing there, dozens of times a day. `Team` is where the owner sets that PIN, so a shop could be
locked out of a code it was never able to type. `Visit` takes the customer's phone AND the plate.
`Connect` takes the six-digit code that registers the shop's number with Meta.

AND ONE SCREEN CONTRADICTED ITSELF. `Visit.tsx` guards the plate with `/[0-9٠-٩]/` beneath a
comment stating that a plate is typed on an Arabic keyboard as often as a Latin one and that
refusing those digits would refuse a correct plate. Two hundred lines above, `formatPlate` — which
runs on EVERY KEYSTROKE — stripped them, so the guard could never see the character it exists to
accept. `formatPlate('ا ب ج ٤٥٦')` returned the empty string. The defence was dead and the operator
was blocked by the screen that meant to admit him.

THE RULE, WITH NO EXCEPTIONS TABLE: these two patterns do not appear in console source at all.
`apps/console/src/digits.ts` provides `western()` and `digitsOnly()`, and is written as a
membership test rather than a negated class SO THAT IT NEEDS NO CARVE-OUT HERE — a rule with one
exception is a rule somebody extends to two.

IT READS THE SYNTAX-BEARING LINES ONLY. Comments explaining the ban are not the ban being broken;
this repository has already shipped one gate that reported its own documentation as a violation.

arabic-indic-digits: intentional — this gate is about those characters, so it must name them.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "apps" / "console" / "src"

#: `.replace(/\D/g, …)` and `.replace(/[^0-9]/…)` — the two spellings of «delete anything that is
#: not a Western digit», applied to a string a person typed.
BANNED = re.compile(r"\.replace\(\s*/(?:\\D|\[\^0-9\])")

#: A line that is entirely comment. Not a parser — the check below only needs to skip prose, and
#: the patterns above are distinctive enough that a false skip is safer than a false accusation.
COMMENT = re.compile(r"^\s*(?://|/?\*|\*/)")


def main() -> int:
    if not CONSOLE.is_dir():
        print("no apps/console/src — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(CONSOLE.rglob("*.ts")) + sorted(CONSOLE.rglob("*.tsx"))
    if not files:
        # SILENCE IS NOT AGREEMENT.
        print("no console sources found — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT checked")
            return 1
        for n, line in enumerate(text.splitlines(), start=1):
            if COMMENT.match(line):
                continue
            if BANNED.search(line):
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{n}  {line.strip()}")

    if hits:
        print(f"{len(hits)} input(s) that delete a digit instead of folding it:")
        for line in hits:
            print("  " + line)
        print("\nIn JavaScript `\\D` and `[^0-9]` both mean exactly 0-9, so what an Arabic keyboard")
        print("produces is removed as he types it and the box stays empty — no error, nothing to")
        print("correct. Use `digitsOnly()` from apps/console/src/digits.ts, which folds first.")
        return 1

    print(f"{len(files)} console source(s): every numeric box folds rather than deletes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
