"""A check that reports a count must refuse a count of nothing.

THE FAILURE THIS CLOSES, and it is the one this project keeps finding in its own guards: a check
whose evidence is weaker than the sentence it prints. A check that discovers its subject — globs a
directory, matches a call shape, reads a registry — and then prints «ok N» is telling the truth
about N and nothing about whether N SHOULD have been zero. Rename the thing it looks for, move a
directory, change an extension, and the scan matches nothing, the count is zero, and the check
goes green for ever over a rule nobody enforces any more.

Three checks had exactly that shape, one of them written two days ago:
  · `check_every_send_says_which_number_it_leaves_from` — finds sends by `.send(` + `template_name=`
  · `check_the_browser_does_not_search_the_fleet_directly` — globs the console's source
  · `check_the_class_of_a_message_comes_from_its_reason` — where ZERO IS THE GOAL, so its evidence
    had to become the subject it scanned rather than the findings it counted

THE RULE, WITH NO EXCEPTIONS TABLE: a check whose success line interpolates a value must refuse
that value being nothing. Which value is not this check's business — findings, files, rows — only
that a nothing is refused rather than reported.

AND IT WAS WRONG TWICE WHILE BEING WRITTEN, both times in the way it polices. It read one line and
missed a success line wrapped across two. Then it accepted ANY emptiness test anywhere in a file
as proof, so removing a guard from a check still passed — an unrelated `if not want:` two
functions away satisfied it. Both are recorded at the code that fixes them.

WHAT IT CANNOT SEE: a scan that narrows without emptying — matching three files where it should
match thirty. Nothing mechanical catches that; it is what the sabotage step in the method is for.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CI = ROOT / "ci"

OK_CALL = re.compile(r'print\(\s*f?"ok')


def printed_names(src: str) -> list[str]:
    """The values a `print("ok …")` call interpolates — read by paren depth, not by line.

    THE FIRST DRAFT MATCHED ONE LINE and reported two counting checks where there are three: one
    wraps its success line across two, with the `{` on the second. A guard that reads less than
    the code writes is exactly what this file exists to close.
    """
    names: list[str] = []
    for m in OK_CALL.finditer(src):
        depth, i = 0, src.index("(", m.start())
        while i < len(src):
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    names += re.findall(r"\{\s*([A-Za-z_][A-Za-z_0-9]*)", src[m.start():i])
                    break
            i += 1
    return names


def refuses(src: str, name: str) -> bool:
    """Is THIS name — the one that gets printed — tested for emptiness anywhere?

    NOT «any emptiness test in the file», which is what the first draft accepted. Its own sabotage
    passed under that rule: strip the guard out of a check and an unrelated `if not want:` two
    functions away still matched. A guard that accepts evidence about something else is the defect
    this file is named after.
    """
    return bool(re.search(rf"if\s+not\s+{re.escape(name)}\s*:"
                          rf"|{re.escape(name)}\s*==\s*0"
                          rf"|{re.escape(name)}\s*<\s*1"
                          rf"|len\(\s*{re.escape(name)}\s*\)\s*==\s*0", src))


def main() -> int:
    bad: list[str] = []
    counting = 0
    for path in sorted(CI.glob("check_*.py")):
        if path.name == pathlib.Path(__file__).name:
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        names = printed_names(src)
        if not names:
            continue
        counting += 1
        # ANY of the printed values may carry the proof — a check may report three numbers and
        # refuse on one. What is refused is that ALL of them can be nothing, unremarked.
        if not any(refuses(src, n) for n in names):
            bad.append(f"{path.name} (prints {', '.join(sorted(set(names)))})")

    for b in bad:
        print(f"  \033[31m✗ {b}: prints a count and never refuses a count of nothing\033[0m")
    if bad:
        print("\nAn empty scan and a clean repository look identical from inside a check. Refuse "
              "the empty one — a rename is the likeliest way a guard stops guarding.")
        return 1
    if not counting:
        # This check has the shape it polices, so it is held to it.
        print("  \033[31m✗ found no counting checks at all — the pattern here no longer "
              "matches\033[0m")
        return 1
    print(f"ok {counting} counting checks each refuse a count of nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
