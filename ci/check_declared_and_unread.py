"""A state the console declares must be read by something.

WHY THIS EXISTS (م · النمط 3). Two of these shipped side by side:

  · `Local.tsx` declared `const [locked, setLocked] = useState<Record<string, string>>({})` with a
    paragraph above it explaining that `insights.bundles` and `insights.associations` answer 402
    with a sentence naming what the plan does not include, and that «a capability nobody can see is
    one nobody can buy». Nothing ever called `setLocked`, and nothing ever read `locked`. Dead code
    beside a live comment: every 402 was swallowed into `null` and the section simply vanished.

  · `catalog.unreachable` was declared with the same care — «named, never silent: a section missing
    because a service is down must be distinguishable from a section missing because this person
    may not have it» — and its only reader was `isOutage`, which fires only when EVERY service is
    down. So loyalty falling over by itself deleted «نقاطي» from the rail without a word, and the
    owner who pays for it phoned support about his permissions.

Both are the same defect: the product decided what to say, wrote the place to keep it, and never
connected it. It is invisible to every test, because the code that would have failed is the code
that was never written.

WHAT IT CHECKS. A `useState` whose SETTER is never called, or whose VALUE is never read, in the
file that declares it. Either half missing makes the state a decoration.

    python ci/check_declared_and_unread.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "apps" / "console" / "src"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: `useState<Record<string, string>>({})` — the type argument NESTS, so a naive `[^>]*` stops at
#: the first `>` and the whole declaration goes unseen. That is exactly how this check missed
#: `locked` the first time the fix was removed to test it: the state it exists to find was
#: invisible to its own pattern.
DECL = re.compile(r"const\s*\[\s*(\w+)\s*,\s*(set\w+)\s*\]\s*=\s*useState\s*"
                  r"(<(?:[^<>]|<[^<>]*>)*>)?\s*\((.*?)\);")

#: A placeholder: nothing but an empty value. A state INITIALISED FROM SOMETHING — a prop, a
#: computed default — is filled at construction, and never setting it afterwards is a decision
#: rather than an oversight. Flagging those too would have reported the editor's own draft the
#: moment it started opening on his saved text, which is the fix and not the defect.
EMPTY = {"", "''", '""', "{}", "[]", "false", "0", "null", "undefined"}

#: A MENTION IS NOT A CALL. This check's own comments name `setLocked` while explaining it, and
#: counting that sentence as a caller made the gate report the defect as repaired while it was
#: deliberately broken. A comment is the one place a name appears without doing anything.
COMMENT = re.compile(r"/\*.*?\*/|//[^\r\n]*", re.S)


def _blank_comments(text: str) -> str:
    """Comments blanked, NOT removed — every character keeps its offset, so a line number computed
    on this string is the line number in the file. Deleting them shifted every position after the
    first comment and turned the whole console into findings."""
    return COMMENT.sub(lambda m: re.sub(r"[^\r\n]", " ", m.group(0)), text)


def scan(path: pathlib.Path) -> list[str]:
    code = _blank_comments(path.read_text(encoding="utf-8"))
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    out: list[str] = []

    for m in DECL.finditer(code):
        value, setter = m.group(1), m.group(2)
        rest = code[m.end():] + code[:m.start()]
        # The setter passed to a child counts: `onChange={setFoo}` is how it is called.
        writes = len(re.findall(rf"\b{re.escape(setter)}\b", rest))
        # The value rendered, compared, passed down, or read in a dependency list.
        reads = len(re.findall(rf"\b{re.escape(value)}\b", rest))
        line = code[:m.start()].count("\n") + 1
        initial = (m.group(4) or "").strip()

        if writes == 0 and initial in EMPTY:
            out.append(f"{rel}:{line}  `{value}` is declared and NOTHING ever sets it — the state "
                       f"the screen was given to say something with is never filled")
        elif reads == 0:
            out.append(f"{rel}:{line}  `{value}` is written and NOTHING ever reads it — what the "
                       f"screen was told is never shown to anybody")
    return out


def main() -> int:
    findings: list[str] = []
    files = 0
    for path in sorted(SRC.rglob("*.tsx")):
        files += 1
        findings += scan(path)

    if findings:
        print(f"{C_R}  ✘ {len(findings)} state(s) declared and never joined up:{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Wire it or delete it. A place to keep an answer, with nothing putting "
              f"the answer there, reads in review as a feature that exists.{C_N}")
        return 1

    print(f"{C_G}  ✔ every declared state is both written and read ({files} screens){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
