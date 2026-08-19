"""د-2 · handing a pseudonym back to the hasher must fold to itself, not produce a ref of a ref.

WHY A TEST HERE, IN A SERVICE THAT NEVER LOST THIS. `operations` is where it was lost: compliance
fans an erasure out by the pseudonym — the only identifier every service holds — and operations
hashed what it was handed. The ref of a ref matches no row, so the scan found nothing, answered
`already_absent` with 200, the dispatcher read ACKED, and the request closed COMPLETED. The person
was told their data was erased while the name, the number, the plate and the notes sat untouched.

This service's `subject_ref` is only ever called on a token's `sub` today, so nothing is broken
here — and that is exactly the reason to pin it. `pii.py` is one file copied into six services;
the guard was added to one of them, and the next erasure written in any of the other five would
have reproduced a critical PDPL defect with no guard and no failing test to notice.

IDEMPOTENT, NOT REFUSED (v0.16.23). The original guard raised on a double-wrap, but a caller that
already holds a subject_ref and passes it along again is the ORDINARY case — that call needed to
keep working, not crash. Folding it to itself fixes the same defect without turning routine reuse
into an outage.
"""
from __future__ import annotations

SALT = "test-salt"
TENANT = "t1"


def test_hashing_a_pseudonym_again_folds_to_the_same_pseudonym() -> None:
    from app.core.pii import subject_ref

    ref = subject_ref(SALT, TENANT, "966501234567")

    assert subject_ref(SALT, TENANT, ref) == ref


def test_a_real_subject_still_hashes_and_stays_stable() -> None:
    """The guard must not cost the ordinary path — a pseudonym is stable forever by contract."""
    from app.core.pii import subject_ref

    once = subject_ref(SALT, TENANT, "966501234567")
    twice = subject_ref(SALT, TENANT, "966501234567")
    assert once == twice
    assert once.startswith("sub_")


def test_the_same_person_in_two_shops_is_two_different_people_here() -> None:
    """Tenant is inside the MAC, so a ref cannot be carried across an establishment boundary."""
    from app.core.pii import subject_ref

    assert subject_ref(SALT, "t1", "966501234567") != subject_ref(SALT, "t2", "966501234567")
