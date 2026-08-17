"""Halalas become riyals — and riyals become halalas — only in `apps/console/src/money.ts`.

WHAT IT COST, IN THREE PLACES THAT EACH READ FINE ALONE (ح-9، ح-10).

  · `Plans.tsx` advertised a price as `Math.round(minor / 100)`. A plan at 9950 halalas was shown
    as «100 ريال»: fifty halalas above what we charge, on the screen whose entire job is to state
    the price before he agrees to it.

  · `AccountPanes.tsx` rounded an ISSUED INVOICE the same way. A bill of 26950 read «270 ريال»
    while 269.50 left his card. Reconciling our screen against his bank statement produces a
    number that appears on neither side.

  · `Points.tsx` converted the other way with `Number(riyals) * 100` — directly beneath a comment
    reading «no float ever touches money». `2.3 * 100` is `229.99999999999997`, so a reward priced
    at 2.30 was stored as 229 halalas and stayed one halala short on every redemption after it.

WHY A GATE AND NOT THREE FIXES. Each site was written by someone who knew the rule — one of them
wrote the rule down on the line above — and each reached for the arithmetic anyway, because
`/ 100` is obviously right until you ask what happens to the remainder. The rule cannot live in
the reviewer's memory; it has to be the only import that does the conversion.

SCOPED BY WHAT THE NUMBER IS, NOT BY THE OPERATOR. `* 100` on a RATE is correct and common —
`return_rate` on the shop dashboard is a fraction that becomes a percentage, and banning the
operator would be wrong about that and every layout calculation in the app. So this reads the
expression for a money name: `minor`, `halalas`, `amount`, `total`, `price`, `cost_minor`. A
number that is not money is none of this gate's business.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "apps" / "console" / "src"
HOME = "money.ts"

#: Dividing money down to riyals, or multiplying riyals up to halalas.
#:
#: THE OPERATOR ONLY, AND DELIBERATELY SO. This first tried to match the operand as well — and the
#: `* 100` half then missed the very line that motivated it, because `Number(form.get('riyals')
#: || 0) * 100` contains spaces and a pipe that no sane operand pattern admits. Anything written
#: to describe «an expression» is a small language parser and will be wrong about the next one.
#: Scoping is `IS_MONEY`'s job — it reads the whole line, where the money name always is.
CROSSES = re.compile(r"/\s*100\b|\*\s*100\b")

#: The names this product gives to money. `minor` and `halalas` are the units themselves; the rest
#: are the fields that carry them across the wire.
IS_MONEY = re.compile(r"minor|halala|amount|total|price|riyal|cost|fee|discount|subtotal|tax",
                      re.IGNORECASE)


def main() -> int:
    if not SRC.is_dir():
        # A GATE THAT CANNOT READ MUST FAIL LOUDLY.
        print("no apps/console/src — this gate cannot answer, so it refuses to")
        return 1
    if not (SRC / HOME).is_file():
        # SILENCE IS NOT AGREEMENT: with no home for the conversion, «nothing converts money
        # elsewhere» would be a true sentence about a product that cannot show a price at all.
        print(f"apps/console/src/{HOME} is missing — the one place money may cross is gone, and "
              f"this gate will not pass a codebase with nowhere correct to do it")
        return 1

    files = [f for f in sorted(SRC.rglob("*.ts")) + sorted(SRC.rglob("*.tsx"))
             if f.name != HOME and not f.name.endswith(".test.ts")]
    if not files:
        print("no console sources found — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    scanned = 0
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {rel}: {exc}")
            return 1
        scanned += 1
        for n, line in enumerate(text.split("\n"), start=1):
            # PROSE DECIDES NOTHING — the sixth gate this week to need the same treatment. Every
            # one of these three sites explains the rule in a comment, and money.ts's own module
            # note quotes the broken expressions verbatim.
            code = line.split("//")[0]
            if not CROSSES.search(code) or not IS_MONEY.search(code):
                continue
            hits.append(f"{rel}:{n}: {line.strip()[:96]}")

    if hits:
        print(f"{len(hits)} place(s) convert money outside money.ts:")
        for h in hits:
            print("  " + h)
        print("\nDividing by 100 drops the halalas — an invoice of 26950 reads «270 ريال» when")
        print("269.50 was charged. Multiplying by 100 goes through a float: `2.3 * 100` is")
        print("229.99999999999997, so 2.30 is stored as 229 and stays a halala short forever.")
        print("\nImport `riyals`, `riyalsLabel` or `halalas` from money.ts. A rate is different")
        print("and is not read here: `return_rate * 100` is a percentage, not an amount.")
        return 1

    print(f"{scanned} console file(s): money crosses the halalas boundary only in {HOME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
