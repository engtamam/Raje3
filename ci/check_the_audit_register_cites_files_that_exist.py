"""A finding that cites `path/file.py:120` must cite a file that exists, at a line it has.

WHY THIS EXISTS. The quality registers under `docs/` are the most-read prose in this repository:
every overnight session starts by opening one and believing what it says. And they are the one
large artefact nothing checks. Over this campaign four separate sessions opened a finding marked
OPEN, spent a turn reading the code, and found it closed — and one finding marked closed («ج-7:
`portal/core/render.py` no longer writes the offset») was wrong in the other direction, about a
file that was still writing it. The register drifted from the tree in BOTH directions, silently,
while reading exactly as authoritative as the day it was written.

That is this repository's recurring defect — prose read as truth — applied to the document that
decides what gets worked on. A stale citation is not a typo: it sends the next reader to a file
that no longer contains what they were told to look at, and the cheapest thing they can conclude
is that the register is approximately right.

THE RULE, AND ITS SCOPE IS THE HONEST PART. A citation that names a FULL path — one rooted at a
real top-level directory of this repository — must resolve to a file that exists, and if it names
a line number, the file must be long enough to have that line.

Shorthand is out of scope, said out loud rather than silently passed. `pricing.py:37` and
`core/seams.py:44` are ambiguous by construction — several services carry a `config.py`, an
`internal.py` and a `tick.py` — and resolving them would mean guessing which the finding meant.
Guessing is what a register does; a gate must not. This was not a design choice made up front: the
first version treated «has a slash» as «is a path» and reported 43 findings of which 40 were the
house style. See ROOTS below.

WHAT THIS DOES NOT CLAIM. That the line still contains what the finding says it does — no gate can
read that. It claims the weaker, checkable thing: the reader will land somewhere real. The strong
version is what the sessions do by hand, and this removes the cheapest way for that work to be
wasted.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

#: `services/operations/app/core/operations.py:317-329` or `deploy/x.yaml:25` — a path, then a line
#: or a range. Backticks are how the registers write them, and requiring them keeps prose sentences
#: that merely mention a directory out of the match.
A_CITATION = re.compile(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.[a-z]{2,5}):(\d+)(?:-\d+)?`")

#: A FULL PATH STARTS AT A REAL ROOT OF THIS REPOSITORY, and nothing else is in scope.
#:
#: THE FIRST VERSION OF THIS GATE TREATED «CONTAINS A SLASH» AS «IS A PATH», and reported 43
#: findings of which 40 were wrong. The registers write service-relative shorthand constantly —
#: `core/seams.py:44`, `loyalty/internal.py:352`, `reminders/config.py:318` — because the sentence
#: around them already says which service. That shorthand is not a broken citation; it is the
#: house style, and a gate that calls it broken forty times buries the three that are real.
#:
#: Resolving shorthand by searching for a matching filename was the obvious repair and is the
#: wrong one: several services carry a `config.py` and an `internal.py`, so the gate would have to
#: GUESS which one the finding meant. Guessing is what a register does. A gate must not.
ROOTS = ("services/", "apps/", "deploy/", "ci/", "config/", "docs/", ".github/", "scripts/")

#: A citation the register has struck through AND stated is gone. Both are required: the strike
#: alone could be an edit in progress, and the word alone could be prose about something else.
RETIRED = re.compile(r"~~`[^`]+`~~.*(?:محذوف|حُذف|deleted|removed)")

#: The vendored platform is a submodule that may be absent, and citing into it is correct even
#: when it is not checked out.
def _skipped(rel: str) -> bool:
    return rel.startswith("platform/") or not rel.startswith(ROOTS)


def main() -> int:
    if not DOCS.is_dir():
        print("no docs/ directory — this gate cannot answer, so it refuses to")
        return 1

    registers = sorted(DOCS.glob("فحص-الجودة*.md"))
    if not registers:
        # SILENCE IS NOT AGREEMENT: reading no register is not the same as finding no stale
        # citation, and this gate exists because the registers are trusted.
        print("no quality register found under docs/ — this gate needs re-pointing")
        return 1

    broken: list[str] = []
    checked = 0
    skipped = 0

    for doc in registers:
        rel_doc = doc.relative_to(ROOT).as_posix()
        try:
            text = doc.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {rel_doc}: {exc} — so it was NOT checked")
            return 1

        for n, line in enumerate(text.split("\n"), start=1):
            # A REGISTER MUST BE ABLE TO NAME A FILE THAT IS GONE, or a resolved finding cannot say
            # what it resolved. So a citation STRUCK THROUGH and stated as deleted on the same line
            # is a historical reference: it does not send the reader anywhere, it tells them.
            #
            # This is not an exceptions table — there is no list of blessed paths. It is a property
            # of the citation itself, and it costs the writer something visible: the strike AND the
            # word, in the sentence a reader sees, rather than a quiet entry in a file nobody opens.
            if RETIRED.search(line):
                skipped += 1
                continue
            for path_text, line_no in A_CITATION.findall(line):
                if _skipped(path_text):
                    skipped += 1
                    continue
                checked += 1
                target = ROOT / path_text
                if not target.is_file():
                    broken.append(f"{rel_doc}:{n}: cites `{path_text}` — no such file")
                    continue
                try:
                    length = len(target.read_text(encoding="utf-8", errors="ignore").split("\n"))
                except OSError as exc:
                    broken.append(f"{rel_doc}:{n}: cannot read `{path_text}` ({exc})")
                    continue
                if int(line_no) > length:
                    broken.append(f"{rel_doc}:{n}: cites `{path_text}:{line_no}` — the file has "
                                  f"{length} lines")

    if broken:
        print(f"{len(broken)} citation(s) in the register point nowhere:")
        for b in broken:
            print("  " + b)
        print("\nA reader opens the register, follows the citation, and lands on nothing — and the")
        print("cheapest conclusion available to them is that the register is approximately right.")
        print("Correct the citation, or mark the finding resolved and say what replaced it.")
        return 1

    print(f"{checked} full-path citation(s) across {len(registers)} register(s) all resolve "
          f"({skipped} skipped: platform/, or service-relative shorthand this gate will not guess "
          f"at)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
