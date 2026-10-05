"""Mutual benefit — a customer who meets a condition at shop A becomes automatically
eligible for a discount at shop B, detected automatically, no proof the customer must carry.

See docs/خطة-شراكة-استراتيجية-الإحالة.md for the full design this module implements. NOT the same
feature as `core/coupons.py` («ولاء الشركاء») — that one discounts a shop's OWN subscription with
us, through billing-service, unilaterally. This one discounts nothing of ours.

A DISCOUNT GRANT'S VALUE IS MANDATORY AND STORED (owner's own correction, 2026-10-04 — a customer's
own right must be a real, visible number, never a silent "whatever shop_b feels like that day",
which read as shop_b being free to hand a customer 0% while still showing "eligible"). For
`GRANT_DISCOUNT` (every scope), `discount_kind`/`discount_amount` are REQUIRED at `propose()` time —
same two-field shape `campaigns`' own `reward_kind`/`reward_amount` already uses (`"percent"` or
`"fixed_halalas"`), so the same money-safety rules apply (never a float, a percent capped at 100).
We still never APPLY the number ourselves — shop_b's own till still does the real reduction by hand
— but the number is no longer invisible: it is copied onto the grant, shown verbatim on shop_b's
own redemption screen (`public_for_beneficiary()`), and on both parties' agreement screens, so a
customer's entitlement is a concrete, checkable fact rather than a promise with no number attached.
`GRANT_GIFT` has no value field — a named free service IS the whole value, nothing to misstate.

THE ONE REAL INTEGRATION POINT — `Operations.record_visit()` (core/operations.py), verified by
reading that method, not assumed. Every real "customer did something that counts" event funnels
through it: the manual visit screen calls it directly, `core/mobile_requests.py` calls it directly
(same service, same process), and `bookings` — a SEPARATE service — is architecturally forbidden
from writing a Visit row itself (see `services/bookings/app/adapters/visit_gateway/http.py`'s own
docstring: "NEVER a direct write to a Visit row from this service") and instead calls THIS service's
own `POST /internal/operations/visits/from-customer`, which itself calls `record_visit()`. So hooking
`on_visit_recorded()` into `record_visit()` itself — once — covers every current and future channel
(any app, any external integration) with zero changes anywhere else, exactly the design doc's own
claim, now enforced in code rather than merely stated.

NEVER BLOCKS A VISIT. `on_visit_recorded` is called from `record_visit()` wrapped in a broad
try/except at the call site — a bug in this engine must never cost a shop the customer visit itself,
which is the one fact this whole product cannot survive losing (see `Operations.record_visit`'s own
long note on why an unknown service is absorbed rather than refused; the same principle applies here
with even less room to argue: this engine's failure is not even about THIS visit's own data).

TENANT ISOLATION — SAME KEY-PREFIX DISCIPLINE AS `coupons.py`. An agreement or grant is a fact about
TWO tenants, owned by neither alone, so rows live under the reserved `_platform` prefix (same
registry `coupons.py`/`partners.py` already use) rather than either tenant's own namespace — and
every read that serves an API caller is filtered in Python against `shop_a`/`shop_b` before it is
ever returned, so a third tenant's `find()` (scoped to ITS OWN tenant id) can never even match these
rows in the first place, and a caller who somehow knows another pair's agreement id still gets
refused by `_agreement_for` unless its own tenant is a party to it.

PRIVACY AT REDEMPTION — shop B's own visit/redemption screen is told only "eligible for X until Y",
never shop A's name (`MutualBenefitGrant.public_for_beneficiary()`). The granting shop's name is kept on
the row for the two parties' OWN agreement screens (they already know each other — they approved the
partnership by name) and for any future settlement report between them; it is simply never handed to
the beneficiary's OWN redemption flow, which only needs "does this phone qualify, and for what".

AN ALREADY-EARNED GRANT ALWAYS HONOURS ITS OWN EXPIRY, REGARDLESS OF WHY THE PARENT AGREEMENT
STOPPED (design doc's own explicit rule) — `MutualBenefitGrant.expires_at` is copied at CREATION time from
the agreement's `grant_validity_days` and never again consulted against the agreement's own state.
`redeem()` checks only the grant's own `expires_at`, never the agreement.

MUTUAL CONSENT FOR EARLY CANCELLATION, SAME MECHANISM AS CREATION — a `cancel_request` needs the
other side's own `cancel_confirm` before the agreement actually ends; the ONE exception is a
subscription pausing, which is immediate and unilateral by nature (a shop that stopped paying cannot
be asked to "agree" to anything).

THE CONCURRENCY CAP — `MAX_CONCURRENT_PARTNERSHIPS` (owner's own requirement). A shop may hold at
most that many ACTIVE agreements AT ANY POINT IN TIME, in EITHER role (`shop_a` and `shop_b` count
together — a shop that is `shop_a` in two and `shop_b` in one is already at three). This is a
TIME-RANGE check, not a point-in-time count: `_would_exceed_cap` walks a sweep-line over every
[start, end) interval a candidate would sit among (see that method's own docstring for the exact
half-open boundary rule), so a shop already at the cap right now can still propose — and later
accept — a new agreement whose own interval starts only after one of the existing three has
actually ended. Checked at `propose()` (an early, TENTATIVE refusal — the real interval is not
committed until `accept()`, so this only spares a proposal that would obviously never be
acceptable) and, authoritatively, at `accept()` itself, which is the one moment an interval is
truly reserved. A RENEWAL IS NOT A SEPARATE MECHANISM — the design doc's own rule is that a lapsed
agreement needs an explicit fresh propose/accept from both sides (no silent auto-renew), so a
renewal simply walks through `propose()`/`accept()` again like any new agreement, and is governed
by the exact same cap check with no special-casing anywhere.

GRANT TYPE — NO FREE TEXT ANYWHERE, FOR EITHER KIND (owner's own correction). What a grant actually
IS, at CREATION time only, is one of:

  * GRANT_GIFT — a SPECIFIC service from the granting shop's (`shop_b`'s) OWN real catalogue.
  * GRANT_DISCOUNT, itself one of three CATALOGUE-DRIVEN scopes, never a typed note:
      - "item"    — one specific service from `shop_b`'s catalogue (same shape as a gift, just
                    discount-typed instead of handed over free).
      - "blanket" — the whole visit, explicitly ("خصم شامل") — a real, deliberate choice, never an
                    empty/missing field that could be mistaken for "nobody set this".
      - "group"   — a `Package` (this codebase's own existing "named group of a shop's OWN
                    services" concept, `core/models.py::Package` — reused rather than inventing a
                    second grouping concept) from `shop_b`'s catalogue; the discount applies to
                    that package's member services.

EVERY service/group reference is VALIDATED against the granting shop's (`shop_b`'s) OWN catalogue
at `propose()` time (`ServiceStore`/`PackageStore`, both tenant-scoped) — a redeemed grant must be
attributable to something real, for that shop's own KPIs, never an arbitrary string nobody can
reconcile. The human-readable `text` an entitlement shows (`core/entitlements.py`'s own `text`
field) is always DERIVED at the moment it is shown, from whichever real catalogue fact backs the
grant — a service's `.name`, a package's `.name`, or the fixed phrase for "blanket" — never
authored, typed, or stored as its own string on the agreement.

IMMUTABLE AFTER CREATION (owner's own explicit correction) — every one of these fields is decided
ONCE, at `propose()` time, shown in full on the agreement to both parties (`MutualBenefitAgreement.
public()` already returns every field), and NEVER CHANGES for the life of that agreement. There is
no update/patch method or route anywhere in this module or its API that can alter a grant's terms
once the agreement exists — different terms are a NEW agreement (governed by the exact same
concurrency-cap/overlap rules above), never an edit to an existing one. See
`test_mutual_benefit_cap_and_gift.py`'s own structural test proving no such code path exists.

Both kinds/scopes are copied onto `MutualBenefitGrant` at the moment each grant is created (same "copy,
never reference" discipline this module already used before this correction), so a later catalogue
edit or removal can never rewrite what an already-earned grant actually promised. Every kind/scope
stays OPAQUE to `Operations.apply_offer` / `core/entitlements.py::EntitlementGateway` — only this
module's own `eligibility()` needs to know which one it is, to derive the entitlement's `text`
correctly; the caller keeps working completely unchanged regardless of which kind/scope it got.

A FUTURE "your customer already holds an offer at [partner shop]" STAFF SCREEN AT THE GRANTING SHOP
is explicitly DEFERRED (owner's own call) — nothing here scaffolds it; when it is built, it reads
`eligibility()`/`public_for_beneficiary()`, both already shaped to answer it.
"""
from __future__ import annotations

import itertools
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.signup import PHONE_INDEX, canonical_phone
from app.core.subscribe import row_plan_id

AGREEMENTS = "mutual_benefit_agreements"
GRANTS = "mutual_benefit_grants"
AUDIT_LOG = "mutual_benefit_audit_log"
PROPOSAL_LOCKS = "mutual_benefit_proposal_locks"

# Same reserved-key registry pattern as `core/coupons.py::PLATFORM` — a fact owned by neither
# tenant, stored under a key no real tenant id can collide with.
PLATFORM = "_platform"

FEATURE_KEY = "feature.mutual_benefit"

# ── agreement lifecycle states ───────────────────────────────────────────────────────────────────
PROPOSED = "proposed"
ACTIVE = "active"
PAUSED = "paused"                 # a party's subscription lapsed — automatic, unilateral, immediate
CANCEL_REQUESTED = "cancel_requested"
ENDED = "ended"
REJECTED = "rejected"
EXPIRED_UNANSWERED = "expired_unanswered"

# A proposal nobody answers is cleaned up, not left open forever (design doc §"ضوابط إضافية" 4 and
# the edge-case list both ask for a sane expiry). Fourteen days is a generous, simple window — a
# shop on holiday still has two weeks to answer, and a real "no answer" reads as a "no" after that.
_PROPOSAL_TTL_SECONDS = 14 * 24 * 3600

# The per-period grant cap's own period — additive from each agreement's own activation, not
# calendar-aligned, same reasoning `coupons.py::_GRANT_WINDOW_SECONDS` gives for its own window.
_CAP_PERIOD_SECONDS = 30 * 24 * 3600

CONDITION_MIN_TOTAL = "min_total_minor"
CONDITION_SERVICE_ID = "service_id"
CONDITION_TYPES = (CONDITION_MIN_TOTAL, CONDITION_SERVICE_ID)

# THE ONE NAMED CONSTANT — never a bare number repeated at each call site, so the owner changing
# the cap later is a one-line edit, not a grep. See the module docstring's own "THE CONCURRENCY
# CAP" section for the full rule this bounds.
MAX_CONCURRENT_PARTNERSHIPS = 3

GRANT_DISCOUNT = "discount"
GRANT_GIFT = "gift"
GRANT_TYPES = (GRANT_DISCOUNT, GRANT_GIFT)

# THE GRANT'S OWN VALUE — mandatory for GRANT_DISCOUNT, meaningless for GRANT_GIFT (a named free
# service already fully states its own value). Same two-kind shape `campaigns` already uses for the
# identical reason (never a float, a percent capped at 100) — see module docstring's "A DISCOUNT
# GRANT'S VALUE IS MANDATORY AND STORED" section.
REWARD_PERCENT = "percent"
REWARD_FIXED_HALALAS = "fixed_halalas"
DISCOUNT_REWARD_KINDS = (REWARD_PERCENT, REWARD_FIXED_HALALAS)

# THE THREE VALID SCOPES FOR A DISCOUNT GRANT — meaningless for GRANT_GIFT, required for
# GRANT_DISCOUNT. See module docstring's own "GRANT TYPE" section.
DISCOUNT_SCOPE_ITEM = "item"
DISCOUNT_SCOPE_BLANKET = "blanket"
DISCOUNT_SCOPE_GROUP = "group"
DISCOUNT_SCOPES = (DISCOUNT_SCOPE_ITEM, DISCOUNT_SCOPE_BLANKET, DISCOUNT_SCOPE_GROUP)

# ── audit event kinds — every one of these, and only these, is ever written ─────────────────────
EV_PROPOSED = "proposed"
EV_ACCEPTED = "accepted"
EV_REJECTED = "rejected"
EV_ACTIVATED = "activated"
EV_CANCEL_REQUESTED = "cancel_requested"
EV_CANCEL_CONFIRMED = "cancel_confirmed"
EV_EXPIRED_UNANSWERED = "expired_unanswered"
EV_PAUSED = "paused"
EV_RESUMED = "resumed"
EV_ENDED_TERM = "ended_term"
EV_GRANT_CREATED = "grant_created"
EV_GRANT_REDEEMED = "grant_redeemed"
EV_GRANT_CAPPED = "grant_capped"


def _now() -> int:
    return int(time.time())


def uuid_hex() -> str:
    return uuid.uuid4().hex


class MutualBenefitError(Exception):
    """A refusal an API route can show verbatim to the caller."""


SELF_PARTNER = "self_partner"
NOT_SUBSCRIBED = "not_subscribed"
NOT_FOUND = "not_found"
FORBIDDEN = "forbidden"
BAD_CONDITION = "bad_condition"
WRONG_STATE = "wrong_state"
BILLING_UNAVAILABLE = "billing_unavailable"
# «تجاوز الحد الأقصى للشراكات النشطة» — the owner's own exact wording for the API to show.
OVER_CONCURRENCY_CAP = "over_concurrency_cap"
# A referenced service (gift, or discount scope "item") does not exist, is inactive, or belongs
# to a DIFFERENT tenant than the granting shop — all three read as this one refusal, on purpose
# (an IDOR probe must not learn WHICH of the three is true).
CATALOG_ITEM_NOT_FOUND = "catalog_item_not_found"
# A referenced Package (discount scope "group") — same three-way refusal, for the group case.
CATALOG_GROUP_NOT_FOUND = "catalog_group_not_found"


@dataclass
class MutualBenefitAgreement:
    id: str
    shop_a: str                    # the referring shop — where the condition is met
    shop_b: str                    # the beneficiary shop — where the discount is offered
    condition_type: str
    condition_value: str           # halalas as a string for min_total_minor, else a service id
    grant_validity_days: int       # how long ONE customer's own eligibility lasts
    agreement_duration_days: int   # how long the AGREEMENT itself lasts
    per_period_cap: int            # 0 = unlimited grants per rolling 30-day period
    created_by: str                # tenant that proposed it (always shop_a today — see propose())
    created_by_operator: str
    created: int
    status: str = PROPOSED
    proposal_expires_at: int = 0
    started_at: int = 0
    ends_at: int = 0
    # THE ORIGINAL TERM, NEVER MOVED. A pause-then-resume-before-expiry continues to this exact
    # timestamp (design doc: "لا تمديد، لا خسارة للمدة المتبقية"); resuming AFTER it requires an
    # explicit fresh agreement, never a silent extension.
    original_ends_at: int = 0
    paused_at: int = 0
    cancel_requested_by: str = ""
    idempotency_key: str = ""
    # THE GRANT'S OWN TERMS — DECIDED ONCE, AT PROPOSE() TIME, IMMUTABLE FOR THE LIFE OF THIS
    # AGREEMENT (owner's own explicit correction — see module docstring's "GRANT TYPE" section in
    # full for the no-free-text rule and every field's exact meaning per kind/scope). No method
    # anywhere in this module ever assigns to any of these eight fields after `propose()` creates
    # the row — different terms are a NEW agreement, never an edit to this one.
    grant_type: str = GRANT_DISCOUNT
    # GRANT_GIFT, or GRANT_DISCOUNT scope "item": one real service from shop_b's own catalogue.
    gift_service_id: str = ""
    gift_service_name: str = ""
    # GRANT_DISCOUNT ONLY — which of the three scopes, and (for "item"/"group") which real
    # catalogue reference backs it. "" scope on a GRANT_GIFT row is meaningless and never read.
    discount_scope: str = ""
    discount_group_id: str = ""
    discount_group_name: str = ""
    # MANDATORY FOR GRANT_DISCOUNT, "" / 0 ON A GRANT_GIFT ROW (never read there) — see module
    # docstring's "A DISCOUNT GRANT'S VALUE IS MANDATORY AND STORED" section.
    discount_kind: str = ""
    discount_amount: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MutualBenefitGrant:
    id: str
    agreement_id: str
    shop_a: str
    shop_b: str
    customer_phone: str
    triggering_visit_id: str
    created: int
    expires_at: int
    redeemed_at: int = 0
    redeemed_visit_id: str = ""
    # COPIED FROM THE AGREEMENT AT GRANT-CREATION TIME, NEVER REFERENCED LATER — same "copy, not
    # reference" discipline this product already uses elsewhere (e.g. `CouponGrant`'s own copied
    # text), so a later catalogue edit (a service renamed/retired, a package changed) can never
    # rewrite what an already-earned grant actually promised this customer. Same eight fields as
    # `MutualBenefitAgreement`'s own immutable terms — see that dataclass's own docstring.
    grant_type: str = GRANT_DISCOUNT
    gift_service_id: str = ""
    gift_service_name: str = ""
    discount_scope: str = ""
    discount_group_id: str = ""
    discount_group_name: str = ""
    discount_kind: str = ""
    discount_amount: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)

    def public_for_beneficiary(self) -> dict[str, Any]:
        """`shop B`'s OWN redemption screen never sees shop A's identity (design doc's privacy
        rule) — only that this phone is eligible, until when, and exactly WHAT it is eligible
        for, derived from the real catalogue fact backing the grant (a gift/item names the real
        service; a group names the real package; a blanket discount just says so)."""
        out: dict[str, Any] = {"eligible": True, "expires_at": self.expires_at,
                               "redeemed": bool(self.redeemed_at), "grant_type": self.grant_type}
        if self.grant_type == GRANT_GIFT:
            out["gift_service_id"] = self.gift_service_id
            out["gift_service_name"] = self.gift_service_name
        else:
            out["discount_scope"] = self.discount_scope
            out["discount_kind"] = self.discount_kind
            out["discount_amount"] = self.discount_amount
            if self.discount_scope == DISCOUNT_SCOPE_ITEM:
                out["gift_service_id"] = self.gift_service_id
                out["gift_service_name"] = self.gift_service_name
            elif self.discount_scope == DISCOUNT_SCOPE_GROUP:
                out["discount_group_id"] = self.discount_group_id
                out["discount_group_name"] = self.discount_group_name
        return out


@dataclass
class MutualBenefitAuditEntry:
    id: str
    agreement_id: str
    event: str
    actor_tenant: str
    detail: dict[str, Any]
    created: int
    # A HIGH-RESOLUTION WRITE ORDER, SEPARATE FROM `created`. Two transitions in the same lifecycle
    # call (e.g. `accept()`'s own "accepted" then "activated") can land in the same wall-clock
    # SECOND, and `DataStore.find`'s own tie-break is by ROW ID (arbitrary uuids here), not
    # insertion order — so `created` alone cannot reproduce "every transition, in the order it
    # truly happened". `time.time_ns()` alone was tried first and FAILED IN PRACTICE (found live):
    # two `_audit()` calls back-to-back with no real I/O between them (`accept()`'s own "accepted"
    # then "activated") can land on the SAME OS clock tick — Windows' `time_ns()` resolution is far
    # coarser than a nanosecond in practice — and the id tie-break above is a random uuid, so a
    # collision scrambles the two entries' order. `_SEQ.next()` folded into the low bits below
    # breaks that tie deterministically, in true call order, while the time bits still dominate the
    # value — so cross-pod entries for the same agreement still land in roughly wall-clock order,
    # which is all a counter reset per pod could never give on its own.
    seq: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


# Module-level, not per-engine-instance — the collision this exists for is call-to-call within one
# process regardless of which agreement or engine object is involved, so one counter shared by the
# whole process is what actually closes the window; `next()` on an `itertools.count()` is a single
# C-level op and stays GIL-atomic for this purpose. Masked to 20 bits (kept well under time_ns()'s
# own least-significant bits) so it can never overflow into, and corrupt, the time component.
_SEQ = itertools.count()
_SEQ_MASK = (1 << 20) - 1


def _next_seq() -> int:
    return (time.time_ns() << 20) | (next(_SEQ) & _SEQ_MASK)


class MutualBenefitEngine:
    """Everything the propose/accept/reject/cancel lifecycle, the `record_visit()` hook, and each
    shop's own KPI screen need. `plans` is the same peer `CouponService` takes — `plan_id_for_key`/
    `subscriptions` — used identically here for the feature-gate and the pause/resume check."""

    def __init__(self, *, store, plans: Any, notifier: Any = None, authz: Any = None,
                default_cc: str) -> None:
        self._s = store
        self._plans = plans
        self._notifier = notifier
        self._authz = authz
        self._cc = default_cc

    # ── the immutable audit log — append-only, by construction: this method is the ONLY writer,
    # and it never reuses an id, so there is no key any later call could `put` over. ─────────────
    async def _audit(self, agreement_id: str, event: str, *, actor_tenant: str,
                     detail: dict[str, Any] | None = None) -> None:
        entry = MutualBenefitAuditEntry(id=f"rpaud_{uuid_hex()}", agreement_id=agreement_id,
                                   event=event, actor_tenant=actor_tenant,
                                   detail=detail or {}, created=_now(), seq=_next_seq())
        await self._s.put(AUDIT_LOG, f"{PLATFORM}|{entry.id}", {"tenant": PLATFORM, **asdict(entry)})

    async def audit_log(self, tenant: str, agreement_id: str, limit: int = 200
                        ) -> list[MutualBenefitAuditEntry]:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise MutualBenefitError(NOT_FOUND)
        rows, _ = await self._s.find(
            AUDIT_LOG, {"tenant": PLATFORM, "agreement_id": agreement_id},
            limit=limit, sort=("seq", "asc"))
        return [MutualBenefitAuditEntry(**{k: v for k, v in r.items() if k != "tenant"}) for r in rows]

    # ── subscription gate — same shape as `CouponService.granter_is_subscribed` ────────────────
    async def _is_subscribed(self, tenant: str) -> bool | None:
        plan_id = await self._plans.plan_id_for_key(FEATURE_KEY)
        if not plan_id:
            return False
        subs = await self._plans.subscriptions(tenant)
        if subs is None:
            return None
        return any(row_plan_id(s) == plan_id
                  and str(s.get("status") or "") in ("active", "trialing") for s in subs)

    async def _lookup_tenant_by_phone(self, phone: str) -> str:
        row = await self._s.get(PHONE_INDEX, canonical_phone(phone, default_cc=self._cc))
        return str((row or {}).get("tenant") or "")

    # ── reads, always tenant-scoped ──────────────────────────────────────────────────────────────
    async def _agreement_row(self, agreement_id: str) -> dict[str, Any] | None:
        return await self._s.get(AGREEMENTS, f"{PLATFORM}|{agreement_id}")

    async def _agreement_for(self, tenant: str, agreement_id: str) -> MutualBenefitAgreement | None:
        """`None` for an id that does not exist AND for one that exists but belongs to two OTHER
        tenants — the two are indistinguishable to the caller, on purpose (an IDOR probe must learn
        nothing from the difference)."""
        row = await self._agreement_row(agreement_id)
        if row is None:
            return None
        if row.get("shop_a") != tenant and row.get("shop_b") != tenant:
            return None
        return MutualBenefitAgreement(**{k: v for k, v in row.items() if k != "tenant"})

    async def get(self, tenant: str, agreement_id: str) -> MutualBenefitAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise MutualBenefitError(NOT_FOUND)
        return await self._synced(agreement)

    async def agreements_for(self, tenant: str, limit: int = 200) -> list[MutualBenefitAgreement]:
        as_a, _ = await self._s.find(AGREEMENTS, {"tenant": PLATFORM, "shop_a": tenant},
                                     limit=limit, sort=("created", "desc"))
        as_b, _ = await self._s.find(AGREEMENTS, {"tenant": PLATFORM, "shop_b": tenant},
                                     limit=limit, sort=("created", "desc"))
        seen: set[str] = set()
        out: list[MutualBenefitAgreement] = []
        for row in list(as_a) + list(as_b):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            agreement = MutualBenefitAgreement(**{k: v for k, v in row.items() if k != "tenant"})
            out.append(await self._synced(agreement))
        out.sort(key=lambda a: a.created, reverse=True)
        return out[:limit]

    async def _save_agreement(self, agreement: MutualBenefitAgreement) -> None:
        await self._s.put(AGREEMENTS, f"{PLATFORM}|{agreement.id}",
                          {"tenant": PLATFORM, **asdict(agreement)})

    # ── lazy subscription pause/resume — consulted on every read/hook touch, never a cron ───────
    async def _synced(self, agreement: MutualBenefitAgreement) -> MutualBenefitAgreement:
        now = _now()
        if (agreement.status == PROPOSED and agreement.proposal_expires_at
                and now > agreement.proposal_expires_at):
            agreement.status = EXPIRED_UNANSWERED
            await self._save_agreement(agreement)
            await self._audit(agreement.id, EV_EXPIRED_UNANSWERED, actor_tenant=PLATFORM)
            return agreement
        if agreement.status not in (ACTIVE, PAUSED):
            return agreement
        a_ok = await self._is_subscribed(agreement.shop_a)
        b_ok = await self._is_subscribed(agreement.shop_b)
        # `None` (billing unreachable) is NEVER treated as "not subscribed" — a hiccup must not
        # pause a real, paying partnership. Only a definite `False` pauses it.
        both_ok = (a_ok is not False) and (b_ok is not False)
        if agreement.status == ACTIVE and not both_ok:
            agreement.status = PAUSED
            agreement.paused_at = now
            await self._save_agreement(agreement)
            await self._audit(agreement.id, EV_PAUSED, actor_tenant=PLATFORM)
        elif agreement.status == PAUSED and both_ok:
            if now <= agreement.original_ends_at:
                agreement.status = ACTIVE
                agreement.ends_at = agreement.original_ends_at
                agreement.paused_at = 0
                await self._save_agreement(agreement)
                await self._audit(agreement.id, EV_RESUMED, actor_tenant=PLATFORM)
            else:
                agreement.status = ENDED
                await self._save_agreement(agreement)
                await self._audit(agreement.id, EV_ENDED_TERM, actor_tenant=PLATFORM,
                                  detail={"reason": "resumed_after_original_term"})
        elif agreement.status == ACTIVE and now > agreement.ends_at:
            agreement.status = ENDED
            await self._save_agreement(agreement)
            await self._audit(agreement.id, EV_ENDED_TERM, actor_tenant=PLATFORM)
        return agreement

    # ── the concurrency cap — a time-range check, not a raw count ──────────────────────────────
    @staticmethod
    def _max_concurrent(intervals: list[tuple[int, int]]) -> int:
        """The maximum number of `[start, end)` intervals ever simultaneously open, over the
        whole set — a sweep-line, not a pairwise overlap count (which would answer a different,
        more expensive question for no benefit here: we only ever need the PEAK).

        HALF-OPEN, END EXCLUSIVE — THE DECIDED, DOCUMENTED BOUNDARY RULE. An agreement ending at
        timestamp X and one starting at timestamp X do NOT overlap: at the instant X, the first
        has already ended and the second has just begun, never both live at once. Implemented by
        sorting `(time, delta)` pairs ascending — `-1` (an end) sorts before `+1` (a start) at an
        EQUAL timestamp, so an end event is always applied before a start event landing on the
        exact same instant, which is what makes touching endpoints not count as simultaneous.
        """
        events: list[tuple[int, int]] = []
        for start, end in intervals:
            events.append((start, 1))
            events.append((end, -1))
        events.sort()
        current = 0
        peak = 0
        for _, delta in events:
            current += delta
            peak = max(peak, current)
        return peak

    async def _active_intervals(self, tenant: str) -> list[tuple[int, int]]:
        """Every ACTIVE agreement's real `[started_at, ends_at)` where `tenant` holds EITHER role
        — the cap counts both roles together, per the owner's own requirement. Only ACTIVE counts
        (not PROPOSED, which reserves nothing yet — see `propose()`'s own note on why its check is
        only a tentative courtesy; and not PAUSED/CANCEL_REQUESTED, which occupy a slot that was
        already reserved at the ORIGINAL `accept()` and so need no second reservation now)."""
        as_a, _ = await self._s.find(AGREEMENTS, {"tenant": PLATFORM, "shop_a": tenant,
                                                   "status": ACTIVE}, limit=1000)
        as_b, _ = await self._s.find(AGREEMENTS, {"tenant": PLATFORM, "shop_b": tenant,
                                                   "status": ACTIVE}, limit=1000)
        seen: set[str] = set()
        out: list[tuple[int, int]] = []
        for row in list(as_a) + list(as_b):
            rid = str(row.get("id") or "")
            if rid in seen:
                continue
            seen.add(rid)
            out.append((int(row.get("started_at") or 0), int(row.get("ends_at") or 0)))
        return out

    async def _would_exceed_cap(self, tenant: str, candidate_start: int,
                                candidate_end: int) -> bool:
        intervals = await self._active_intervals(tenant)
        intervals.append((candidate_start, candidate_end))
        return self._max_concurrent(intervals) > MAX_CONCURRENT_PARTNERSHIPS

    async def _resolve_catalog_service(self, tenant: str, service_id: str) -> "Any":
        """One real, ACTIVE service from `tenant`'s OWN catalogue, or `None`. Used identically for
        a GRANT_GIFT and for a GRANT_DISCOUNT scope "item" — the same real-catalogue requirement,
        just a different label on what happens to the customer."""
        from app.core.stores import ServiceStore

        service = await ServiceStore(self._s).get(tenant, service_id)
        return service if service is not None and service.active else None

    async def _resolve_catalog_group(self, tenant: str, group_id: str) -> "Any":
        """One real, ACTIVE `Package` — this codebase's own existing "named group of a shop's OWN
        services" concept (`core/models.py::Package`), reused here rather than inventing a second
        grouping concept, for GRANT_DISCOUNT scope "group"."""
        from app.core.stores import PackageStore

        package = await PackageStore(self._s).get(tenant, group_id)
        return package if package is not None and package.active else None

    # ── the act itself ──────────────────────────────────────────────────────────────────────────
    async def propose(self, *, shop_a: str, shop_b_phone: str, operator_id: str,
                      condition_type: str, condition_value: str,
                      grant_validity_days: int, agreement_duration_days: int,
                      per_period_cap: int = 0, idempotency_key: str = "",
                      grant_type: str = GRANT_DISCOUNT,
                      gift_service_id: str = "",
                      # DEFAULTS TO BLANKET, NOT EMPTY — "" is never a valid stored scope (module
                      # docstring: an explicit "all" scope, never a field that reads as unset); a
                      # caller who does not care about scope at all still gets one deliberate,
                      # concrete value, the same way `grant_type` already defaults to a real kind
                      # rather than nothing.
                      discount_scope: str = DISCOUNT_SCOPE_BLANKET,
                      discount_group_id: str = "",
                      discount_kind: str = "",
                      discount_amount: int = 0) -> MutualBenefitAgreement:
        if condition_type not in CONDITION_TYPES:
            raise MutualBenefitError(BAD_CONDITION)
        if condition_type == CONDITION_MIN_TOTAL:
            try:
                if int(condition_value) <= 0:
                    raise MutualBenefitError(BAD_CONDITION)
            except (TypeError, ValueError):
                raise MutualBenefitError(BAD_CONDITION) from None
        elif not str(condition_value).strip():
            raise MutualBenefitError(BAD_CONDITION)
        if not (0 < grant_validity_days <= 365):
            raise MutualBenefitError(BAD_CONDITION)
        if not (0 < agreement_duration_days <= 3650):
            raise MutualBenefitError(BAD_CONDITION)
        if per_period_cap < 0:
            raise MutualBenefitError(BAD_CONDITION)

        subscribed = await self._is_subscribed(shop_a)
        if subscribed is None:
            raise MutualBenefitError(BILLING_UNAVAILABLE)
        if not subscribed:
            raise MutualBenefitError(NOT_SUBSCRIBED)

        shop_b = await self._lookup_tenant_by_phone(shop_b_phone)
        if not shop_b:
            raise MutualBenefitError(NOT_FOUND)
        if shop_b == shop_a:
            raise MutualBenefitError(SELF_PARTNER)

        # THE GRANT ITSELF — NO FREE TEXT ANYWHERE (owner's own correction). Every reference is
        # validated against shop_b's OWN catalogue right here, never trusted as typed; `shop_b`
        # was only just resolved above, which is why this could not happen any earlier. Decided
        # ONCE, here, and never again — see `MutualBenefitAgreement`'s own docstring on immutability.
        if grant_type not in GRANT_TYPES:
            raise MutualBenefitError(BAD_CONDITION)
        gift_service_name = ""
        discount_group_name = ""
        if grant_type == GRANT_GIFT:
            if not gift_service_id.strip():
                raise MutualBenefitError(BAD_CONDITION)
            service = await self._resolve_catalog_service(shop_b, gift_service_id)
            if service is None:
                raise MutualBenefitError(CATALOG_ITEM_NOT_FOUND)
            gift_service_name = service.name
            discount_scope = ""
            discount_group_id = ""
            discount_kind = ""
            discount_amount = 0
        else:
            # MANDATORY — a discount grant with no stored value is exactly the gap this field
            # exists to close (module docstring's own 2026-10-04 correction). Same bounds
            # `campaigns` already enforces for the identical reason.
            if discount_kind not in DISCOUNT_REWARD_KINDS:
                raise MutualBenefitError(BAD_CONDITION)
            if discount_amount <= 0:
                raise MutualBenefitError(BAD_CONDITION)
            if discount_kind == REWARD_PERCENT and discount_amount > 100:
                raise MutualBenefitError(BAD_CONDITION)
            if discount_scope not in DISCOUNT_SCOPES:
                raise MutualBenefitError(BAD_CONDITION)
            if discount_scope == DISCOUNT_SCOPE_ITEM:
                if not gift_service_id.strip():
                    raise MutualBenefitError(BAD_CONDITION)
                service = await self._resolve_catalog_service(shop_b, gift_service_id)
                if service is None:
                    raise MutualBenefitError(CATALOG_ITEM_NOT_FOUND)
                gift_service_name = service.name
                discount_group_id = ""
            elif discount_scope == DISCOUNT_SCOPE_GROUP:
                if not discount_group_id.strip():
                    raise MutualBenefitError(BAD_CONDITION)
                package = await self._resolve_catalog_group(shop_b, discount_group_id)
                if package is None:
                    raise MutualBenefitError(CATALOG_GROUP_NOT_FOUND)
                discount_group_name = package.name
                gift_service_id = ""
            else:                                                   # DISCOUNT_SCOPE_BLANKET
                gift_service_id = ""
                discount_group_id = ""

        if idempotency_key:
            rows, _ = await self._s.find(
                AGREEMENTS, {"tenant": PLATFORM, "shop_a": shop_a, "idempotency_key": idempotency_key},
                limit=1)
            if rows:
                return await self._synced(
                    MutualBenefitAgreement(**{k: v for k, v in rows[0].items() if k != "tenant"}))

        # ATOMIC "IS THERE ALREADY A LIVE PROPOSAL BETWEEN THIS EXACT PAIR" — `store.claim` is the
        # one operation that can make the check-then-act one statement (see `DataStore.claim`'s own
        # docstring): two concurrent proposals for the same (shop_a, shop_b) pair must converge on
        # ONE agreement, never create two.
        lock_key = f"{shop_a}|{shop_b}"
        took = await self._s.claim(PROPOSAL_LOCKS, f"{PLATFORM}|{lock_key}", {"tenant": PLATFORM},
                                   ttl_seconds=10.0, now=time.time())
        if not took:
            # Somebody else's propose() is mid-flight for this exact pair right now — the honest
            # answer is "try again", not a silent duplicate.
            raise MutualBenefitError(WRONG_STATE)
        try:
            existing, _ = await self._s.find(
                AGREEMENTS, {"tenant": PLATFORM, "shop_a": shop_a, "shop_b": shop_b}, limit=200)
            candidates = [r for r in existing if r.get("status") in (PROPOSED, ACTIVE, PAUSED,
                                                                      CANCEL_REQUESTED)]
            # SYNCED BEFORE THE DECISION, NOT AFTER — a row whose stored status still literally
            # says "active" but whose real `ends_at` has already passed (nobody has READ it since,
            # so `_synced` never ran) must be recognised as genuinely over HERE, or a legitimate
            # renewal would be handed back the dead row instead of a fresh proposal. Reading it via
            # `_synced` is exactly what a human proposing a renewal would see first on their own
            # agreements screen — this makes `propose()` see the same truth without relying on
            # that screen having been opened first.
            for row in candidates:
                synced = await self._synced(
                    MutualBenefitAgreement(**{k: v for k, v in row.items() if k != "tenant"}))
                if synced.status in (PROPOSED, ACTIVE, PAUSED, CANCEL_REQUESTED):
                    return synced

            now = _now()
            # THE TENTATIVE CAP CHECK — see module docstring's "THE CONCURRENCY CAP" section for
            # why this is a courtesy, not the authoritative gate: the real interval is not
            # reserved until `accept()` sets `started_at`/`ends_at` for real, which is where this
            # SAME check runs again, authoritatively. Using "now" as the candidate start is the
            # best available estimate at propose time — a proposal sitting unanswered for days
            # before acceptance is exactly why `accept()` must re-check with the REAL numbers.
            candidate_end = now + agreement_duration_days * 24 * 3600
            if (await self._would_exceed_cap(shop_a, now, candidate_end)
                    or await self._would_exceed_cap(shop_b, now, candidate_end)):
                raise MutualBenefitError(OVER_CONCURRENCY_CAP)

            agreement = MutualBenefitAgreement(
                id=f"rpa_{uuid_hex()}", shop_a=shop_a, shop_b=shop_b,
                condition_type=condition_type, condition_value=str(condition_value),
                grant_validity_days=grant_validity_days,
                agreement_duration_days=agreement_duration_days, per_period_cap=per_period_cap,
                created_by=shop_a, created_by_operator=operator_id, created=now,
                status=PROPOSED, proposal_expires_at=now + _PROPOSAL_TTL_SECONDS,
                idempotency_key=idempotency_key, grant_type=grant_type,
                gift_service_id=gift_service_id, gift_service_name=gift_service_name,
                discount_scope=discount_scope, discount_group_id=discount_group_id,
                discount_group_name=discount_group_name,
                discount_kind=discount_kind, discount_amount=discount_amount)
            await self._save_agreement(agreement)
            await self._audit(agreement.id, EV_PROPOSED, actor_tenant=shop_a,
                              detail={"shop_b": shop_b})
        finally:
            await self._s.delete(PROPOSAL_LOCKS, f"{PLATFORM}|{lock_key}")

        if self._notifier is not None and self._authz is not None:
            recipients = await self._managers(shop_b)
            for recipient in recipients:
                await self._notifier.send(
                    tenant=shop_b, user_id=recipient,
                    template_key="operations.mutual_benefit_proposed",
                    variables={}, idempotency_key=f"refpartner_propose:{agreement.id}:{recipient}")
        return agreement

    async def _managers(self, tenant: str) -> list[str]:
        from app.core.notify_recipients import managers_for_branch
        try:
            return await managers_for_branch(store=self._s, authz=self._authz, tenant=tenant,
                                             branch_id="", capability="operations.manage")
        except Exception:                                                      # noqa: BLE001
            return []

    async def accept(self, *, tenant: str, agreement_id: str) -> MutualBenefitAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise MutualBenefitError(NOT_FOUND)
        if tenant != agreement.shop_b:
            # ONLY THE INVITED SIDE ACCEPTS — the proposer already agreed by proposing (design doc
            # step 1: A sets the terms). Accepting one's own proposal is not a second approval.
            raise MutualBenefitError(FORBIDDEN)
        agreement = await self._synced(agreement)
        if agreement.status != PROPOSED:
            raise MutualBenefitError(WRONG_STATE)

        subscribed = await self._is_subscribed(tenant)
        if subscribed is None:
            raise MutualBenefitError(BILLING_UNAVAILABLE)
        if not subscribed:
            raise MutualBenefitError(NOT_SUBSCRIBED)

        now = _now()
        candidate_end = now + agreement.agreement_duration_days * 24 * 3600
        # THE AUTHORITATIVE CAP CHECK — this is the one moment `started_at`/`ends_at` are actually
        # committed, so this is where the real interval is checked, for BOTH roles independently
        # (module docstring's own "THE CONCURRENCY CAP"). `propose()`'s own check used "now" at
        # propose time as an estimate; accepting can happen days later, so re-checking here with
        # today's real numbers is what actually enforces the cap rather than merely gesturing at
        # it — a shop that was under the cap when proposed but has since filled up must still be
        # refused here.
        if (await self._would_exceed_cap(agreement.shop_a, now, candidate_end)
                or await self._would_exceed_cap(agreement.shop_b, now, candidate_end)):
            raise MutualBenefitError(OVER_CONCURRENCY_CAP)

        agreement.status = ACTIVE
        agreement.started_at = now
        agreement.ends_at = candidate_end
        agreement.original_ends_at = agreement.ends_at
        await self._save_agreement(agreement)
        await self._audit(agreement.id, EV_ACCEPTED, actor_tenant=tenant)
        await self._audit(agreement.id, EV_ACTIVATED, actor_tenant=PLATFORM)
        return agreement

    async def reject(self, *, tenant: str, agreement_id: str) -> MutualBenefitAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise MutualBenefitError(NOT_FOUND)
        if tenant != agreement.shop_b:
            raise MutualBenefitError(FORBIDDEN)
        agreement = await self._synced(agreement)
        if agreement.status != PROPOSED:
            raise MutualBenefitError(WRONG_STATE)
        agreement.status = REJECTED
        await self._save_agreement(agreement)
        await self._audit(agreement.id, EV_REJECTED, actor_tenant=tenant)
        return agreement

    async def cancel_request(self, *, tenant: str, agreement_id: str) -> MutualBenefitAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise MutualBenefitError(NOT_FOUND)
        agreement = await self._synced(agreement)
        if agreement.status != ACTIVE:
            raise MutualBenefitError(WRONG_STATE)
        agreement.status = CANCEL_REQUESTED
        agreement.cancel_requested_by = tenant
        await self._save_agreement(agreement)
        await self._audit(agreement.id, EV_CANCEL_REQUESTED, actor_tenant=tenant)
        other = agreement.shop_b if tenant == agreement.shop_a else agreement.shop_a
        if self._notifier is not None and self._authz is not None:
            for recipient in await self._managers(other):
                await self._notifier.send(
                    tenant=other, user_id=recipient,
                    template_key="operations.mutual_benefit_cancel_requested",
                    variables={},
                    idempotency_key=f"refpartner_cancel:{agreement.id}:{recipient}")
        return agreement

    async def cancel_confirm(self, *, tenant: str, agreement_id: str) -> MutualBenefitAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise MutualBenefitError(NOT_FOUND)
        agreement = await self._synced(agreement)
        if agreement.status != CANCEL_REQUESTED:
            raise MutualBenefitError(WRONG_STATE)
        if tenant == agreement.cancel_requested_by:
            # THE SAME SIDE THAT ASKED CANNOT ALSO BE THE ONE WHO CONFIRMS — that would be a
            # unilateral cancellation wearing a two-step costume (design doc: mutual consent only).
            raise MutualBenefitError(FORBIDDEN)
        if tenant not in (agreement.shop_a, agreement.shop_b):
            raise MutualBenefitError(FORBIDDEN)
        agreement.status = ENDED
        await self._save_agreement(agreement)
        await self._audit(agreement.id, EV_CANCEL_CONFIRMED, actor_tenant=tenant)
        return agreement

    # ── the `record_visit()` hook — called for EVERY channel, see module docstring ──────────────
    async def on_visit_recorded(self, *, tenant: str, customer_phone: str, service_ids: list[str],
                                total_minor: int, visit_id: str) -> "MutualBenefitGrant | None":
        """`tenant` is the shop where the visit just happened — potentially shop_a for zero, one, or
        several active agreements at once. Never raises: any failure here must never be seen by the
        caller, which is why `Operations.record_visit` wraps this call itself defensively too — this
        method's own contract is simply "best effort", the same posture `InAppNotifier.send` and
        `rating_alerts.check_and_notify` already take for every non-essential side effect off the
        visit-recording hot path.

        RETURNS THE GRANT THIS VISIT ACTUALLY CREATED, IF ANY — added for the counter's own
        celebration moment (owner's own requirement: a real "you just earned a partner reward"
        screen, fired only on a genuine new grant, never on the routine case). The RETURN VALUE is
        an optimisation only — `Operations.record_visit` still wraps this whole call in its own
        try/except and treats any exception as "nothing happened", so a bug in this return path can
        at worst lose the celebration, never the visit or the grant itself (which is already
        durably written by `_grant` before this method returns).
        """
        rows, _ = await self._s.find(AGREEMENTS, {"tenant": PLATFORM, "shop_a": tenant, "status": ACTIVE},
                                     limit=200)
        for row in rows:
            agreement = MutualBenefitAgreement(**{k: v for k, v in row.items() if k != "tenant"})
            agreement = await self._synced(agreement)
            if agreement.status != ACTIVE:
                continue
            if not self._condition_met(agreement, service_ids=service_ids, total_minor=total_minor):
                continue
            grant = await self._grant(agreement, customer_phone=customer_phone, visit_id=visit_id)
            if grant is not None:
                return grant
        return None

    @staticmethod
    def _condition_met(agreement: MutualBenefitAgreement, *, service_ids: list[str],
                       total_minor: int) -> bool:
        if agreement.condition_type == CONDITION_MIN_TOTAL:
            try:
                threshold = int(agreement.condition_value)
            except (TypeError, ValueError):
                return False
            return total_minor >= threshold
        return agreement.condition_value in service_ids

    async def _grant(self, agreement: MutualBenefitAgreement, *, customer_phone: str,
                     visit_id: str) -> "MutualBenefitGrant | None":
        phone = canonical_phone(customer_phone, default_cc=self._cc)
        if not phone:
            return None
        # IDEMPOTENT ON THE TRIGGERING VISIT — a retried `record_visit()` call (the visit's own
        # idempotency key already made record_visit itself return the SAME visit id) must never
        # grant twice for that one visit. `None`, not the existing grant: a REPLAY is not a NEW
        # grant, and the celebration screen this return value now feeds must fire once, on the
        # visit that actually created it — never again on a retry of the same one.
        existing, _ = await self._s.find(
            GRANTS, {"tenant": PLATFORM, "agreement_id": agreement.id,
                    "triggering_visit_id": visit_id}, limit=1)
        if existing:
            return None

        # THE PER-PERIOD CAP — refused silently from the visit's own point of view (a visit is never
        # affected either way), logged as its own outcome so the granting shop's KPI screen can show
        # WHY a period produced fewer referrals than usual.
        if agreement.per_period_cap > 0:
            now = _now()
            window_start = now - _CAP_PERIOD_SECONDS
            recent, _ = await self._s.find(
                GRANTS, {"tenant": PLATFORM, "agreement_id": agreement.id}, limit=100000)
            in_window = [g for g in recent if int(g.get("created") or 0) >= window_start]
            if len(in_window) >= agreement.per_period_cap:
                await self._audit(agreement.id, EV_GRANT_CAPPED, actor_tenant=PLATFORM,
                                  detail={"triggering_visit_id": visit_id})
                return None

        now = _now()
        grant = MutualBenefitGrant(
            id=f"rpg_{uuid_hex()}", agreement_id=agreement.id, shop_a=agreement.shop_a,
            shop_b=agreement.shop_b, customer_phone=phone, triggering_visit_id=visit_id,
            created=now, expires_at=now + agreement.grant_validity_days * 24 * 3600,
            # COPIED FROM THE AGREEMENT NOW, NOT REFERENCED LATER — see `MutualBenefitGrant`'s own
            # docstring on these eight fields for why.
            grant_type=agreement.grant_type, gift_service_id=agreement.gift_service_id,
            gift_service_name=agreement.gift_service_name,
            discount_scope=agreement.discount_scope,
            discount_group_id=agreement.discount_group_id,
            discount_group_name=agreement.discount_group_name,
            discount_kind=agreement.discount_kind, discount_amount=agreement.discount_amount)
        await self._s.put(GRANTS, f"{PLATFORM}|{grant.id}", {"tenant": PLATFORM, **asdict(grant)})
        await self._audit(agreement.id, EV_GRANT_CREATED, actor_tenant=PLATFORM,
                          detail={"grant_id": grant.id, "triggering_visit_id": visit_id})
        return grant

    # ── shop B's own redemption check — the visit screen's own "does this phone qualify" ────────
    async def eligibility(self, tenant: str, phone: str) -> dict[str, Any] | None:
        """The one thing shop B's own visit screen may ask: is this phone eligible right now, for
        what, until when — NEVER which shop referred them (see `MutualBenefitGrant.public_for_beneficiary`
        and the module docstring's privacy note). `None` when nothing live is found."""
        canon = canonical_phone(phone, default_cc=self._cc)
        if not canon:
            return None
        now = _now()
        rows, _ = await self._s.find(
            GRANTS, {"tenant": PLATFORM, "shop_b": tenant, "customer_phone": canon}, limit=1000)
        live = [r for r in rows if not r.get("redeemed_at") and int(r.get("expires_at") or 0) > now]
        if not live:
            return None
        live.sort(key=lambda r: int(r.get("expires_at") or 0))
        best = MutualBenefitGrant(**{k: v for k, v in live[0].items() if k != "tenant"})
        return best.public_for_beneficiary()

    async def redeem(self, tenant: str, phone: str, *, visit_id: str) -> bool:
        """Called when shop B actually applies its own discount on a real visit — marks the
        BEST-MATCHING live grant used, so the KPI screen's "used vs expired unused" ratio is real.
        An already-earned grant is honoured regardless of the parent agreement's own state
        (design doc's own explicit rule) — this method never reads `MutualBenefitAgreement` at all.

        IDEMPOTENT ON `visit_id`, DELIBERATELY (added for `core/entitlements.py`'s own use from
        `Operations.apply_offer`). `EntitlementGateway.finalize` calls this BEFORE the visit is
        stamped, so a caller whose write timed out — but whose `redeem` in fact landed — retries
        the WHOLE `apply_offer` flow, which calls `choose()` again and then `redeem()` again for
        the SAME visit. Without this check, the retry would find the first grant now marked
        redeemed and simply pick the NEXT best live one — spending a SECOND grant for one visit,
        a real double-redemption bug a naive "just pick the best live one" would have on retry.
        """
        canon = canonical_phone(phone, default_cc=self._cc)
        if not canon:
            return False
        now = _now()
        rows, _ = await self._s.find(
            GRANTS, {"tenant": PLATFORM, "shop_b": tenant, "customer_phone": canon}, limit=1000)
        already = next((r for r in rows if r.get("redeemed_visit_id") == visit_id), None)
        if already is not None:
            return True
        live = [r for r in rows if not r.get("redeemed_at") and int(r.get("expires_at") or 0) > now]
        if not live:
            return False
        live.sort(key=lambda r: int(r.get("expires_at") or 0))
        row = live[0]
        grant = MutualBenefitGrant(**{k: v for k, v in row.items() if k != "tenant"})
        grant.redeemed_at = now
        grant.redeemed_visit_id = visit_id
        await self._s.put(GRANTS, f"{PLATFORM}|{grant.id}", {"tenant": PLATFORM, **asdict(grant)})
        await self._audit(grant.agreement_id, EV_GRANT_REDEEMED, actor_tenant=tenant,
                          detail={"grant_id": grant.id, "visit_id": visit_id})
        return True

    # ── KPIs — each shop sees only its own numbers (design doc's own isolation rule) ─────────────
    async def kpis(self, tenant: str) -> dict[str, Any]:
        as_a, _ = await self._s.find(GRANTS, {"tenant": PLATFORM, "shop_a": tenant}, limit=100000)
        as_b, _ = await self._s.find(GRANTS, {"tenant": PLATFORM, "shop_b": tenant}, limit=100000)
        now = _now()

        def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
            total = len(rows)
            redeemed = sum(1 for r in rows if r.get("redeemed_at"))
            expired_unused = sum(1 for r in rows if not r.get("redeemed_at")
                                 and int(r.get("expires_at") or 0) <= now)
            redemption_rate = round(redeemed / total, 4) if total else 0.0
            history: dict[str, int] = {}
            for r in rows:
                mk = time.strftime("%Y-%m", time.gmtime(int(r.get("created") or 0)))
                history[mk] = history.get(mk, 0) + 1
            # PER REAL CATALOGUE REFERENCE — the owner's own reason for the catalogue-driven grant
            # model existing at all ("عشان يربطها... ربحت"): a shop must be able to see which of
            # its OWN services/packages a partnership actually moved, counted toward that shop's
            # own numbers, never a free-text note nobody could reconcile against anything real.
            # A GIFT and a DISCOUNT scope "item" both reference a service the same way, so they
            # share one bucket by service id; a DISCOUNT scope "group" gets its own, by package id.
            by_service: dict[str, dict[str, Any]] = {}
            by_group: dict[str, dict[str, Any]] = {}
            for r in rows:
                sid = str(r.get("gift_service_id") or "")
                if sid:
                    bucket = by_service.setdefault(
                        sid, {"service_name": r.get("gift_service_name") or "", "granted": 0,
                             "redeemed": 0})
                    bucket["granted"] += 1
                    if r.get("redeemed_at"):
                        bucket["redeemed"] += 1
                    continue
                gid = str(r.get("discount_group_id") or "")
                if gid:
                    bucket = by_group.setdefault(
                        gid, {"group_name": r.get("discount_group_name") or "", "granted": 0,
                             "redeemed": 0})
                    bucket["granted"] += 1
                    if r.get("redeemed_at"):
                        bucket["redeemed"] += 1
            return {"referrals_sent": total, "redeemed": redeemed,
                   "expired_unused": expired_unused, "redemption_rate": redemption_rate,
                   "by_month": dict(sorted(history.items())),
                   "gift_redemptions_by_service": by_service,
                   "discount_redemptions_by_group": by_group}

        return {"as_referrer": _summarise(as_a), "as_beneficiary": _summarise(as_b)}
