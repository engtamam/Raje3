#!/usr/bin/env python3
"""A STATE THE CODE WRITES IS A STATE SOMETHING READS — or the row is lost in it for ever.

THE OUTAGE THIS PREVENTS IS COMPLETELY SILENT, WHICH IS WHY IT SURVIVED A FULL QA ROUND.

`reminders` claims a row before sending: `state = "sending"`. Then it sends, and on success, on
failure, or at the ceiling it writes some other state. Between those two writes the process can
die — a deploy, an eviction, an OOM — and the row stays `sending`.

Nothing ever looks at it again. `SchedStore.due()` selects `state == "pending"`; `sending` is not
`pending` so it is never picked up, and it is not `sent` or `failed` so it appears in no report.
The customer's reminder simply never happens, and NOBODY LEARNS THAT IT DIDN'T — not the shop, not
us. `grep '"sending"'` across the whole service returned exactly one hit: the line that writes it.

AND THE CARE TAKEN ELSEWHERE IS WHAT MAKES IT INSTRUCTIVE. `_fail()` deliberately returns a row to
`pending` rather than closing it as `failed`, with a comment explaining that a closed schedule is a
reminder that silently never happens. The author saw the exact failure mode — for the case where an
exception is RAISED. Process death raises nothing, and it is the most common event during a deploy.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. Every string literal assigned to a row's `state` must
appear somewhere else in the service as something READ — a comparison, a query filter, a branch.
A state with exactly one mention, and that mention a write, is a hole with a row in it.

WHY A GATE RATHER THAN A SWEEP. Because states are added by people modelling a real workflow — a
`queued`, an `approving`, a `held` — and each one is obviously fine on the day it is written. The
reader that would rescue a row stranded in it is the part nobody remembers, precisely because the
happy path never needs it.

AND WHAT THIS GATE DOES NOT CATCH, SAID PLAINLY. It proves a state is READ somewhere; it cannot
prove the reader actually rescues a stranded row. Delete the sweeper from `due()` and leave the
lease check in `_claim`, and this still passes — `sending` is mentioned more than once, so the
unambiguous signal is gone even though the hole is back. That deeper property belongs to the tests
(`test_a_claim_abandoned_mid_send_is_swept_back_and_delivered`), which assert the message actually
goes out. This gate closes the case that is decidable by reading: a state nothing ever looks at.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The field this is about. Named rather than guessed, so a service with a `status` column is not
# swept in by accident and forced to satisfy a rule written about something else.
FIELD = "state"


def _states_written(tree: ast.AST) -> dict[str, int]:
    """`row["state"] = "sending"` → {"sending": lineno}."""
    out: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if (isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant)
                    and target.slice.value == FIELD):
                out.setdefault(node.value.value, node.lineno)
    return out


def main() -> int:
    bad: list[str] = []
    checked = 0

    services = sorted(p for p in SERVICES.iterdir() if p.is_dir()) if SERVICES.is_dir() else []
    if not services:
        print(f"{C_R}no services found — this gate checked nothing, which is not the same as "
              f"finding nothing wrong{C_N}")
        return 1

    for service in services:
        files = [p for p in service.rglob("*.py")
                 if "test" not in p.parts and not p.name.startswith("test_")]
        if not files:
            continue

        written: dict[str, tuple[str, int]] = {}
        corpus: list[tuple[str, str]] = []
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, ValueError, UnicodeDecodeError) as exc:
                bad.append(f"{rel}: cannot read it — {exc}")
                continue
            corpus.append((rel, text))
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                bad.append(f"{rel}: cannot parse it — {exc}")
                continue
            for value, line in _states_written(tree).items():
                written.setdefault(value, (rel, line))

        for value, (rel, line) in sorted(written.items()):
            checked += 1
            # A READ is any mention of the literal that is not this assignment: a comparison, a
            # query filter, a membership test. Counting mentions across the whole service is
            # deliberately generous — the gate is looking for a state mentioned ONCE, which is the
            # unambiguous case, rather than trying to prove a particular reader is correct.
            mentions = sum(len(re.findall(rf'["\']{re.escape(value)}["\']', text))
                           for _, text in corpus)
            if mentions <= 1:
                bad.append(
                    f"{rel}:{line}: a row is moved into `{value}` and nothing in "
                    f"{service.name} ever reads that value. A process that dies after this write "
                    f"— a deploy, an eviction, an OOM — strands the row there permanently: not "
                    f"picked up as pending, not reported as finished. The work never happens and "
                    f"no one finds out")

    if bad:
        print(f"{C_R}a row can enter a state it can never leave{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Either give it a reader (a sweeper, a lease, a query) or do not write it.")
        return 1

    if checked == 0:
        print(f"{C_R}no state assignments found — either the field was renamed or this gate no "
              f"longer matches it, and an empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {checked} row states, every one of them read by something")
    return 0


if __name__ == "__main__":
    sys.exit(main())
