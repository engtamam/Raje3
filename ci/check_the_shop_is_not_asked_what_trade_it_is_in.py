"""No shop is asked what trade it is in, and nothing in the product branches on the answer.

WHAT WAS THERE. Sign-up opened on «نوع النشاط» — tyres, car wash, salon, upholstery — and the
answer was load-bearing four times over: it seeded the service catalogue, it seeded the starting
rewards, it decided whether «تسجيل زيارة» shows a plate page, and it decided whether a meter is
asked for. One question, four consequences, and the owner answering it had no way to know that.

WHY IT IS GONE. The seeded catalogue was a guess about a business we had never seen — a tyre shop
that also details cars got a list that was wrong on its first day, and correcting it meant deleting
our guesses one by one. A shop now starts empty and the owner writes what he actually sells; that
is one screen of work and it is TRUE, which the guess never was. The starting rewards went with it
for the same reason: a rewards table for a trade we assumed is worse than no table.

WHAT REPLACED IT. One thing, because only one thing was ever really being asked: does this shop
work on cars? That is a checkbox on his own establishment, and it decides the plate page and the
meter. Nothing else in the product may branch on a trade.

NO EXCEPTIONS TABLE. A single surviving mention is how the concept comes back: a type nobody
fills, a seed file nobody runs, a field the console still sends. The word is either gone or it is
still deciding something.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Where the product lives. `platform/` is a vendored submodule and never held this concept.
TREES = [
    ROOT / "services",
    ROOT / "apps" / "console" / "src",
    ROOT / "apps" / "console" / "e2e",
    ROOT / "deploy",
    ROOT / "data",
]

#: PUBLISHED LEGAL DOCUMENTS ARE NOT CODE, and this is a scope narrowing with a reason rather than
#: a hole. `deploy/seed/legal/` holds the seven PDPL documents; each is version-pinned and shops
#: have ACCEPTED a specific version of it. Their «vehicle sectors» is ordinary Arabic-English prose
#: describing shops that work on cars — it names no field of ours and decides nothing. Rewriting a
#: published document to satisfy a grep would change what somebody agreed to, silently, which is a
#: far worse defect than the word surviving in a sentence. Any real change there is a new version,
#: republished, and it is a deliberate decision to make.
LEGAL = ROOT / "deploy" / "seed" / "legal"

#: A COMMENT DECIDES NOTHING, AND THIS IS THE SCOPE, NOT AN EXCEPTION. What this gate is for is a
#: shop being ASKED — a field, a route, a seeded row, a control on a form, a sentence we SHIP. A
#: comment is none of those: it is where the removal is explained, and every file that lost the
#: concept carries a note saying what used to be there and why it went. Forbidding those notes
#: would mean the only record of the decision is a commit message nobody reads while editing the
#: file. So comments are stripped before the scan and STRING LITERALS ARE NOT — a string ships, and
#: «تُعبَّأ من افتراضيات القطاع» sitting in a help text is the shop still being told about a trade.
LINE_COMMENT = {".py": "#", ".sh": "#", ".yaml": "#", ".yml": "#", ".ts": "//", ".tsx": "//"}
BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_comments(text: str, suffix: str) -> str:
    """Blank out comment bodies, keeping line numbers and every string literal intact."""
    if suffix in {".ts", ".tsx"}:
        text = BLOCK.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)
    if suffix == ".py":
        # Module and function docstrings are documentation wearing a string's clothes.
        text = re.sub(r'"""(?:[^"\\]|\\.|"(?!""))*"""',
                      lambda m: re.sub(r"[^\n]", " ", m.group()), text)
    mark = LINE_COMMENT.get(suffix)
    if not mark:
        return text
    out = []
    for line in text.split("\n"):
        # A `#` inside a string is not a comment, and a crude cut would blind the gate to a
        # shipped string on the same line. Only a line whose FIRST non-space is the marker is one.
        out.append("" if line.lstrip().startswith(mark) else line)
    return "\n".join(out)


SKIP_DIRS = {"node_modules", "__pycache__", ".pytest_cache", "dist", "build", ".venv"}
SUFFIXES = {".py", ".ts", ".tsx", ".json", ".yaml", ".yml", ".sh", ".md"}

#: `sector` as a word. Not `sectors_of_a_circle` in some unrelated maths, and not a substring of a
#: longer identifier that means something else.
WORD = re.compile(r"\bsectors?\b|نوع النشاط|القطاع(?:ات)?\b", re.IGNORECASE)


def main() -> int:
    hits: list[str] = []
    scanned = 0
    for tree in TREES:
        if not tree.exists():
            continue
        for path in sorted(tree.rglob("*")):
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if LEGAL in path.parents:
                continue
            if path.resolve() == pathlib.Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                # A GATE THAT CANNOT READ MUST FAIL LOUDLY. An unreadable file is an unchecked one.
                print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
                return 1
            scanned += 1
            for line_no, line in enumerate(strip_comments(text, path.suffix).splitlines(), start=1):
                if WORD.search(line):
                    hits.append(f"{path.relative_to(ROOT).as_posix()}:{line_no}: {line.strip()[:110]}")

    if not scanned:
        # SILENCE IS NOT AGREEMENT: scanning nothing is not the same as finding nothing.
        print("scanned no files — this gate needs re-pointing")
        return 1
    if hits:
        print(f"The trade a shop is in is still in the product ({len(hits)} place(s)):")
        for line in hits[:60]:
            print("  " + line)
        if len(hits) > 60:
            print(f"  … and {len(hits) - 60} more")
        print("\nA shop starts empty and says only whether it works on cars.")
        return 1
    print(f"{scanned} files: no shop is asked what trade it is in")
    return 0


if __name__ == "__main__":
    sys.exit(main())
