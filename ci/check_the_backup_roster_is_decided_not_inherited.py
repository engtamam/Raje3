#!/usr/bin/env python3
"""EVERY SERVICE IS EITHER BACKED UP OR EXEMPT ON PURPOSE — never by accident of a borrowed list.

THE FAILURE THIS COMES FROM, AND IT WAS RUNNING NIGHTLY. `seed-backup-targets.sh` derives its
roster from `PRIVACY_TARGETS` in compliance-service. That is right for one reason and wrong for
another, and the wrong one cost us a failing backup every night:

  * RIGHT: «every service holding personal data» is one question, and two hand-kept lists of the
    answer drift the day somebody adds a service to one of them.
  * WRONG: «must receive an erasure» and «is worth archiving» are NOT the same question. They part
    company at a derived index. search-service must receive every deletion — the index absolutely
    holds the customer's number — and must never be archived, because restoring a stale copy of
    records the owning service already holds is worse than having no copy at all.

So search-service was registered as a backup target, answered every export with its exemption, and
the run failed. Three consecutive nights of `BackoffLimitExceeded`, and this was one of the causes.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE:

  1. `BACKUP_EXEMPT` exists in backup-service.values.yaml and is non-empty-or-explicitly-empty —
     a missing key is a roster that inherits silently again.
  2. Every name in it is a real service — one that appears in `PRIVACY_TARGETS`. An exemption for
     a service that does not exist protects nothing and hides a typo that would let the real
     service through.
  3. The seeder actually reads it. A declaration nothing consumes is the defect we hunt, wearing
     a comment.

WHY THE GATE RATHER THAN JUST THE FIX. Because the next service that must not be archived will be
added by somebody who never read this file, and the symptom — one failed job among many — is the
kind that gets retried rather than read. A silent drop from the backup roster must cost a commit.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKUP_VALUES = ROOT / "deploy" / "services" / "backup-service.values.yaml"
PRIVACY_VALUES = ROOT / "deploy" / "services" / "compliance-service.values.yaml"
SEEDER = ROOT / "deploy" / "seed" / "seed-backup-targets.sh"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def value_of(text: str, key: str) -> str | None:
    m = re.search(rf'^\s*{re.escape(key)}:\s*"([^"]*)"', text, re.M)
    return m.group(1) if m else None


def main() -> int:
    bad: list[str] = []

    for path in (BACKUP_VALUES, PRIVACY_VALUES, SEEDER):
        if not path.is_file():
            # LOUD, NOT SKIPPED. A gate that cannot find its subject has not checked it.
            print(f"{C_R}{path.relative_to(ROOT).as_posix()} is missing — this gate cannot run, "
                  f"which is not the same as finding nothing wrong{C_N}")
            return 1

    backup_text = BACKUP_VALUES.read_text(encoding="utf-8")
    privacy_text = PRIVACY_VALUES.read_text(encoding="utf-8")
    seeder_text = SEEDER.read_text(encoding="utf-8")

    exempt_raw = value_of(backup_text, "BACKUP_EXEMPT")
    if exempt_raw is None:
        bad.append("backup-service.values.yaml declares no BACKUP_EXEMPT — without it the roster "
                   "is inherited from PRIVACY_TARGETS wholesale, and a service that cannot be "
                   "archived gets registered and fails the run every night")
        exempt_raw = ""

    exempt = [s.strip() for s in exempt_raw.split(",") if s.strip()]

    roster_raw = value_of(privacy_text, "PRIVACY_TARGETS") or ""
    known = {pair.split("=", 1)[0].strip()
             for pair in roster_raw.split(",") if "=" in pair}
    if not known:
        bad.append("PRIVACY_TARGETS is empty or unreadable — the roster this gate reasons about "
                   "does not exist, and an empty set is not agreement")

    for name in exempt:
        if known and name not in known:
            bad.append(f"BACKUP_EXEMPT names `{name}`, which is not in PRIVACY_TARGETS. An "
                       f"exemption for a service that is never on the roster excludes nothing — "
                       f"and if this is a typo, the service it meant is still being registered")

    if "BACKUP_EXEMPT" not in seeder_text:
        bad.append("seed-backup-targets.sh never reads BACKUP_EXEMPT — the exemption is a comment "
                   "with a colon in it, and the seeder still registers everything on the roster")

    if bad:
        print(f"{C_R}the backup roster is inherited rather than decided{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Declare it in deploy/services/backup-service.values.yaml, with the reason.")
        return 1

    kept = len(known) - len(exempt)
    print(f"{C_G}ok{C_N}  {kept} services archived, {len(exempt)} exempt by declaration "
          f"({', '.join(exempt) or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
