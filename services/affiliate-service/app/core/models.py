# =============================================================================
# affiliate-service — domain records for Slice 2 (application → approval → account)
# -----------------------------------------------------------------------------
# Two rows, and why they are not one.
#
#   Application   what a person SUBMITTED, before anybody has judged it. Nothing here grants
#                 access to anything — this row exists purely so «بوابة القبول» (spec §2) has
#                 something to show a platform admin, and so a rejected/duplicate attempt has a
#                 place to be recorded rather than silently vanishing.
#
#   Affiliate     what a person IS, once approved: an identity-service account exists for them,
#                 they hold a role, and — for a promoter — they have a manager. This is the row
#                 every other slice (commission, dashboard, leads) hangs off, keyed on the SAME
#                 person_id identity minted, never on the phone number (a phone can be recycled;
#                 a person_id cannot mean two different people).
#
# ONE SHARED TENANT, spec §1/§12: marketers are not a shop, so there is exactly one tenant for
# all of them — its id lives in Settings.AFFILIATE_TENANT, never guessed here.
# =============================================================================
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


def new_id() -> str:
    return uuid.uuid4().hex


APPLICATIONS = "affiliate_applications"
AFFILIATES = "affiliates"

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
APPLICATION_STATUSES = (PENDING, APPROVED, REJECTED)

MANAGER = "affiliate_manager"
PROMOTER = "affiliate_promoter"
ROLES = (MANAGER, PROMOTER)

ACTIVE = "active"
SUSPENDED = "suspended"
#: A promoter/manager who left — kept, never deleted, so a commission already earned still has
#: someone real behind it. Mirrors operations' own staff model (revoked, not erased).
DEPARTED = "departed"
AFFILIATE_STATUSES = (ACTIVE, SUSPENDED, DEPARTED)


@dataclass
class Application:
    id: str
    phone: str
    name: str
    #: The REFERRING affiliate's id, empty for a manager applicant. Resolved and stored at
    #: apply-time so approval never has to trust a code typed twice — see onboarding.py.
    parent_id: str = ""
    status: str = PENDING
    created_at: int = 0
    decided_at: int = 0
    #: The admin who approved/rejected — a subject_ref, never a raw identifier (see api/deps
    #: actor pattern already used by operator.py in this service).
    decided_by: str = ""
    reason: str = ""
    #: HMAC(PII_SALT, tenant, phone) — computed once at apply() time so a DSAR against this
    #: number finds the row without operations/erasure.py having to re-derive it from a phone it
    #: may itself have already blanked. See erasure.py.
    subject_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "phone": self.phone, "name": self.name,
            "parent_id": self.parent_id, "status": self.status,
            "created_at": self.created_at, "decided_at": self.decided_at,
            "decided_by": self.decided_by, "reason": self.reason,
            "subject_ref": self.subject_ref,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Application":
        return cls(
            id=str(d.get("id", "")), phone=str(d.get("phone", "")),
            name=str(d.get("name", "")), parent_id=str(d.get("parent_id", "")),
            status=str(d.get("status", PENDING)), created_at=int(d.get("created_at", 0)),
            decided_at=int(d.get("decided_at", 0)), decided_by=str(d.get("decided_by", "")),
            reason=str(d.get("reason", "")), subject_ref=str(d.get("subject_ref", "")),
        )


@dataclass
class Affiliate:
    id: str
    #: identity-service's person_id — the token's `sub` once this affiliate signs in. THE join
    #: key for every later slice; never the phone (see module docstring).
    person_id: str
    phone: str
    name: str
    role: str
    parent_id: str = ""
    status: str = ACTIVE
    #: The application this account was approved from — kept for audit, never re-read for
    #: authority (the Affiliate row itself, once written, is the authority).
    application_id: str = ""
    created_at: int = 0
    #: Same derivation as Application.subject_ref — see erasure.py.
    subject_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "person_id": self.person_id, "phone": self.phone,
            "name": self.name, "role": self.role, "parent_id": self.parent_id,
            "status": self.status, "application_id": self.application_id,
            "created_at": self.created_at, "subject_ref": self.subject_ref,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Affiliate":
        return cls(
            id=str(d.get("id", "")), person_id=str(d.get("person_id", "")),
            phone=str(d.get("phone", "")), name=str(d.get("name", "")),
            role=str(d.get("role", PROMOTER)), parent_id=str(d.get("parent_id", "")),
            status=str(d.get("status", ACTIVE)), application_id=str(d.get("application_id", "")),
            created_at=int(d.get("created_at", 0)), subject_ref=str(d.get("subject_ref", "")),
        )
