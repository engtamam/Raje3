"""The holdout — reading the group that `reminders` withholds from (proof 2).

A DELIBERATE COPY OF services/reminders/app/core/holdout.py, AND THE COPY IS THE POINT. Two
services with no shared library must agree byte-for-byte on who is in the group: reminders decides
whom to skip, insights decides whom to compare, and a service boundary between them is exactly the
seam where two «roughly the same» hashes drift into a comparison of two overlapping populations —
which is worse than no comparison, because it looks rigorous.

tests/contracts/test_holdout_vector.py pins the same fixed inputs to the same fixed buckets on both
sides, so drift fails a build instead of quietly corrupting a number the owner is shown.

WHAT FOLLOWS IS THE ORIGINAL FILE'S REASONING, KEPT VERBATIM so the copy does not become the
version nobody understands.


THE ONLY HONEST ANSWER TO «هل الرسائل تنفع أم تزعج؟» IS ONE HE MEASURES HIMSELF. Every other answer
we could give is our word for our own product: a return rate of 52% proves nothing without the
number the same shop would have had in silence. So a fixed tenth of his customers receive no
reminder, no offer and no campaign — and the difference between the two groups is the whole claim,
stated in his own data.

DETERMINISTIC, NOT STORED, AND NEVER RE-ROLLED. The group is a pure function of the tenant and the
customer, so it needs no table, survives a restore, and — the part that matters — cannot drift. A
customer who moves between groups destroys the comparison in a way nobody notices: he gets the
messages for six months, stops getting them, and is then counted as evidence that silence works.

SHA-256 AND NOT hash(). Python's built-in hash is salted per process (PYTHONHASHSEED), so the same
customer would land in a different group after every pod restart — which is the drifting-membership
bug above, arriving through the back door.

WHAT IS WITHHELD, AND WHAT NEVER IS.

    withheld    reminder · offer · marketing campaign      — the engine, which is what we are proving
    always sent visit confirmation · redemption receipt · anything he asked for personally

A confirmation is not a nudge; it is a receipt for something the customer just did, and withholding
it would make the holdout a worse experience rather than a quieter one. The comparison stays about
the ENGINE, which is the thing being paid for.

AND THE OWNER CAN SWITCH IT OFF. Some will not accept withholding an offer from a real customer,
and that is his call to make about his own shop — `enabled` comes from his settings, defaults on,
and the moment it is off the two groups merge and the comparison stops being drawn rather than
being drawn wrong.
"""
from __future__ import annotations

import hashlib

# A tenth. Large enough that the two groups separate within a season on a shop doing a hundred
# visits a month, small enough that he is not withholding his product from a quarter of his people.
DEFAULT_SHARE = 10

# THE CLASSES THE ENGINE OWNS. Everything else — service confirmations, personal replies, warnings —
# goes out to everybody, because none of them is what the subscription is being judged on.
WITHHELD_CLASSES = frozenset({"marketing", "reminder"})


def bucket(tenant: str, subject_ref: str) -> int:
    """0–99, stable for ever for this pair.

    The tenant is inside the hash on purpose: the same customer at two shops must not land in the
    holdout at both, or a person who happens to hash low would be systematically under-served
    across the whole platform.
    """
    digest = hashlib.sha256(f"{tenant}|{subject_ref}".encode("utf-8")).digest()
    return digest[0] % 100


def is_holdout(tenant: str, subject_ref: str, *, share: int = DEFAULT_SHARE,
               enabled: bool = True) -> bool:
    if not enabled or share <= 0 or not subject_ref:
        # NO SUBJECT MEANS NO HOLDOUT. A message with no customer behind it is a broadcast or a
        # test, and silently dropping a tenth of those would look like a flaky sender.
        return False
    return bucket(tenant, subject_ref) < share


def withholds(cls: str) -> bool:
    return cls in WITHHELD_CLASSES


def refusal(share: int = DEFAULT_SHARE) -> str:
    """The reason, written for the owner's own send log — where every refusal in this service ends
    up. It says what happened and why in one line, because «not sent» is the sentence support
    cannot answer."""
    return (
        f"ضمن مجموعة القياس ({share}% من عملائك لا تصلهم رسائل الحملات والعروض) — "
        "لنقيس أثر راجِع على محلّك بالمقارنة. يمكن إيقاف القياس من إعدادات محلّك."
    )
