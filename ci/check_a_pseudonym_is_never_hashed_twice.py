"""Every `subject_ref()` in this fleet must refuse a subject that is already a pseudonym.

WHAT IT COST (د-2). `compliance` fans an erasure out by the PSEUDONYM, because that is the only
identifier every service holds. `operations` holds the phone number too, so its erasure hashed
what it was handed — and the ref of a ref matches no row anywhere. The scan found nothing, the
route answered `already_absent` with 200, the dispatcher read ACKED, and `derive_completion`
closed the request COMPLETED. The name, the number, the plate and the notes stayed exactly where
they were, in the ONE service holding the real identifier, and the person was told their data was
erased — on a legal deadline, with nothing in any log that disagreed.

THE GUARD EXISTED THE WHOLE TIME AND HAD NO CALLER. `is_subject_ref()` sits in all six copies of
`pii.py`; not one of them used it. That is the part worth a standing check: the defect was not a
missing idea, it was an idea nobody wired up, and it survived a review that read the file it was
written in.

WHY THE FUNCTION AND NOT THE CALL SITE. Guarding the one erasure that lost this would fix the
defect and leave its shape: the next caller to hand a ref to a hasher gets the same silence. In
the function, the mistake is impossible to make quietly in any of the six services, and there is
no list of exceptions to keep current.

SO THIS GATE READS BEHAVIOUR, NOT PROSE — it imports each service's `subject_ref` and hands it a
real pseudonym. A comment describing the guard, a helper named for it, or a test asserting it all
satisfy a grep; only calling the function proves the guard is wired. That distinction has cost
this repository four separate defects in a week.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

SALT = "gate-salt-not-a-real-one"
TENANT = "t1"


def _load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"pii_{path.parent.parent.parent.name}", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    files = sorted(SERVICES.glob("*/app/core/pii.py"))
    if not files:
        # SILENCE IS NOT AGREEMENT: reading nothing is not the same as finding nothing, and this
        # gate guards a PDPL obligation. If the file moved, it must say so rather than pass.
        print("no services/*/app/core/pii.py found — this gate cannot answer, so it refuses to")
        return 1

    hits: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        service = path.parents[2].name
        try:
            mod = _load(path)
        except Exception as exc:                                          # noqa: BLE001
            print(f"cannot import {rel}: {exc}")
            return 1
        if mod is None or not hasattr(mod, "subject_ref"):
            hits.append(f"{rel}: no subject_ref() to check — this gate needs re-pointing")
            continue

        # A REAL PSEUDONYM, MADE BY THE SERVICE'S OWN FUNCTION. Hand-writing one would test this
        # gate's idea of the format rather than the service's.
        ref = mod.subject_ref(SALT, TENANT, "966501234567")
        try:
            again = mod.subject_ref(SALT, TENANT, ref)
        except ValueError:
            continue                                                      # refused, as required
        hits.append(f"{rel}: {service}.subject_ref() hashed a pseudonym again and returned "
                    f"{again[:12]}… instead of refusing")

    if hits:
        print(f"{len(hits)} of {len(files)} pseudonym function(s) will hash a ref a second time:")
        for h in hits:
            print("  " + h)
        print("\nThe ref of a ref matches no row anywhere. The caller doing it is an erasure, so")
        print("the scan finds nothing, answers `already_absent` with 200, and the request closes")
        print("COMPLETED — the person is told their data is gone while all of it remains.")
        print("\nRaise ValueError when `is_subject_ref(subject)`. The helper is already in the")
        print("file; d-2 happened because nothing called it.")
        return 1

    print(f"{len(files)} pseudonym function(s): every one refuses to hash a ref a second time")
    return 0


if __name__ == "__main__":
    sys.exit(main())
