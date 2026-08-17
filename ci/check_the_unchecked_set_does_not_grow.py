#!/usr/bin/env python3
"""THE NOTE CHANNEL THAT ALWAYS PASSES — AND HOW A GATE ROTS WITHOUT EVER BEING SWITCHED OFF.

Six gates print a note and exit zero:

    check_deploy_wiring              WhatsApp is still on the bring-up driver
    check_internal_contracts         13 internal calls it cannot read
    check_audit_actions              12 audited actions built at runtime
    check_screens_send_declared_fields   4 calls to a route it could not resolve
    check_undefined_names            9 names that usually mean a defect
    check_undeclared_field_read      1 getattr on a computed attribute name

EVERY ONE OF THOSE IS DEFENSIBLE ON ITS OWN, and that is exactly the problem. A body assembled at
runtime genuinely cannot be read from source; refusing the build over it would be a gate that
overreaches, and an overreaching gate gets loosened. So each author was right, each note was the
correct call, and nobody was ever wrong.

Together they are FORTY PLACES that pass green every day, with no ceiling, no date and no baseline.
Nothing stops the number becoming forty-five next month, or sixty by the spring — and nothing would
say so, because each new note arrives one at a time, attached to a change that is otherwise fine,
and each one is defensible on its own.

THIS DOES NOT REFUSE THE NOTES. It refuses the DRIFT. The count is written down, and it may only
move when somebody moves it.

STRICT IN BOTH DIRECTIONS, AND THAT IS DELIBERATE.
  · A count that ROSE means the unchecked set grew without a decision. That is the failure this
    exists for.
  · A count that FELL also fails. A baseline that quietly absorbs an improvement is a baseline
    that will quietly absorb a regression the next time — the ratchet only holds if it is tight.
    Writing the smaller number down is a one-line diff, made by the person who is already looking
    at what they just fixed.

WHY PARSE THE OUTPUT RATHER THAN IMPORT THE GATES. Because what matters is what a HUMAN READING CI
is told. A gate could count correctly and print something else, and the printed line is the one
that ends up in a pull request. This reads exactly what CI reads.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "ci" / "notes-baseline.json"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
# A note line: the leading marker these gates use for «looked, could not decide, let it through».
NOTE = re.compile(r"^\s*[~!]\s")
# «13 internal call(s) …» — the size of what was let through. A note with no number is one place.
COUNT = re.compile(r"^\s*[~!]\s+(\d+)\b")


def notes_from(gate: str) -> tuple[int, str]:
    """Run the gate and count what it waved through. Returns (count, error-or-empty)."""
    script = ROOT / "ci" / f"{gate}.py"
    if not script.is_file():
        return -1, f"{gate}: no such gate — the baseline names a file that is not there"
    try:
        run = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                             cwd=ROOT, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, f"{gate}: could not run it — {exc}"

    total = 0
    for line in ANSI.sub("", run.stdout + run.stderr).splitlines():
        if not NOTE.match(line):
            continue
        m = COUNT.match(line)
        total += int(m.group(1)) if m else 1
    return total, ""


def main() -> int:
    try:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8")).get("gates") or {}
    except (OSError, ValueError) as exc:
        print(f"{C_R}the baseline cannot be read — {exc}{C_N}\n"
              f"  Without it there is no ceiling, which is the state this gate exists to end.")
        return 1
    if not baseline:
        print(f"{C_R}the baseline names no gates — an empty set is not agreement{C_N}")
        return 1

    grew: list[str] = []
    shrank: list[str] = []
    broken: list[str] = []
    total = expected = 0

    for gate, allowed in sorted(baseline.items()):
        found, err = notes_from(gate)
        if err:
            broken.append(err)
            continue
        total += found
        expected += int(allowed)
        if found > allowed:
            grew.append(f"{gate}: {found} unchecked, baseline {allowed} — {found - allowed} more "
                        f"place(s) now pass without being decided about")
        elif found < allowed:
            shrank.append(f"{gate}: {found} unchecked, baseline {allowed} — write the smaller "
                          f"number down so the next regression cannot hide inside the slack")

    if broken:
        print(f"{C_R}a gate in the baseline could not be run — «could not tell» is not «nothing "
              f"grew»{C_N}")
        for line in broken:
            print(f"  {line}")
        return 1

    if grew:
        print(f"{C_R}the unchecked set grew{C_N}")
        for line in grew:
            print(f"  {line}")
        print(f"\n  Total now {total}, recorded {expected}. Either decide about the new places or "
              f"raise the baseline ON PURPOSE, in a diff somebody reviews.")
        return 1

    if shrank:
        print(f"{C_Y}the unchecked set shrank — write it down{C_N}")
        for line in shrank:
            print(f"  {line}")
        print(f"\n  Total now {total}, recorded {expected}. Update ci/notes-baseline.json.")
        return 1

    print(f"{C_G}ok{C_N}  {total} places pass with a note, exactly the {expected} on record "
          f"(د-10 — a ceiling, so the set cannot drift)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
