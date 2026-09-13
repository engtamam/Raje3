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

# WHAT THE ENGINE INITIATES — which is what the subscription is being judged on.
#
# THIS USED TO READ `{"marketing", "reminder"}` AND «reminder» IS NOT A CLASS. The vocabulary is
# `service · personal · awareness · warning · marketing`; every reminder in the product is
# scheduled as `service`, and so is every rung of the follow-up ladder. So the moment the holdout
# was switched on, MARKETING ALONE would be withheld — while `insights` published «أثر الرسائل،
# مقيساً» as the difference between two groups that both received every reminder and every
# follow-up. Noise, published with confidence, in the one figure that claims not to be us talking
# about ourselves — and wrong in the direction that flatters us. `reminder` is what we CALL the
# thing in every conversation; that is exactly why it was written and why nobody caught it.
#
# AND THE CLASS ALONE STILL CANNOT SAY IT. `service` holds both the reminder we send on our own
# schedule AND the confirmation of a visit the customer made ten seconds ago. Withholding the
# second would be a customer walking out of a shop having been told nothing — a real harm, done to
# a real person, to tidy up a measurement.
#
# So the line is drawn where it actually falls: WE INITIATED IT versus WE ACKNOWLEDGED SOMETHING
# HE DID. The same distinction, in the same words, that `WINDOW_EXEMPT_TYPES` in gate.py already
# had to make — «reminders and follow-ups are service-class too, and neither is a reply to
# anything».
WITHHELD_CLASSES = frozenset({"marketing", "awareness"})

# The two proactive templates that live under a class we otherwise deliver in full. Named rather
# than prefixed because there are exactly two and each one is a decision: `svc_service_reminder`
# is the reminder itself, `svc_follow_up` is the ladder. `svc_visit_confirmation` and
# `svc_visit_redeemed` acknowledge something that just happened and are never withheld.
WITHHELD_TYPES = frozenset({"svc_service_reminder", "svc_follow_up"})


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


def withholds(cls: str, template_type: str = "") -> bool:
    """Is this a message WE started, rather than an answer to something he did?"""
    return cls in WITHHELD_CLASSES or template_type in WITHHELD_TYPES


def refusal(share: int = DEFAULT_SHARE) -> str:
    """The reason, written for the owner's own send log — where every refusal in this service ends
    up. It says what happened and why in one line, because «not sent» is the sentence support
    cannot answer."""
    return (
        f"ضمن مجموعة القياس ({share}% من عملائك لا تصلهم رسائل الحملات والعروض) — "
        "لنقيس أثر راجِع على محلّك بالمقارنة. يمكن إيقاف القياس من إعدادات محلّك."
    )
