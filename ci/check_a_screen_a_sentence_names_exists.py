"""A sentence that sends somebody to a screen must name a screen that exists.

WHAT THIS WAS WRITTEN AFTER. «بلغت عدد الفروع المتاحة في باقتك. للمزيد، رقِّ باقتك من «متجر
التطبيقات».» shipped for months. There was no «متجر التطبيقات» anywhere in the product: no row in
the rail, no tab, no address. The tab that sold apps was called «اشتراكي», and it was reachable
only from a link the owner had to already be looking at.

So the sentence was an instruction to go somewhere that did not exist. The owner who read it went
looking, found four tabs with four other names, and concluded the product could not do what he had
just been told to do — a dead end reached by following our own directions.

THE RULE, AND IT IS ABOUT EVIDENCE RATHER THAN ABOUT WORDING. When a user-facing string points at
a place — «… من «X»», «… في «X»», «… إلى «X»» — then X must appear somewhere in this console as a
LABEL: a nav row, a tab, a segmented option. A name that is a label is a name a person can see and
press. A name that appears only inside the sentence that sends him there is a name that exists
nowhere but in our prose.

WHAT IT DOES NOT DO: check that the label leads to the right place, or that the reader has it. The
first needs a browser; the second is a capability question the gateway answers. This gate answers
only «does this name exist at all», which is the question the shipped sentence got wrong.

    python ci/check_a_screen_a_sentence_names_exists.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "console" / "src"

#: A POINTER, NOT EVERY QUOTED NAME. «محلّي» in a sentence ABOUT the section is prose; «افتح
#: «محلّي»» is a direction, and only a direction can dead-end. The verbs and prepositions here are
#: the ones that turn a mention into an errand.
POINTER = re.compile(r"(?:من|في|إلى|افتح|اذهب إلى)\s+«([^»]{2,40})»")

#: WHAT COUNTS AS A PLACE THAT EXISTS: something the console draws as a label. Nav rows, tabs and
#: segmented options are all written this way, so one pattern reads all three.
LABEL = re.compile(r"label:\s*'([^']+)'|label=\"([^\"]+)\"|label:\s*\"([^\"]+)\"")

#: THE SHELL'S OWN CONTROLS ARE PLACES TOO, and they are not written as `label:`. «حسابي» is drawn
#: by the kit from `labels={{ account: '…' }}` — an icon beside sign-out that two sentences on the
#: opening page point at. A gate that read only `label:` would have called the one screen every
#: role can open a name that does not exist.
SHELL_LABELS = re.compile(r"labels=\{\{(.*?)\}\}", re.S)
QUOTED = re.compile(r"'([^']+)'")

#: COMMENTS ARE NOT THE PRODUCT. Every fix in this repository explains itself at length in the file
#: it changed, and those explanations quote the sentences they replaced — including the broken one
#: above. A gate that read them would go red on its own history.
BLOCK = re.compile(r"/\*.*?\*/", re.S)
LINE = re.compile(r"^\s*//.*$", re.M)


def strip(text: str) -> str:
    return LINE.sub("", BLOCK.sub("", text))


def main() -> int:
    files = sorted(SRC.rglob("*.tsx")) + sorted(SRC.rglob("*.ts"))
    if not files:
        print("apps/console/src holds no sources — this gate cannot answer, and that is not a pass")
        return 1

    names: set[str] = set()
    bodies: list[tuple[pathlib.Path, str]] = []
    for f in files:
        if f.name.endswith((".test.ts", ".test.tsx")):
            # A TEST'S FIXTURES ARE NOT SCREENS. Their labels would let a name exist because
            # something asserted about it, which is the opposite of what this gate measures.
            continue
        code = strip(f.read_text(encoding="utf-8"))
        bodies.append((f, code))
        for m in LABEL.finditer(code):
            names.add((m.group(1) or m.group(2) or m.group(3)).strip())
        for block in SHELL_LABELS.finditer(code):
            names.update(v.strip() for v in QUOTED.findall(block.group(1)))

    bad: list[str] = []
    for f, code in bodies:
        for m in POINTER.finditer(code):
            target = m.group(1).strip()
            if target not in names:
                bad.append(f"{f.relative_to(ROOT)}: «{target}»")

    if bad:
        print("  \033[31m✘ sentences that send somebody to a screen this console does not have:"
              "\033[0m")
        for line in bad:
            print(f"      \033[31m{line}\033[0m")
        print("\n    Give the place a label — a nav row, a tab, a segmented option — or name the "
              "place that\n    already exists. Do not exempt it here: the reader follows the "
              "sentence either way.")
        return 1

    print(f"  \033[32m✔ every screen a sentence names is a label somebody can find "
          f"({len(names)} labels)\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
