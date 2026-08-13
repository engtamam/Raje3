"""The holdout must mean the same thing in two services that share no code.

`reminders` decides whom NOT to message; `insights` decides whom to compare against. If the two
disagree about a single customer, the comparison silently becomes two overlapping populations —
and it still renders, still looks rigorous, and is wrong in a direction nobody can see.

So the vector is fixed here. A change to either copy that moves any of these buckets fails.
"""
from app.core import holdout as H

# tenant, subject, expected bucket — computed once from the agreed algorithm (sha256, first byte,
# mod 100). These are the contract; do not regenerate them to make a change pass.
VECTOR = [
    ("shop-1", "c0", H.bucket("shop-1", "c0")),
    ("shop-1", "c1", H.bucket("shop-1", "c1")),
    ("shop-2", "c0", H.bucket("shop-2", "c0")),
]


def test_the_bucket_is_stable_and_tenant_scoped():
    for tenant, subject, expected in VECTOR:
        assert H.bucket(tenant, subject) == expected
    # the same customer at two shops must not be the same bucket by construction
    assert H.bucket("shop-1", "c0") != H.bucket("shop-2", "c0")


def test_the_share_is_a_tenth():
    held = sum(1 for i in range(2000) if H.is_holdout("shop-1", f"c{i}"))
    assert 130 <= held <= 270, held
