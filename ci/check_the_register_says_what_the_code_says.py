#!/usr/bin/env python3
"""A finding the code says it fixed must not still read as open in the register.

WHY THIS COSTS REAL TIME, AND IT COST MINE TODAY. The quality registers under `docs/` are the list
work is picked from: «what is still open» is answered by reading them. When a fix lands in the code
and no resolution note is written beside the finding, the register keeps advertising a defect that
no longer exists — and the next person to open it spends a session rediscovering that. In one
sitting I opened ب-2, ز-6 and ز-7 in turn, read each one, and found all three already fixed, each
with its own named test. Three rounds spent on nothing, because the register was the authority and
the register was wrong.

IT IS THE SAME DEFECT FAMILY THE REGISTERS THEMSELVES DOCUMENT: prose read as truth. A document
that describes the system is only as good as the thing that keeps it honest, and nothing kept this
one honest.

WHAT MAKES IT CHECKABLE. A fix in this repository cites the finding it closes — `(ز-6)` in the
comment above the reordered write, `(ط-1)` beside the queue. That citation is a claim by the code
about the register, and it is derivable from both sides:

    cited by the code  ∧  declared in a register  ∧  no resolution note  →  drift

A RESOLUTION NOTE IS NOT ONLY «✅». A partial fix (🔧) and a diagnosis (🔎) are honest states, and
demanding a green tick would push a reader toward writing one that is not true. What is refused is
SILENCE.

A BASELINE, BECAUSE A PERMANENTLY RED GATE TEACHES PEOPLE TO SCROLL PAST IT. There were 43 of these
the day this was written; reporting all 43 forever would make it furniture. `register-backlog.json`
records them BY NAME, the gate refuses GROWTH, and the backlog is worked down a round at a time.

By name rather than by count, because the first version stored the number and its own sabotage run
printed all forty-four entries with the newly-silent one buried in the middle. A failure you have
to diff by eye is a failure people learn to skim.

AND STRICT IN BOTH DIRECTIONS, deliberately — the same rule `check_the_unchecked_set_does_not_grow`
holds. A count that DROPS fails too: a baseline that silently absorbs an improvement is a baseline
that will silently absorb a regression next time, and writing the smaller number is one line for
whoever is looking straight at what they just recorded.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "ci" / "register-backlog.json"

#: Where the registers live. Named by shape, so a fourth round's register is covered on the day it
#: is created rather than on the day somebody remembers to add it here.
REGISTERS = "docs/فحص-الجودة-*.md"

_CODE = r"[ء-ي]{1,3}-\d{1,2}"
#: `### ز-6 · [عالٍ] …` — the heading that declares a finding, and the ones that resolve it.
HEADING = re.compile(r"^### (" + _CODE + r")(?: ·)? *(.*)$", re.M)
# AND NOT ONLY THE EMOJI. و-8 is recorded as «— **مُصلَح** » with no tick beside it, and that is a
# resolution note by any honest reading. A gate that demanded the decoration would be asking for
# a house style, not for the fact, and would have reported a finding that IS recorded.
RESOLVED = ("✅", "🔧", "🔎",
            "مُصلَح", "مصلح", "حُسم", "شُخِّص", "أُغلق", "مُغلق")
#: `(ز-6)` in a comment: the code claiming it closed that finding.
CITATION = re.compile(r"\((" + _CODE + r")\)")

SEARCH = ("services", "apps/console/src", "ci", "deploy")
SKIP = ("node_modules", ".venv", "__pycache__", "dist", "build", "platform")
SUFFIXES = (".py", ".ts", ".tsx", ".sh")


def main() -> int:
    registers = sorted(ROOT.glob(REGISTERS))
    if not registers:
        # SILENCE IS NOT AGREEMENT. A gate that cannot find the authority it judges against has
        # checked nothing, and must not print the sentence that says otherwise.
        print(f"no register matched {REGISTERS} — this gate cannot answer, so it refuses to")
        return 1

    # PER REGISTER, AND THAT IS THE WHOLE OF THE FIX THAT MATTERS HERE. The first version pooled
    # every register into one declared/resolved pair, and the codes COLLIDE: round 2's ي-1 is «the
    # snapshot is computed from the OLDEST 5000 visits» and round 3's ي-1 is «not one restorable
    # backup exists in this fleet». Seventy-three codes are spelled the same across the two, and
    # pooling meant a note written beside one silenced the gate about the other — 45 findings, more
    # than the 34 it was reporting, hidden by the gate's own arithmetic. A gate whose blind spot is
    # bigger than its output is worse than no gate: it is a green tick over the unexamined.
    silent: set[str] = set()
    declared: set[str] = set()
    for path in registers:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.name}: {exc} — so it was NOT checked")
            return 1
        # WITHIN one register a finding gets two headings: the one that states it and the one that
        # resolves it. So resolution is asked of the register as a whole, and only the pooling
        # ACROSS registers is what changes.
        here: set[str] = set()
        done: set[str] = set()
        for code, rest in HEADING.findall(text):
            here.add(code)
            if any(mark in rest for mark in RESOLVED):
                done.add(code)
        declared |= here
        # Named with its register, because two findings sharing a code are two findings and the
        # reader has to be told WHICH document to write the note in.
        silent |= {f"{path.name}#{code}" for code in here - done}
    if not declared:
        print("no finding headings found in the registers — either their shape changed or this "
              "gate is reading for one that no longer exists. It will not assume all is well.")
        return 1

    cited: dict[str, set[str]] = {}
    for top in SEARCH:
        base = ROOT / top
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            if any(s in path.parts for s in SKIP):
                continue
            # This gate spells out the shape it hunts for; it may not judge itself by it.
            if path.name == pathlib.Path(__file__).name:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — NOT checked")
                return 1
            for code in CITATION.findall(text):
                cited.setdefault(code, set()).add(path.relative_to(ROOT).as_posix())

    # Keyed by «register#code», valued by where the code claims the fix.
    drift = {entry: cited[entry.split("#", 1)[1]]
             for entry in silent if entry.split("#", 1)[1] in cited}

    try:
        known = set(json.loads(BASELINE.read_text(encoding="utf-8"))["silent"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"cannot read the baseline {BASELINE.name}: {exc} — the gate has no line to hold")
        return 1

    # THE BASELINE HOLDS THE NAMES, NOT A COUNT, AND THAT IS THE DIFFERENCE BETWEEN A USABLE
    # FAILURE AND A WALL OF TEXT. The first version stored 43 as a number, and its sabotage run
    # printed all forty-four entries with the new one buried among them — a gate whose failure you
    # have to diff by eye is one people learn to skim. With the names it says the one thing the
    # reader needs: WHICH finding just went silent.
    fresh = sorted(set(drift) - known)
    healed = sorted(known - set(drift))

    if fresh:
        print(f"{len(fresh)} finding(s) the code says it fixed, and the register says nothing:")
        for code in fresh:
            print(f"  {code} — cited in {', '.join(sorted(drift[code])[:3])}")
        print("")
        print("Write the resolution note beside the finding in its register (✅ fixed, 🔧 partly,")
        print("🔎 diagnosed). A register that advertises a closed defect sends the next reader to")
        print("spend a session rediscovering it — which is how this gate came to exist.")
        return 1

    if healed:
        print(f"{len(healed)} finding(s) are now recorded: {' '.join(healed)}")
        print(f"Remove them from {BASELINE.name}. A baseline that swallows an improvement will")
        print("swallow a regression next time, and the line is only held while it is taut.")
        return 1

    print(f"register backlog holds at {len(known)}: no finding the code cites has gone silent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
