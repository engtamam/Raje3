"""An input that declares itself numeric must fold what he types before it becomes state.

THE COMPANION TO `check_a_screen_does_not_delete_what_he_typed.py`, AND THE HALF IT CANNOT SEE.
That gate bans deleting a digit. This one catches the opposite omission: a box that does nothing at
all, and passes an Arabic-Indic number through untouched to a service that will not recognise it.

WHAT IT COST AT THE WORST POSSIBLE DOOR. `Door.tsx` is sign-in and sign-up. Both phone fields
declare `type="tel"` and neither folded, so an owner whose keyboard is set to Arabic typed his own
number, the request carried digits identity-service does not match, and the sign-in was refused —
with a message blaming his phone or his password. He is locked out of the product he pays for by a
keyboard setting, while our own text tells him he mistyped his own number.

SCOPED BY WHAT THE AUTHOR ALREADY DECLARED, so there is no list here to fall behind. An element
carrying `inputMode="tel"`, `inputMode="numeric"` or `type="tel"` has said, in its own markup, that
a person will type digits into it. That declaration is the scope; every such element must route its
`onChange` through `western()` or `digitsOnly()` from `apps/console/src/digits.ts`.

A HANDLER THAT IS A NAMED FUNCTION IS ACCEPTED WHEN THAT FUNCTION FOLDS. `Door` passes
`set('phone')`, a shared setter — so this gate accepts an element whose file both declares the
element and imports a folder, rather than demanding the call appear inside the attribute. That is
deliberately the weaker check: the alternative is a gate that forces every handler inline, which
would be this gate dictating the shape of the code rather than the property it needs. The test
suite carries the behaviour; this carries the omission.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "apps" / "console" / "src"

#: An element the author marked as numeric, read to its self-closing `/>`.
#:
#: NOT `[^>]*?>`, WHICH IS WHAT THIS GATE FIRST SAID AND IT WAS WRONG ABOUT MOST OF ITS SUBJECT.
#: Every `onChange={(e) => ...}` contains a `>`, so a tag scanned to the first one ends in the
#: middle of the handler and the `inputMode` attribute below it falls outside the match. The gate
#: saw four inputs of the ten that exist and reported green over the six it never read. A gate that
#: silently narrows its own scope is worse than no gate: it answers with confidence.
ELEMENT = re.compile(r"<(?:input|Input)\b.*?/>", re.S)
DECLARES = re.compile(r'inputMode="(?:tel|numeric)"|type="tel"')
#: The fold, wherever it appears in the file — see the docstring on why file scope and not tag.
FOLDS = re.compile(r"\b(?:western|digitsOnly)\s*\(")


def main() -> int:
    if not CONSOLE.is_dir():
        print("no apps/console/src — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(CONSOLE.rglob("*.tsx"))
    if not files:
        # SILENCE IS NOT AGREEMENT.
        print("no console screens found — this gate needs re-pointing")
        return 1

    declared = 0
    bare: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT checked")
            return 1
        elements = [m for m in ELEMENT.finditer(text) if DECLARES.search(m.group(0))]
        if not elements:
            continue
        declared += len(elements)
        if FOLDS.search(text):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for m in elements:
            line = text.count("\n", 0, m.start()) + 1
            ident = re.search(r'id="([^"]+)"', m.group(0))
            bare.append(f"{rel}:{line}  {ident.group(1) if ident else '<unnamed input>'}")

    if not declared:
        print("no input declares itself numeric — this gate is reading for markup that changed")
        return 1

    if bare:
        print(f"{len(bare)} numeric input(s) that never fold what he types:")
        for line in bare:
            print("  " + line)
        print("\nThese say in their own markup that a person types digits into them, and pass what")
        print("an Arabic keyboard produces straight through. The service on the far side does not")
        print("recognise it, and he is told he got his own number wrong. Fold with `western()`.")
        return 1

    print(f"{declared} numeric input(s) across the console: every one folds before it stores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
