"""`str.isdigit()` is banned in service code: it answers a question nobody here is asking.

WHAT IT COST, AND THE FUNCTION IT BROKE SAYS SO ITSELF. `_normalise_phone` in operations exists,
by its own docstring, so that «the same person is one customer however they were typed» — and it
filtered with `c.isdigit()`. That predicate is true for ARABIC-INDIC DIGIT FIVE and for its Persian
counterpart, so a number typed on an Arabic keyboard passed the filter unchanged, in its own script.
`startswith("966")` then matched nothing, `lstrip("0")` stripped nothing, and the number was stored
exactly as typed. One man, two keyboards, TWO CUSTOMERS — the precise outcome that function was
written to prevent, in the product whose entire premise is recognising the returning customer.

AND A SECOND SITE, WHERE THE PERSON WAS SIMPLY REFUSED. `coupons.normalise` repaired lowercase,
stray spaces and a missing dash — everything a person does to a code except what their keyboard
does to it. Since `code_for` draws from an alphabet containing 2-9, most issued codes carry a
digit: the customer held up a phone showing the code we sent him, the operator typed it, and the
till said no. Neither of them could see why.

WHY BAN THE PREDICATE RATHER THAN FIX THE CALLERS. Because it READS as «is this 0-9» and MEANS «is
this a decimal digit in any script of Unicode», and that gap is invisible at the call site — it
survived review at three sites in this repository, written by people who knew the market. A rule
about this one method needs no judgement, no list of exceptions and no reviewer who happens to
remember. `app/core/digits.py` provides `western()` to fold and `WESTERN` to test against.

`isnumeric()` AND `isdecimal()` ARE HERE FOR THE SAME REASON. `isnumeric()` is true of the
Arabic-Indic digits, of vulgar fractions and of the CJK numerals; `isdecimal()` is true of the
Arabic-Indic ones too. Banning only the one that bit us would leave the other two waiting.

SCOPED TO `services/*/app/` — our own running code. Tests may write `isdigit` while proving what it
does, and this gate has no business editing a proof.

IT READS THE SYNTAX, NOT THE TEXT, AND IT LEARNED THAT THE HARD WAY. The first version matched the
name with a regex and reported eight hits, five of them the very sentences above — the prose that
explains the ban, in the module written to replace it. A gate wrong about most of what it prints is
one people learn to scroll past, and «a comment mentioning a thing is not the thing» is the exact
defect family this repository keeps paying for. So the check is an AST walk: only a real attribute
call on a real expression counts.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

#: The three predicates that claim to be about digits and are not about ours.
BANNED = ("isdigit", "isnumeric", "isdecimal")


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(SERVICES.glob("*/app/**/*.py"))
    if not files:
        # SILENCE IS NOT AGREEMENT.
        print("no service modules found under services/*/app/ — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT checked")
            return 1
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            print(f"cannot parse {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT checked")
            return 1
        lines = text.splitlines()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in BANNED):
                n = node.lineno
                src = lines[n - 1].strip() if n - 1 < len(lines) else ""
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{n}  {src}")

    if hits:
        print(f"{len(hits)} use(s) of a digit predicate that is true for more than 0-9:")
        for line in hits:
            print("  " + line)
        print("\nThese are true for the Arabic-Indic digits a keyboard in this market produces, so")
        print("the value survives the check in a script nothing downstream expects. Fold first with")
        print("`app/core/digits.western()`, then test membership in `digits.WESTERN`.")
        return 1

    print(f"{len(files)} service module(s): no digit predicate that outranges 0-9")
    return 0


if __name__ == "__main__":
    sys.exit(main())
