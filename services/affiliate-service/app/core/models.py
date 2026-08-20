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
from dataclasses import dataclass, field
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
    #: HOW HE WANTS TO BE PAID — spec §5, extended (Tamam, 2026-08-20) to accept an intermediary
    #: payment platform (e.g. بحر) as a real alternative to a bank IBAN, not just a fallback.
    #: `payout_channel` is "bank_iban" | "intermediary"; `payout_channel_name` is free text for
    #: the intermediary case (never hardcoded to one provider — a new one tomorrow needs no code
    #: change); `payout_account_ref` is the IBAN or the marketer's account identifier on that
    #: platform. This is the CURRENT method — a WithdrawalRequest copies it at request time (spec
    #: §4's own "locked, not re-read later" principle, applied here to where the money goes).
    payout_channel: str = ""
    payout_channel_name: str = ""
    payout_account_ref: str = ""
    #: spec §10's optional whole-platform revenue view (Tamam, 2026-08-20) — OFF by default for
    #: every manager. An admin-only grant (see api/v1/admin.py), never self-service: seeing what
    #: the affiliate channel earns platform-wide is a broader window than "my own tree", and
    #: nobody grants that to himself. The moment it is set True, /me/team simply starts returning
    #: the platform figure — no separate rollout step, no code change, matches the standing
    #: infra-first / activate-from-the-UI-later pattern already used for the console feature
    #: itself.
    sees_platform_revenue: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "person_id": self.person_id, "phone": self.phone,
            "name": self.name, "role": self.role, "parent_id": self.parent_id,
            "status": self.status, "application_id": self.application_id,
            "created_at": self.created_at, "subject_ref": self.subject_ref,
            "invite_token": self.invite_token,
            "agreed_terms_version": self.agreed_terms_version, "agreed_at": self.agreed_at,
            "payout_channel": self.payout_channel,
            "payout_channel_name": self.payout_channel_name,
            "payout_account_ref": self.payout_account_ref,
            "sees_platform_revenue": self.sees_platform_revenue,
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
            payout_channel=str(d.get("payout_channel", "")),
            payout_channel_name=str(d.get("payout_channel_name", "")),
            payout_account_ref=str(d.get("payout_account_ref", "")),
            sees_platform_revenue=bool(d.get("sees_platform_revenue", False)),
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
#: RENEWAL retired (Tamam, 2026-08-20): paying a marketer on every Nth renewal was one flat
#: commission for indefinite, un-serviced revenue — replaced by a separate program (a threshold
#: of shops brought + real support/ticket work, its own KPI) rather than a recurring cut here.
#: `COMMISSION_KINDS` keeps only what this engine still creates; a "renewal" string can still
#: exist on a historical row (never rewritten — see Commission's own retain-don't-erase rule) and
#: simply is not a kind anything here produces or checks for anymore.
COMMISSION_KINDS = (CONVERSION,)

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
    #: Copied from Referral.commission_amount_halalas AT THE MOMENT this row is created — same
    #: "locked, never re-read from config later" rule as the Referral row itself.
    amount_halalas: int
    status: str = PENDING
    #: billing's own `paid_at` for the invoice this was earned on — ISO 8601, billing's format,
    #: never re-derived. The hold is computed FROM this, not from when our sync happened to run.
    earned_at: str = ""
    #: earned_at + Settings.AFFILIATE_COMMISSION_HOLD_DAYS, computed once at creation — see the
    #: field's twin on Referral (expires_at) for why this is never re-derived from config later.
    confirms_at: int = 0
    created_at: int = 0
    #: Empty means "available" — the one flag a withdrawal request needs to claim a confirmed
    #: commission without double-counting it into a second request. Set ONCE, when a request
    #: locks it in (core/payouts.py); cleared if that request is rejected, so a rejected request
    #: returns the money to the available balance rather than losing it in limbo.
    withdrawal_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "affiliate_id": self.affiliate_id,
            "kind": self.kind, "amount_halalas": self.amount_halalas, "status": self.status,
            "earned_at": self.earned_at, "confirms_at": self.confirms_at,
            "created_at": self.created_at, "withdrawal_id": self.withdrawal_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Commission":
        return cls(
            id=str(d.get("id", "")), tenant=str(d.get("tenant", "")),
            affiliate_id=str(d.get("affiliate_id", "")), kind=str(d.get("kind", CONVERSION)),
            amount_halalas=int(d.get("amount_halalas", 0)), status=str(d.get("status", PENDING)),
            earned_at=str(d.get("earned_at", "")), confirms_at=int(d.get("confirms_at", 0)),
            created_at=int(d.get("created_at", 0)),
            withdrawal_id=str(d.get("withdrawal_id", "")),
        )


# ── the withdrawal itself — spec §5 ─────────────────────────────────────────────────────────────
WITHDRAWALS = "affiliate_withdrawals"

REQUESTED = "requested"
COMPLETED = "completed"
#: A request an admin refused — a bad IBAN, a suspicious pattern, whatever the reason. The
#: commissions it had locked are RELEASED back to available balance (core/payouts.py::reject) —
#: a rejected request must never strand real money in limbo.
WITHDRAWAL_REJECTED = "rejected"
WITHDRAWAL_STATUSES = (REQUESTED, COMPLETED, WITHDRAWAL_REJECTED)


@dataclass
class WithdrawalRequest:
    id: str
    affiliate_id: str
    amount_halalas: int
    #: THE COMMISSIONS THIS REQUEST CLAIMS — never re-derived from a live "confirmed balance"
    #: query later, because that balance moves (more commissions confirm every day). Locked at
    #: request time so this row always answers "which specific commissions paid for this
    #: transfer", the same audit trail spec §5's own "لا نزاع ما استلمت" protection depends on.
    commission_ids: list[str] = field(default_factory=list)
    status: str = REQUESTED
    #: Copied from the Affiliate's CURRENT payout method at request time — see that field's own
    #: note on why this is locked rather than re-read from a method he might change afterward.
    payout_channel: str = ""
    payout_channel_name: str = ""
    payout_account_ref: str = ""
    requested_at: int = 0
    decided_at: int = 0
    decided_by: str = ""
    #: A receipt/confirmation-screenshot REFERENCE (a URL, or an object-store key — never the
    #: file itself in this row), attached the moment an admin marks a request completed. Spec
    #: §5: "يبقى محفوظاً كإثبات امتثال، يقدر المسوّق يعرضه لاحقاً".
    receipt_reference: str = ""
    #: Set ONLY when receipt_reference is an uploaded object (never for a pasted URL — nothing
    #: to serve back with a content-type for a link the admin already controls). Kept because
    #: the object store's own `get()` returns bytes alone; without this, serving the file back
    #: would have to guess its type from the key.
    receipt_content_type: str = ""
    reason: str = ""   # why rejected, if it was

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "affiliate_id": self.affiliate_id,
            "amount_halalas": self.amount_halalas, "commission_ids": list(self.commission_ids),
            "status": self.status, "payout_channel": self.payout_channel,
            "payout_channel_name": self.payout_channel_name,
            "payout_account_ref": self.payout_account_ref,
            "requested_at": self.requested_at, "decided_at": self.decided_at,
            "decided_by": self.decided_by, "receipt_reference": self.receipt_reference,
            "receipt_content_type": self.receipt_content_type, "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WithdrawalRequest":
        return cls(
            id=str(d.get("id", "")), affiliate_id=str(d.get("affiliate_id", "")),
            amount_halalas=int(d.get("amount_halalas", 0)),
            commission_ids=[str(c) for c in (d.get("commission_ids") or [])],
            status=str(d.get("status", REQUESTED)),
            payout_channel=str(d.get("payout_channel", "")),
            payout_channel_name=str(d.get("payout_channel_name", "")),
            payout_account_ref=str(d.get("payout_account_ref", "")),
            requested_at=int(d.get("requested_at", 0)), decided_at=int(d.get("decided_at", 0)),
            decided_by=str(d.get("decided_by", "")),
            receipt_reference=str(d.get("receipt_reference", "")),
            receipt_content_type=str(d.get("receipt_content_type", "")),
            reason=str(d.get("reason", "")),
        )


# ── «برنامج دعم الوفاء» — spec §8's optional monthly stipend (Tamam, 2026-08-20) ────────────────
#: NOT a commission — RENEWAL was retired for exactly this reason (see commission.py's own note).
#: A recurring monthly amount for a marketer who keeps SERVICING the shops he brought, gated by a
#: real measurable performance check, never by shop count alone.
WAFA_REQUESTS = "affiliate_wafa_requests"

WAFA_REQUESTED = "requested"
WAFA_GRANTED = "granted"
WAFA_REJECTED = "rejected"
WAFA_STATUSES = (WAFA_REQUESTED, WAFA_GRANTED, WAFA_REJECTED)

WAFA_APPROVE = "approve"
WAFA_REJECT = "reject"
WAFA_DECISIONS = (WAFA_APPROVE, WAFA_REJECT)


@dataclass
class WafaRequest:
    id: str
    affiliate_id: str
    #: The shop count AT REQUEST TIME — locked, same "never re-read from a moving number later"
    #: rule as everywhere else in this service. tier_amount_halalas is derived from this and
    #: equally locked: a config change next month must not silently rewrite what this request
    #: asked for.
    active_shops: int = 0
    tier_amount_halalas: int = 0
    status: str = WAFA_REQUESTED
    requested_at: int = 0
    #: THE SYSTEM'S OWN RECOMMENDATION, computed once from real measurable data (WafaService.
    #: performance_for) at the moment of request — never re-derived later, same locked-snapshot
    #: reasoning as active_shops. Shown to BOTH the manager and the admin so neither decides
    #: blind; binds neither.
    system_recommendation: str = ""
    system_retention_rate: float = 0.0
    system_refund_rate: float = 0.0
    #: THE MANAGER'S OWN CALL — advisory, never binding (see core/wafa.py's module docstring on
    #: why the platform keeps the final word). Blank means "not yet reviewed".
    manager_decision: str = ""
    manager_decided_by: str = ""
    manager_decided_at: int = 0
    manager_reason: str = ""
    #: THE PLATFORM'S BINDING DECISION.
    decided_by: str = ""
    decided_at: int = 0
    reason: str = ""
    #: Set ONLY on a GRANTED decision, and to `requested_at` — NEVER `now` (core/wafa.py's own
    #: module docstring: the admin's review speed must have zero effect on the marketer's next
    #: eligible date, or a slow review compounds into an ever-later cycle instead of a stable
    #: monthly one).
    granted_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "affiliate_id": self.affiliate_id, "active_shops": self.active_shops,
            "tier_amount_halalas": self.tier_amount_halalas, "status": self.status,
            "requested_at": self.requested_at,
            "system_recommendation": self.system_recommendation,
            "system_retention_rate": self.system_retention_rate,
            "system_refund_rate": self.system_refund_rate,
            "manager_decision": self.manager_decision,
            "manager_decided_by": self.manager_decided_by,
            "manager_decided_at": self.manager_decided_at,
            "manager_reason": self.manager_reason,
            "decided_by": self.decided_by, "decided_at": self.decided_at, "reason": self.reason,
            "granted_at": self.granted_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WafaRequest":
        return cls(
            id=str(d.get("id", "")), affiliate_id=str(d.get("affiliate_id", "")),
            active_shops=int(d.get("active_shops", 0)),
            tier_amount_halalas=int(d.get("tier_amount_halalas", 0)),
            status=str(d.get("status", WAFA_REQUESTED)), requested_at=int(d.get("requested_at", 0)),
            system_recommendation=str(d.get("system_recommendation", "")),
            system_retention_rate=float(d.get("system_retention_rate", 0.0)),
            system_refund_rate=float(d.get("system_refund_rate", 0.0)),
            manager_decision=str(d.get("manager_decision", "")),
            manager_decided_by=str(d.get("manager_decided_by", "")),
            manager_decided_at=int(d.get("manager_decided_at", 0)),
            manager_reason=str(d.get("manager_reason", "")),
            decided_by=str(d.get("decided_by", "")), decided_at=int(d.get("decided_at", 0)),
            reason=str(d.get("reason", "")), granted_at=int(d.get("granted_at", 0)),
        )


# ── «رشّح نفسك لوظيفة» — spec §8's other promotion path ─────────────────────────────────────────
#: A ONE-TIME career milestone, not a recurring payment — no tier math, no cooldown (a rejected
#: marketer may simply try again once he genuinely has more converted customers; nothing here
#: punishes that). Separate from WafaRequest on purpose: "قابل للتوظيف" and "يستحق دخلاً شهرياً"
#: are two different questions with two different thresholds and two different decision-makers.
EMPLOYMENT_REQUESTS = "affiliate_employment_requests"

EMPLOYMENT_REQUESTED = "requested"
EMPLOYMENT_APPROVED = "approved"
EMPLOYMENT_REJECTED = "rejected"
EMPLOYMENT_STATUSES = (EMPLOYMENT_REQUESTED, EMPLOYMENT_APPROVED, EMPLOYMENT_REJECTED)


@dataclass
class EmploymentRequest:
    id: str
    affiliate_id: str
    #: How many of his referrals had ever actually converted (a real CONVERSION commission
    #: exists) AT REQUEST TIME — locked, same "never re-read from a moving number later" rule as
    #: WafaRequest.active_shops.
    converted_customers: int = 0
    status: str = EMPLOYMENT_REQUESTED
    requested_at: int = 0
    decided_by: str = ""
    decided_at: int = 0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "affiliate_id": self.affiliate_id,
            "converted_customers": self.converted_customers, "status": self.status,
            "requested_at": self.requested_at, "decided_by": self.decided_by,
            "decided_at": self.decided_at, "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EmploymentRequest":
        return cls(
            id=str(d.get("id", "")), affiliate_id=str(d.get("affiliate_id", "")),
            converted_customers=int(d.get("converted_customers", 0)),
            status=str(d.get("status", EMPLOYMENT_REQUESTED)),
            requested_at=int(d.get("requested_at", 0)), decided_by=str(d.get("decided_by", "")),
            decided_at=int(d.get("decided_at", 0)), reason=str(d.get("reason", "")),
        )


# ── §٦ Lead Sourcing — ported from places_scraper_v2.py, CLI→CSV turned into a resumable job
# that writes straight to this table (Tamam's own conversion plan) ─────────────────────────────
LEADS = "affiliate_leads"
LEAD_SEARCH_JOBS = "affiliate_lead_search_jobs"

LEAD_NEW = "new"
LEAD_ASSIGNED = "assigned"
LEAD_STATUSES = (LEAD_NEW, LEAD_ASSIGNED)

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_STATUSES = (JOB_QUEUED, JOB_RUNNING, JOB_COMPLETED, JOB_FAILED)


@dataclass
class Lead:
    #: The FIRST place_id found for this business — the record's own primary key. A dedup match
    #: on PHONE (not place_id) appends the new place_id to `extra_place_ids` instead of a second
    #: row — spec §6: "فرعان لنفس المحل... يُربط كفرع إضافي لنفس السجل، لا يُتجاهل بالكامل".
    id: str
    place_id: str
    phone: str = ""
    name: str = ""
    place_type: str = ""
    city: str = ""
    region: str = ""
    address: str = ""
    neighborhood: str = ""
    maps_url: str = ""
    rating: float = 0.0
    ratings_count: int = 0
    opening_hours: str = ""
    website: str = ""
    lat: float = 0.0
    lng: float = 0.0
    #: Additional Google place_ids that share this SAME phone number — other branches of the
    #: same business, not separate leads. See the `id` field's own note.
    extra_place_ids: list[str] = field(default_factory=list)
    #: WHO found it — the manager whose search (and whose own Google API key/quota) surfaced
    #: this lead first. Never rewritten by a later manager's duplicate search.
    source_manager_id: str = ""
    #: WHO it is handed to — a promoter on the finding manager's own team (spec §6's own "الإسناد").
    #: Blank means unassigned; only the finding manager may assign (see core/lead_sourcing.py).
    assigned_to: str = ""
    status: str = LEAD_NEW
    found_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "place_id": self.place_id, "phone": self.phone, "name": self.name,
            "place_type": self.place_type, "city": self.city, "region": self.region,
            "address": self.address, "neighborhood": self.neighborhood, "maps_url": self.maps_url,
            "rating": self.rating, "ratings_count": self.ratings_count,
            "opening_hours": self.opening_hours, "website": self.website,
            "lat": self.lat, "lng": self.lng, "extra_place_ids": list(self.extra_place_ids),
            "source_manager_id": self.source_manager_id, "assigned_to": self.assigned_to,
            "status": self.status, "found_at": self.found_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Lead":
        return cls(
            id=str(d.get("id", "")), place_id=str(d.get("place_id", "")),
            phone=str(d.get("phone", "")), name=str(d.get("name", "")),
            place_type=str(d.get("place_type", "")), city=str(d.get("city", "")),
            region=str(d.get("region", "")), address=str(d.get("address", "")),
            neighborhood=str(d.get("neighborhood", "")), maps_url=str(d.get("maps_url", "")),
            rating=float(d.get("rating", 0.0) or 0.0),
            ratings_count=int(d.get("ratings_count", 0) or 0),
            opening_hours=str(d.get("opening_hours", "")), website=str(d.get("website", "")),
            lat=float(d.get("lat", 0.0) or 0.0), lng=float(d.get("lng", 0.0) or 0.0),
            extra_place_ids=[str(p) for p in (d.get("extra_place_ids") or [])],
            source_manager_id=str(d.get("source_manager_id", "")),
            assigned_to=str(d.get("assigned_to", "")),
            status=str(d.get("status", LEAD_NEW)), found_at=int(d.get("found_at", 0)),
        )


@dataclass
class LeadSearchJob:
    """A whole grid×keyword search, real-world runtime measured in HOURS (places_scraper_v2.py's
    own cost estimate: 3–5h for 10 cities) — never one request/response. `cursor` is where a
    bounded internal tick (POST /internal/leads/tick) resumes, same "capped sweep records where
    it stopped" shape as commissions/sweep."""
    id: str
    affiliate_id: str
    place_type: str = ""
    keywords: list[str] = field(default_factory=list)
    radius_km: float = 5.0
    #: Locked geo inputs — spec §12: the service stays generic, so a fixed Saudi-city table lives
    #: in the CALLER (the console's own picker), never hardcoded here. Each: {name, region, lat,
    #: lng, w_km, h_km}.
    cities: list[dict[str, Any]] = field(default_factory=list)
    apply_filter: bool = False
    filter_indicators: list[str] = field(default_factory=list)
    status: str = JOB_QUEUED
    #: {"city": i, "point": i, "keyword": i} — the next unit of work. Advances one (point,
    #: keyword) pair per unit; a city boundary resets point/keyword to 0.
    cursor: dict[str, int] = field(default_factory=lambda: {"city": 0, "point": 0, "keyword": 0})
    found_count: int = 0
    duplicate_count: int = 0
    created_at: int = 0
    started_at: int = 0
    finished_at: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "affiliate_id": self.affiliate_id, "place_type": self.place_type,
            "keywords": list(self.keywords), "radius_km": self.radius_km,
            "cities": list(self.cities), "apply_filter": self.apply_filter,
            "filter_indicators": list(self.filter_indicators), "status": self.status,
            "cursor": dict(self.cursor), "found_count": self.found_count,
            "duplicate_count": self.duplicate_count, "created_at": self.created_at,
            "started_at": self.started_at, "finished_at": self.finished_at, "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LeadSearchJob":
        return cls(
            id=str(d.get("id", "")), affiliate_id=str(d.get("affiliate_id", "")),
            place_type=str(d.get("place_type", "")),
            keywords=[str(k) for k in (d.get("keywords") or [])],
            radius_km=float(d.get("radius_km", 5.0) or 5.0),
            cities=list(d.get("cities") or []), apply_filter=bool(d.get("apply_filter", False)),
            filter_indicators=[str(i) for i in (d.get("filter_indicators") or [])],
            status=str(d.get("status", JOB_QUEUED)),
            cursor=dict(d.get("cursor") or {"city": 0, "point": 0, "keyword": 0}),
            found_count=int(d.get("found_count", 0)), duplicate_count=int(d.get("duplicate_count", 0)),
            created_at=int(d.get("created_at", 0)), started_at=int(d.get("started_at", 0)),
            finished_at=int(d.get("finished_at", 0)), error=str(d.get("error", "")),
        )
