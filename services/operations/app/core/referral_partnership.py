"""Referral partnership — a customer who meets a condition at shop A becomes automatically
eligible for a discount at shop B, detected automatically, no proof the customer must carry.

See docs/خطة-شراكة-استراتيجية-الإحالة.md for the full design this module implements. NOT the same
feature as `core/coupons.py` («تحالف استراتيجي») — that one discounts a shop's OWN subscription with
us, through billing-service, unilaterally. This one discounts nothing of ours: it never touches
money, pricing, or a discount's own value at all. Shop B applies its own discount however it
normally does (a manual till reduction, a note on the receipt) — our whole job is organising the
relationship and detecting eligibility, nothing financial. Separate collections entirely; nothing
here is built on top of `coupons.py`.

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
never shop A's name (`ReferralGrant.public_for_beneficiary()`). The granting shop's name is kept on
the row for the two parties' OWN agreement screens (they already know each other — they approved the
partnership by name) and for any future settlement report between them; it is simply never handed to
the beneficiary's OWN redemption flow, which only needs "does this phone qualify, and for what".

AN ALREADY-EARNED GRANT ALWAYS HONOURS ITS OWN EXPIRY, REGARDLESS OF WHY THE PARENT AGREEMENT
STOPPED (design doc's own explicit rule) — `ReferralGrant.expires_at` is copied at CREATION time from
the agreement's `grant_validity_days` and never again consulted against the agreement's own state.
`redeem()` checks only the grant's own `expires_at`, never the agreement.

MUTUAL CONSENT FOR EARLY CANCELLATION, SAME MECHANISM AS CREATION — a `cancel_request` needs the
other side's own `cancel_confirm` before the agreement actually ends; the ONE exception is a
subscription pausing, which is immediate and unilateral by nature (a shop that stopped paying cannot
be asked to "agree" to anything).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.signup import PHONE_INDEX, canonical_phone

AGREEMENTS = "referral_partnership_agreements"
GRANTS = "referral_partnership_grants"
AUDIT_LOG = "referral_partnership_audit_log"
PROPOSAL_LOCKS = "referral_partnership_proposal_locks"

# Same reserved-key registry pattern as `core/coupons.py::PLATFORM` — a fact owned by neither
# tenant, stored under a key no real tenant id can collide with.
PLATFORM = "_platform"

FEATURE_KEY = "feature.referral_partnership"

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


class ReferralError(Exception):
    """A refusal an API route can show verbatim to the caller."""


SELF_PARTNER = "self_partner"
NOT_SUBSCRIBED = "not_subscribed"
NOT_FOUND = "not_found"
FORBIDDEN = "forbidden"
BAD_CONDITION = "bad_condition"
WRONG_STATE = "wrong_state"
BILLING_UNAVAILABLE = "billing_unavailable"


@dataclass
class ReferralAgreement:
    id: str
    shop_a: str                    # the referring shop — where the condition is met
    shop_b: str                    # the beneficiary shop — where the discount is offered
    condition_type: str
    condition_value: str           # halalas as a string for min_total_minor, else a service id
    discount_note: str             # shop B's OWN description of its own discount — never enforced
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

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReferralGrant:
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

    def public(self) -> dict[str, Any]:
        return asdict(self)

    def public_for_beneficiary(self) -> dict[str, Any]:
        """`shop B`'s OWN redemption screen never sees shop A's identity (design doc's privacy
        rule) — only that this phone is eligible, and until when."""
        return {"eligible": True, "expires_at": self.expires_at,
               "redeemed": bool(self.redeemed_at)}


@dataclass
class ReferralAuditEntry:
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
    # truly happened". Nanosecond epoch (`time.time_ns()`), not a process-local counter — this
    # service runs as several replicas, and a counter reset per process would let two pods
    # writing the SAME agreement's log interleave with colliding sequence numbers.
    seq: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


class ReferralPartnershipEngine:
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
        entry = ReferralAuditEntry(id=f"rpaud_{uuid_hex()}", agreement_id=agreement_id,
                                   event=event, actor_tenant=actor_tenant,
                                   detail=detail or {}, created=_now(), seq=time.time_ns())
        await self._s.put(AUDIT_LOG, f"{PLATFORM}|{entry.id}", {"tenant": PLATFORM, **asdict(entry)})

    async def audit_log(self, tenant: str, agreement_id: str, limit: int = 200
                        ) -> list[ReferralAuditEntry]:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise ReferralError(NOT_FOUND)
        rows, _ = await self._s.find(
            AUDIT_LOG, {"tenant": PLATFORM, "agreement_id": agreement_id},
            limit=limit, sort=("seq", "asc"))
        return [ReferralAuditEntry(**{k: v for k, v in r.items() if k != "tenant"}) for r in rows]

    # ── subscription gate — same shape as `CouponService.granter_is_subscribed` ────────────────
    async def _is_subscribed(self, tenant: str) -> bool | None:
        plan_id = await self._plans.plan_id_for_key(FEATURE_KEY)
        if not plan_id:
            return False
        subs = await self._plans.subscriptions(tenant)
        if subs is None:
            return None
        return any(str(s.get("plan") or "") == plan_id
                  and str(s.get("status") or "") in ("active", "trialing") for s in subs)

    async def _lookup_tenant_by_phone(self, phone: str) -> str:
        row = await self._s.get(PHONE_INDEX, canonical_phone(phone, default_cc=self._cc))
        return str((row or {}).get("tenant") or "")

    # ── reads, always tenant-scoped ──────────────────────────────────────────────────────────────
    async def _agreement_row(self, agreement_id: str) -> dict[str, Any] | None:
        return await self._s.get(AGREEMENTS, f"{PLATFORM}|{agreement_id}")

    async def _agreement_for(self, tenant: str, agreement_id: str) -> ReferralAgreement | None:
        """`None` for an id that does not exist AND for one that exists but belongs to two OTHER
        tenants — the two are indistinguishable to the caller, on purpose (an IDOR probe must learn
        nothing from the difference)."""
        row = await self._agreement_row(agreement_id)
        if row is None:
            return None
        if row.get("shop_a") != tenant and row.get("shop_b") != tenant:
            return None
        return ReferralAgreement(**{k: v for k, v in row.items() if k != "tenant"})

    async def get(self, tenant: str, agreement_id: str) -> ReferralAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise ReferralError(NOT_FOUND)
        return await self._synced(agreement)

    async def agreements_for(self, tenant: str, limit: int = 200) -> list[ReferralAgreement]:
        as_a, _ = await self._s.find(AGREEMENTS, {"tenant": PLATFORM, "shop_a": tenant},
                                     limit=limit, sort=("created", "desc"))
        as_b, _ = await self._s.find(AGREEMENTS, {"tenant": PLATFORM, "shop_b": tenant},
                                     limit=limit, sort=("created", "desc"))
        seen: set[str] = set()
        out: list[ReferralAgreement] = []
        for row in list(as_a) + list(as_b):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            agreement = ReferralAgreement(**{k: v for k, v in row.items() if k != "tenant"})
            out.append(await self._synced(agreement))
        out.sort(key=lambda a: a.created, reverse=True)
        return out[:limit]

    async def _save_agreement(self, agreement: ReferralAgreement) -> None:
        await self._s.put(AGREEMENTS, f"{PLATFORM}|{agreement.id}",
                          {"tenant": PLATFORM, **asdict(agreement)})

    # ── lazy subscription pause/resume — consulted on every read/hook touch, never a cron ───────
    async def _synced(self, agreement: ReferralAgreement) -> ReferralAgreement:
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

    # ── the act itself ──────────────────────────────────────────────────────────────────────────
    async def propose(self, *, shop_a: str, shop_b_phone: str, operator_id: str,
                      condition_type: str, condition_value: str, discount_note: str,
                      grant_validity_days: int, agreement_duration_days: int,
                      per_period_cap: int = 0, idempotency_key: str = "") -> ReferralAgreement:
        if condition_type not in CONDITION_TYPES:
            raise ReferralError(BAD_CONDITION)
        if condition_type == CONDITION_MIN_TOTAL:
            try:
                if int(condition_value) <= 0:
                    raise ReferralError(BAD_CONDITION)
            except (TypeError, ValueError):
                raise ReferralError(BAD_CONDITION) from None
        elif not str(condition_value).strip():
            raise ReferralError(BAD_CONDITION)
        if not (0 < grant_validity_days <= 365):
            raise ReferralError(BAD_CONDITION)
        if not (0 < agreement_duration_days <= 3650):
            raise ReferralError(BAD_CONDITION)
        if per_period_cap < 0:
            raise ReferralError(BAD_CONDITION)

        subscribed = await self._is_subscribed(shop_a)
        if subscribed is None:
            raise ReferralError(BILLING_UNAVAILABLE)
        if not subscribed:
            raise ReferralError(NOT_SUBSCRIBED)

        shop_b = await self._lookup_tenant_by_phone(shop_b_phone)
        if not shop_b:
            raise ReferralError(NOT_FOUND)
        if shop_b == shop_a:
            raise ReferralError(SELF_PARTNER)

        if idempotency_key:
            rows, _ = await self._s.find(
                AGREEMENTS, {"tenant": PLATFORM, "shop_a": shop_a, "idempotency_key": idempotency_key},
                limit=1)
            if rows:
                return await self._synced(
                    ReferralAgreement(**{k: v for k, v in rows[0].items() if k != "tenant"}))

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
            raise ReferralError(WRONG_STATE)
        try:
            existing, _ = await self._s.find(
                AGREEMENTS, {"tenant": PLATFORM, "shop_a": shop_a, "shop_b": shop_b}, limit=200)
            live = [r for r in existing if r.get("status") in (PROPOSED, ACTIVE, PAUSED,
                                                               CANCEL_REQUESTED)]
            if live:
                return await self._synced(
                    ReferralAgreement(**{k: v for k, v in live[0].items() if k != "tenant"}))

            now = _now()
            agreement = ReferralAgreement(
                id=f"rpa_{uuid_hex()}", shop_a=shop_a, shop_b=shop_b,
                condition_type=condition_type, condition_value=str(condition_value),
                discount_note=discount_note[:512], grant_validity_days=grant_validity_days,
                agreement_duration_days=agreement_duration_days, per_period_cap=per_period_cap,
                created_by=shop_a, created_by_operator=operator_id, created=now,
                status=PROPOSED, proposal_expires_at=now + _PROPOSAL_TTL_SECONDS,
                idempotency_key=idempotency_key)
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
                    template_key="operations.referral_partnership_proposed",
                    variables={}, idempotency_key=f"refpartner_propose:{agreement.id}:{recipient}")
        return agreement

    async def _managers(self, tenant: str) -> list[str]:
        from app.core.notify_recipients import managers_for_branch
        try:
            return await managers_for_branch(store=self._s, authz=self._authz, tenant=tenant,
                                             branch_id="", capability="operations.manage")
        except Exception:                                                      # noqa: BLE001
            return []

    async def accept(self, *, tenant: str, agreement_id: str) -> ReferralAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise ReferralError(NOT_FOUND)
        if tenant != agreement.shop_b:
            # ONLY THE INVITED SIDE ACCEPTS — the proposer already agreed by proposing (design doc
            # step 1: A sets the terms). Accepting one's own proposal is not a second approval.
            raise ReferralError(FORBIDDEN)
        agreement = await self._synced(agreement)
        if agreement.status != PROPOSED:
            raise ReferralError(WRONG_STATE)

        subscribed = await self._is_subscribed(tenant)
        if subscribed is None:
            raise ReferralError(BILLING_UNAVAILABLE)
        if not subscribed:
            raise ReferralError(NOT_SUBSCRIBED)

        now = _now()
        agreement.status = ACTIVE
        agreement.started_at = now
        agreement.ends_at = now + agreement.agreement_duration_days * 24 * 3600
        agreement.original_ends_at = agreement.ends_at
        await self._save_agreement(agreement)
        await self._audit(agreement.id, EV_ACCEPTED, actor_tenant=tenant)
        await self._audit(agreement.id, EV_ACTIVATED, actor_tenant=PLATFORM)
        return agreement

    async def reject(self, *, tenant: str, agreement_id: str) -> ReferralAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise ReferralError(NOT_FOUND)
        if tenant != agreement.shop_b:
            raise ReferralError(FORBIDDEN)
        agreement = await self._synced(agreement)
        if agreement.status != PROPOSED:
            raise ReferralError(WRONG_STATE)
        agreement.status = REJECTED
        await self._save_agreement(agreement)
        await self._audit(agreement.id, EV_REJECTED, actor_tenant=tenant)
        return agreement

    async def cancel_request(self, *, tenant: str, agreement_id: str) -> ReferralAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise ReferralError(NOT_FOUND)
        agreement = await self._synced(agreement)
        if agreement.status != ACTIVE:
            raise ReferralError(WRONG_STATE)
        agreement.status = CANCEL_REQUESTED
        agreement.cancel_requested_by = tenant
        await self._save_agreement(agreement)
        await self._audit(agreement.id, EV_CANCEL_REQUESTED, actor_tenant=tenant)
        other = agreement.shop_b if tenant == agreement.shop_a else agreement.shop_a
        if self._notifier is not None and self._authz is not None:
            for recipient in await self._managers(other):
                await self._notifier.send(
                    tenant=other, user_id=recipient,
                    template_key="operations.referral_partnership_cancel_requested",
                    variables={},
                    idempotency_key=f"refpartner_cancel:{agreement.id}:{recipient}")
        return agreement

    async def cancel_confirm(self, *, tenant: str, agreement_id: str) -> ReferralAgreement:
        agreement = await self._agreement_for(tenant, agreement_id)
        if agreement is None:
            raise ReferralError(NOT_FOUND)
        agreement = await self._synced(agreement)
        if agreement.status != CANCEL_REQUESTED:
            raise ReferralError(WRONG_STATE)
        if tenant == agreement.cancel_requested_by:
            # THE SAME SIDE THAT ASKED CANNOT ALSO BE THE ONE WHO CONFIRMS — that would be a
            # unilateral cancellation wearing a two-step costume (design doc: mutual consent only).
            raise ReferralError(FORBIDDEN)
        if tenant not in (agreement.shop_a, agreement.shop_b):
            raise ReferralError(FORBIDDEN)
        agreement.status = ENDED
        await self._save_agreement(agreement)
        await self._audit(agreement.id, EV_CANCEL_CONFIRMED, actor_tenant=tenant)
        return agreement

    # ── the `record_visit()` hook — called for EVERY channel, see module docstring ──────────────
    async def on_visit_recorded(self, *, tenant: str, customer_phone: str, service_ids: list[str],
                                total_minor: int, visit_id: str) -> None:
        """`tenant` is the shop where the visit just happened — potentially shop_a for zero, one, or
        several active agreements at once. Never raises: any failure here must never be seen by the
        caller, which is why `Operations.record_visit` wraps this call itself defensively too — this
        method's own contract is simply "best effort", the same posture `InAppNotifier.send` and
        `rating_alerts.check_and_notify` already take for every non-essential side effect off the
        visit-recording hot path.
        """
        rows, _ = await self._s.find(AGREEMENTS, {"tenant": PLATFORM, "shop_a": tenant, "status": ACTIVE},
                                     limit=200)
        for row in rows:
            agreement = ReferralAgreement(**{k: v for k, v in row.items() if k != "tenant"})
            agreement = await self._synced(agreement)
            if agreement.status != ACTIVE:
                continue
            if not self._condition_met(agreement, service_ids=service_ids, total_minor=total_minor):
                continue
            await self._grant(agreement, customer_phone=customer_phone, visit_id=visit_id)

    @staticmethod
    def _condition_met(agreement: ReferralAgreement, *, service_ids: list[str],
                       total_minor: int) -> bool:
        if agreement.condition_type == CONDITION_MIN_TOTAL:
            try:
                threshold = int(agreement.condition_value)
            except (TypeError, ValueError):
                return False
            return total_minor >= threshold
        return agreement.condition_value in service_ids

    async def _grant(self, agreement: ReferralAgreement, *, customer_phone: str,
                     visit_id: str) -> None:
        phone = canonical_phone(customer_phone, default_cc=self._cc)
        if not phone:
            return
        # IDEMPOTENT ON THE TRIGGERING VISIT — a retried `record_visit()` call (the visit's own
        # idempotency key already made record_visit itself return the SAME visit id) must never
        # grant twice for that one visit.
        existing, _ = await self._s.find(
            GRANTS, {"tenant": PLATFORM, "agreement_id": agreement.id,
                    "triggering_visit_id": visit_id}, limit=1)
        if existing:
            return

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
                return

        now = _now()
        grant = ReferralGrant(
            id=f"rpg_{uuid_hex()}", agreement_id=agreement.id, shop_a=agreement.shop_a,
            shop_b=agreement.shop_b, customer_phone=phone, triggering_visit_id=visit_id,
            created=now, expires_at=now + agreement.grant_validity_days * 24 * 3600)
        await self._s.put(GRANTS, f"{PLATFORM}|{grant.id}", {"tenant": PLATFORM, **asdict(grant)})
        await self._audit(agreement.id, EV_GRANT_CREATED, actor_tenant=PLATFORM,
                          detail={"grant_id": grant.id, "triggering_visit_id": visit_id})

    # ── shop B's own redemption check — the visit screen's own "does this phone qualify" ────────
    async def eligibility(self, tenant: str, phone: str) -> dict[str, Any] | None:
        """The one thing shop B's own visit screen may ask: is this phone eligible right now, for
        what, until when — NEVER which shop referred them (see `ReferralGrant.public_for_beneficiary`
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
        best = ReferralGrant(**{k: v for k, v in live[0].items() if k != "tenant"})
        return best.public_for_beneficiary()

    async def redeem(self, tenant: str, phone: str, *, visit_id: str) -> bool:
        """Called when shop B actually applies its own discount on a real visit — marks the
        BEST-MATCHING live grant used, so the KPI screen's "used vs expired unused" ratio is real.
        An already-earned grant is honoured regardless of the parent agreement's own state
        (design doc's own explicit rule) — this method never reads `ReferralAgreement` at all.

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
        grant = ReferralGrant(**{k: v for k, v in row.items() if k != "tenant"})
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
            return {"referrals_sent": total, "redeemed": redeemed,
                   "expired_unused": expired_unused, "redemption_rate": redemption_rate,
                   "by_month": dict(sorted(history.items()))}

        return {"as_referrer": _summarise(as_a), "as_beneficiary": _summarise(as_b)}
