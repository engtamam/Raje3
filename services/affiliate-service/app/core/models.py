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
REFERRALS = "affiliate_referrals"

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
#: A manager-invited row between identity minting the membership and the invited person setting
#: their OWN password — see onboarding.py::invite/accept_invite. Never reachable from self-apply:
#: there the applicant's own chosen password is redeemed server-side at approval, so the row goes
#: straight to ACTIVE (spec §2's admin gate already vouches for the applicant either way — this
#: status is about WHO holds the credential, not about whether anyone approved the account).
INVITED = "invited"
AFFILIATE_STATUSES = (ACTIVE, SUSPENDED, DEPARTED, INVITED)


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
    #: spec §2: "قبول الشروط إجباري قبل التفعيل" — WHICH version he agreed to and WHEN, so a
    #: later dispute has an answer. Never blank on a real row: apply() refuses to write one
    #: without both. See Settings.AFFILIATE_TERMS_VERSION.
    agreed_terms_version: str = ""
    agreed_at: int = 0
    #: The INVITING affiliate's own id — set ONLY when a manager sent this invitation (see
    #: onboarding.py::invite), blank for a self-submitted application. Deliberately a SEPARATE
    #: field from `parent_id`, even though both currently hold the same value: `parent_id` is a
    #: referral fact (who gets credit), `invited_by` is a PROVENANCE fact that decides which
    #: branch approve() takes (redeem a chosen password vs. mint an invite the person claims
    #: themself) — collapsing them would make a future self-apply-with-referral-code request
    #: silently take the no-password invite branch it was never meant to.
    invited_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "phone": self.phone, "name": self.name,
            "parent_id": self.parent_id, "status": self.status,
            "created_at": self.created_at, "decided_at": self.decided_at,
            "decided_by": self.decided_by, "reason": self.reason,
            "subject_ref": self.subject_ref, "invited_by": self.invited_by,
            "agreed_terms_version": self.agreed_terms_version, "agreed_at": self.agreed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Application":
        return cls(
            id=str(d.get("id", "")), phone=str(d.get("phone", "")),
            name=str(d.get("name", "")), parent_id=str(d.get("parent_id", "")),
            status=str(d.get("status", PENDING)), created_at=int(d.get("created_at", 0)),
            decided_at=int(d.get("decided_at", 0)), decided_by=str(d.get("decided_by", "")),
            reason=str(d.get("reason", "")), subject_ref=str(d.get("subject_ref", "")),
            invited_by=str(d.get("invited_by", "")),
            agreed_terms_version=str(d.get("agreed_terms_version", "")),
            agreed_at=int(d.get("agreed_at", 0)),
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
    #: identity-service's one-time invite_token, held ONLY while status == INVITED — see
    #: onboarding.py::accept_invite. Blank the moment it is redeemed, same reasoning as
    #: `_PENDING_SECRET`: a credential-adjacent value outlives its purpose by exactly zero calls.
    invite_token: str = ""
    #: spec §2's consent, on the row that actually earns commission — copied from the
    #: Application at approval for a self-applicant (he already agreed at apply() time), or set
    #: directly at accept_invite() for a manager-invited one (HE never agreed to anything until
    #: that moment; a manager's own agreement cannot stand in for his). Blank means "not yet
    #: agreed" — true only for an INVITED row still waiting on its own person.
    agreed_terms_version: str = ""
    agreed_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "person_id": self.person_id, "phone": self.phone,
            "name": self.name, "role": self.role, "parent_id": self.parent_id,
            "status": self.status, "application_id": self.application_id,
            "created_at": self.created_at, "subject_ref": self.subject_ref,
            "invite_token": self.invite_token,
            "agreed_terms_version": self.agreed_terms_version, "agreed_at": self.agreed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Affiliate":
        return cls(
            id=str(d.get("id", "")), person_id=str(d.get("person_id", "")),
            phone=str(d.get("phone", "")), name=str(d.get("name", "")),
            role=str(d.get("role", PROMOTER)), parent_id=str(d.get("parent_id", "")),
            status=str(d.get("status", ACTIVE)), application_id=str(d.get("application_id", "")),
            created_at=int(d.get("created_at", 0)), subject_ref=str(d.get("subject_ref", "")),
            invite_token=str(d.get("invite_token", "")),
            agreed_terms_version=str(d.get("agreed_terms_version", "")),
            agreed_at=int(d.get("agreed_at", 0)),
        )


# ── who brought this establishment — the fact commission is paid on ────────────────────────────
#: A referred shop that later cancels or never pays is still a real referral — the establishment
#: was brought, whatever it does afterward. "Did it actually pay" is billing's own fact, read at
#: PAYOUT time (a later slice), never baked into this row: recomputing eligibility here would be
#: a second, driftable copy of what billing already knows.
REFERRED = "referred"
#: A referral an admin reversed — fraud, a duplicate stamp support corrected by hand, or a shop
#: that was never real. KEPT, not deleted: the same "retain, don't erase the fact" principle as
#: everything else in this file — a reversed commission is still a decision that happened.
REVOKED = "revoked"
#: The shop registered through this affiliate but never converted to a paid subscription within
#: the CONVERSION WINDOW (Settings.AFFILIATE_CONVERSION_WINDOW_DAYS from `stamped_at` — Tamam,
#: 2026-08-19: bounding this is what stops "a marketer we haven't heard from in two years shows
#: up demanding commission on a shop that just converted" from being an open-ended, undocumented
#: argument instead of a written rule). NOT revoked — nobody did anything wrong, the window
#: simply lapsed. The row (who referred whom, when) stays exactly as true as it always was; only
#: the money stops being possible. Set by whichever code path first checks eligibility after
#: `expires_at` has passed — see core/referrals.py::lapse_if_expired, called at commission-compute
#: time (a later slice) rather than by a sweep, since nothing needs to know until that moment.
LAPSED = "lapsed"
REFERRAL_STATUSES = (REFERRED, REVOKED, LAPSED)


@dataclass
class Referral:
    """One establishment, one affiliate, forever — see the module note on partners.py's own
    identical rule (operations/core/partners.py): the FIRST stamp wins and is never rewritten,
    or a shop that changes which marketer it heard from last would silently redirect commission
    away from whoever actually brought it."""

    id: str                 # == tenant. One row per establishment — see _stamp's own guard.
    tenant: str
    affiliate_id: str
    shop_name: str = ""
    status: str = REFERRED
    #: LOCKED AT SIGNUP (spec §4) — a flat amount in halalas (integer, never a float; see
    #: core/onboarding.py's own int-timestamp convention for why this codebase avoids float
    #: money). Copied from Settings.AFFILIATE_COMMISSION_AMOUNT_HALALAS at stamp time and never
    #: re-read from config afterward: a rate change next quarter must not silently rewrite what
    #: this specific referral was promised the day it was brought in.
    commission_amount_halalas: int = 0
    stamped_at: int = 0
    #: stamped_at + Settings.AFFILIATE_CONVERSION_WINDOW_DAYS, computed ONCE at stamp time —
    #: never re-derived from a config value that might change later, same "locked, not
    #: recalculated" reasoning as `commission_amount_halalas` right above it.
    expires_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "affiliate_id": self.affiliate_id,
            "shop_name": self.shop_name, "status": self.status,
            "commission_amount_halalas": self.commission_amount_halalas,
            "stamped_at": self.stamped_at, "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Referral":
        return cls(
            id=str(d.get("id", "")), tenant=str(d.get("tenant", "")),
            affiliate_id=str(d.get("affiliate_id", "")), shop_name=str(d.get("shop_name", "")),
            status=str(d.get("status", REFERRED)),
            commission_amount_halalas=int(d.get("commission_amount_halalas", 0)),
            stamped_at=int(d.get("stamped_at", 0)), expires_at=int(d.get("expires_at", 0)),
        )


# ── what a real payment actually earned — spec §4's two commission types ───────────────────────
COMMISSIONS = "affiliate_commissions"

CONVERSION = "conversion"     # the FIRST paid invoice — billing's own paid_sequence == 1
RENEWAL = "renewal"           # the configured Nth renewal — billing's subscription_paid_sequence
COMMISSION_KINDS = (CONVERSION, RENEWAL)

#: "مُستحقة" ليست "مؤكدة" — spec §4's own freeze. A commission is real the moment the invoice it
#: is keyed on is paid; it is not WITHDRAWABLE until Settings.AFFILIATE_COMMISSION_HOLD_DAYS has
#: passed from that same paid_at, in case the payment is refunded within it.
#: Reuses Application's own `PENDING` ("pending") rather than a second constant with the same
#: value — two names for one string is how a future `d.get("status") == PENDING` compares against
#: the wrong PENDING by accident.
CONFIRMED = "confirmed"
#: The invoice it was keyed on was refunded (in full or in part) before or during the hold — spec
#: §4 gives no commission on money that was given back. KEPT, not deleted: same reasoning as
#: Referral's own LAPSED/REVOKED — a voided commission is still a decision with a reason,
#: answerable to a marketer who disputes it later.
VOIDED = "voided"
COMMISSION_STATUSES = (PENDING, CONFIRMED, VOIDED)


@dataclass
class Commission:
    #: THE INVOICE'S OWN id — the natural idempotency key. billing-service's paid-invoice history
    #: is the durable read this is synced from (never the at-most-once event bus; see
    #: core/commission.py's own module docstring), and a sync that runs twice over the same
    #: history must produce the same one row, not two.
    id: str
    tenant: str
    affiliate_id: str
    kind: str
    #: Copied from Referral.commission_amount_halalas (conversion) or
    #: Settings.AFFILIATE_RENEWAL_COMMISSION_HALALAS (renewal) AT THE MOMENT this row is created —
    #: same "locked, never re-read from config later" rule as the Referral row itself.
    amount_halalas: int
    status: str = PENDING
    #: billing's own `paid_at` for the invoice this was earned on — ISO 8601, billing's format,
    #: never re-derived. The hold is computed FROM this, not from when our sync happened to run.
    earned_at: str = ""
    #: earned_at + Settings.AFFILIATE_COMMISSION_HOLD_DAYS, computed once at creation — see the
    #: field's twin on Referral (expires_at) for why this is never re-derived from config later.
    confirms_at: int = 0
    created_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "affiliate_id": self.affiliate_id,
            "kind": self.kind, "amount_halalas": self.amount_halalas, "status": self.status,
            "earned_at": self.earned_at, "confirms_at": self.confirms_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Commission":
        return cls(
            id=str(d.get("id", "")), tenant=str(d.get("tenant", "")),
            affiliate_id=str(d.get("affiliate_id", "")), kind=str(d.get("kind", CONVERSION)),
            amount_halalas=int(d.get("amount_halalas", 0)), status=str(d.get("status", PENDING)),
            earned_at=str(d.get("earned_at", "")), confirms_at=int(d.get("confirms_at", 0)),
            created_at=int(d.get("created_at", 0)),
        )
