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
#: SHARED COPY — this module is pasted into every service, and its CODE must stay identical in
#: all of them. These are separate deployables with no package to share, so the copies are held
#: equal by `ci/check_a_module_copied_into_every_service_stays_one_module.py` rather than by
#: anybody remembering. Prose may differ; logic may not. Removing this line is itself a failure.

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
    # ALREADY A PSEUDONYM (د-2, same defect a sibling service's own pii.py names in full). An
    # erasure fans out by the pseudonym, since that is the one identifier every other service
    # holds — hashing it AGAIN here would produce the ref of a ref, matching no row anywhere: the
    # scan finds nothing, answers `already_absent` with 200, and the request closes COMPLETED
    # while every message and pseudonymised record stays exactly where it was.
    #
    # IDEMPOTENT, NOT REFUSED. A caller that already holds a subject_ref and passes it back in is
    # the ordinary case, not the bug — folding it to itself fixes the defect without turning that
    # ordinary call into a crash.
    if is_subject_ref(subject):
        return subject
    mac = hmac.new(salt.encode("utf-8"),
                   f"{tenant}|{subject}".encode("utf-8"),
                   hashlib.sha256)
    return _PREFIX + mac.hexdigest()[:_LEN]


def is_subject_ref(value: str) -> bool:
    """True if `value` already looks like a pseudonym (so we never double-wrap one)."""
    return isinstance(value, str) and value.startswith(_PREFIX) and len(value) == len(_PREFIX) + _LEN
