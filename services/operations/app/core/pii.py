"""subject_ref — the pseudonym that lets an immutable record outlive the person in it.

An audit event is hash-chained: redact a field and `verify()` fails from that seq onward, and
tamper-evidence is the product. A ledger row and a tax invoice are immutable for the same reason
in law. So a person's identity must never be WRITTEN into one of those records in the first place.

Instead they carry `subject_ref`: a per-tenant pseudonym.

    subject_ref = HMAC-SHA256(PII_SALT, "<tenant>|<subject>")

Two properties earn it its place:

  * It is a PURE FUNCTION. Computing it needs no lookup, so the audit/analytics WRITE path — the
    hottest path in the platform — gains zero datastore reads. Only the reverse direction
    (pseudonym -> person) needs a stored mapping, and that is read on a DSAR, not per event.

  * It is stable and tenant-scoped. The same person in one tenant always folds to the same ref, so
    the record stays queryable ("what did this subject do?") forever. Two tenants never collide.

ERASURE then means: delete the mutable PII, and destroy the LINKAGE (subject_ref -> person). The
immutable record never changes — the chain still verifies, the invoice is still filed — it simply
can no longer name anybody. That is exactly what privacy law and tax law both ask for.

PII_SALT is a FROZEN identifier (config/product.identifiers.lock.json). Change it and every
pseudonym in every immutable record re-maps: the history orphans, and an erasure can no longer
prove it erased the right person. It is guarded by safety:product for that reason.
"""
from __future__ import annotations

import hashlib
import hmac

_PREFIX = "sub_"
_LEN = 32          # 128 bits of the digest — collision-safe, and short enough to index


def subject_ref(salt: str, tenant: str, subject: str) -> str:
    """The pseudonym for `subject` within `tenant`. Pure; no I/O; stable forever.

    `salt` must be the product's PII_SALT. An empty salt is refused rather than silently
    producing an unsalted (and therefore reversible by brute force) pseudonym.
    """
    if not salt:
        raise ValueError("PII_SALT is empty — an unsalted pseudonym is reversible by guessing "
                         "every email address, which is not a pseudonym at all")
    if not subject:
        raise ValueError("subject must not be empty")
    # ALREADY A PSEUDONYM — REFUSED, NEVER WRAPPED AGAIN (د-2).
    #
    # `compliance` fans an erasure out by the pseudonym, because that is the only identifier every
    # other service holds. This one holds the phone number too, and hashed what it was handed: the
    # ref of a ref matches no row anywhere, so the scan found nothing, answered `already_absent`
    # with 200, and the request closed COMPLETED. The name, the number, the plate and the notes
    # stayed exactly where they were — in the ONE service that holds the real identifier — and the
    # customer was told his data was gone, on a legal deadline, with nothing in any log.
    #
    # The guard for this existed in this file from the start and had no production caller. Putting
    # it HERE rather than at the one call site is the difference between fixing a defect and
    # removing its shape: a caller that hands this function a ref now fails loudly, and there is no
    # list of exceptions to keep.
    if is_subject_ref(subject):
        raise ValueError("subject is already a pseudonym — hashing it again produces a ref that "
                         "matches no row, and an erasure that finds nothing reports success")
    mac = hmac.new(salt.encode("utf-8"),
                   f"{tenant}|{subject}".encode("utf-8"),
                   hashlib.sha256)
    return _PREFIX + mac.hexdigest()[:_LEN]


def is_subject_ref(value: str) -> bool:
    """True if `value` already looks like a pseudonym (so we never double-wrap one)."""
    return isinstance(value, str) and value.startswith(_PREFIX) and len(value) == len(_PREFIX) + _LEN
