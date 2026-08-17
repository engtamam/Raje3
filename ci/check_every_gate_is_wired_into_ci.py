"""A gate nothing runs is a comment with a shebang.

WHAT THIS FOUND ON ITS FIRST RUN: seven of eighty-eight gates were in `ci/` and in no workflow.
Each had been written deliberately, reviewed, and committed with an explanation of the defect it
prevents — and then never ran again. Among them:

    check_a_machine_credential_cannot_enumerate_customers.py
        ب-1's guard. A till's credential reading the whole customer base is the privacy failure
        this product most has to not have, and the check for it was inert.

    check_a_workflow_lives_where_github_reads_it.py
        A gate about workflow files, which was not in a workflow file. It would have found itself.

    check_every_state_a_row_enters_has_a_way_out.py
        The reason ز-1 (a reminder stuck in «sending» forever) cannot come back — asleep.

THIS IS THE DEFECT THIS REPOSITORY KEEPS FINDING, one level up. `is_subject_ref()` sat unused in
six files while د-2 destroyed erasures. `tone_index` was written by every ring and read by nobody.
The console's i18n dictionary was complete and one provider from rendering identifiers at a shop
owner. In every case the answer existed and nothing carried it — and a gate that is never invoked
is the purest form of it, because the artefact LOOKS like protection to anybody who greps for one.

THE RULE, WITH NO EXCEPTIONS TABLE: every `ci/check_*.py` is named in at least one workflow file.

There is no allow-list for «gates we are still working on» — a gate too unfinished to run is too
unfinished to commit, and one kept out deliberately would need a reason that survives being written
next to the rule it breaks. If a gate must not run in CI, delete it; the git history keeps it.
"""
from __future__ import annotations

import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATES = ROOT / "ci"
FLOWS = ROOT / ".github" / "workflows"


def main() -> int:
    if not GATES.is_dir():
        print("no ci/ directory — this gate cannot answer, so it refuses to")
        return 1
    if not FLOWS.is_dir():
        # A GATE THAT CANNOT READ ITS AUTHORITY MUST FAIL LOUDLY. With no workflows, «every gate is
        # wired» would be false about all of them rather than vacuously true.
        print(".github/workflows is missing — nothing runs any gate at all, and this check will "
              "not report that as agreement")
        return 1

    gates = sorted(p.name for p in GATES.glob("check_*.py"))
    if not gates:
        # SILENCE IS NOT AGREEMENT.
        print("no gates found in ci/ — this check needs re-pointing")
        return 1

    flows = sorted(FLOWS.glob("*.yml")) + sorted(FLOWS.glob("*.yaml"))
    if not flows:
        print("no workflow files — every gate in ci/ is inert")
        return 1

    text = ""
    for path in flows:
        try:
            text += io.open(path, encoding="utf-8").read() + "\n"
        except OSError as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT checked")
            return 1

    # THE FILENAME, WHICH IS WHAT A RUN LINE CONTAINS. Anything cleverer — parsing YAML for `run:`
    # steps — would have to model matrices, composite actions and reusable workflows, and would be
    # wrong about a gate that is genuinely invoked in a shape the parser did not anticipate. A
    # false «not wired» on a wired gate is how a rule gets an exceptions table.
    orphans = [g for g in gates if g not in text]

    if orphans:
        print(f"{len(orphans)} of {len(gates)} gate(s) are in ci/ and in no workflow — they have "
              f"never run since the day they were written:")
        for g in orphans:
            print(f"  ci/{g}")
        print("\nA gate nothing invokes is a comment with a shebang: it looks like protection to")
        print("anyone who greps for one, and prevents nothing. Add it to .github/workflows, or")
        print("delete it — the history keeps it either way.")
        return 1

    print(f"{len(gates)} gates, all named in a workflow — none of them is asleep")
    return 0


if __name__ == "__main__":
    sys.exit(main())
