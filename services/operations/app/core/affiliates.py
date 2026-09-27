"""Phase 4 of docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md — the "marketer/influencer" tier,
a classification the shop assigns directly (§5 of the plan doc), fully independent of the ordinary
referral campaign built in Phase 2/3.

THE SHOP ADDS AN AFFILIATE DIRECTLY, BY PHONE — no request/approval step. This is a deliberate,
narrower shape than `MutualBenefitGrant`'s own propose/accept lifecycle or coworking's join-request
flow: an affiliate is a marketer/influencer the shop already has an off-platform relationship with
(a blogger, an ambassador) and is choosing to onboard with NEGOTIATED terms (their own custom code,
their own discount for followers, their own per-sale reward) — there is nothing for the marketer to
"apply" for, because the terms are the shop's own decision from the first row.

NEVER BOTH ROLES AT ONCE, PER THE OWNER'S OWN EXPLICIT INSTRUCTION. A phone is either an ordinary
referrer/customer or an affiliate at a given shop — never both simultaneously. This is enforced two
ways: (1) `add()` refuses a phone that already holds an ACTIVE affiliate row at this tenant, and
(2) `core/referral_redemption.py::register()` checks, even when a customer enters someone's
ORDINARY global referral code, whether that referrer phone is CURRENTLY an active affiliate here —
if so, the affiliate's own negotiated terms apply instead of the tenant's ordinary campaign, never
both, and never a silent stacking of the two reward shapes.

SWITCHING ROLES NEVER TOUCHES HISTORY, ON PURPOSE. Toggling an affiliate row `active` (or removing
it) never reaches into `core/referral_redemption.py`'s own grants, nor into loyalty's ledger — every
point already credited stays exactly where and how it was earned, tagged by whichever role earned
it (`reason="referral"` vs `reason="affiliate"`, see that module's own `redeem()`). There is no
migration, no merge, no re-tagging: a former affiliate who becomes an ordinary referrer keeps their
affiliate history as affiliate history, and starts a clean slate as a referrer from that point on —
exactly the "لا تروح ولا تتحول" instruction this module exists to honour.

SETTLEMENT IS BOOKKEEPING, NEVER MONEY MOVEMENT (plan doc §5's own "بلا أي تدخل مالي"). `unsettled_
points` is a running counter this service alone maintains (never billing-service, never a wallet);
`settle()` only ever decrements it and appends an immutable audit row — the actual payment always
happens OUTSIDE this system, and the shop is simply recording that it happened.

EVERY READ-MODIFY-WRITE HERE IS LOCK-PROTECTED, ON PURPOSE. Three real races live in this module
if it were not: (1) two concurrent `add()` calls for the SAME phone (or the SAME code, from two
different phones) both passing their uniqueness checks before either writes — the exact defect
class `core/referral_redemption.py::register()`'s own `_REGISTER_LOCK` closes for a pending grant;
(2) two concurrent `credit_sale()` calls for the SAME affiliate (two different new customers
redeeming at nearly the same moment) racing a classic lost-update on `unsettled_points` — whichever
write lands second overwrites the first's increment, silently losing a referrer's real credit; and
(3) two concurrent `settle()` calls both reading the same balance before either decrements it,
letting an owner double-record (or over-record) a settlement past what was actually owed. All three
use the SAME `claim()`-based mutex (`_lock`/`_unlock` below) — acquired with a short retry loop
(never a bare "busy, refuse" the way `register()`'s own lock is, because dropping a REAL sale's
credit silently is a worse failure here than a few milliseconds' wait) and explicitly released via
`delete()` the moment the protected section finishes, with the TTL only as a crash safety net.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from app.core.signup import canonical_phone

AFFILIATES = "referral_affiliates"
SETTLEMENTS = "referral_affiliate_settlements"
_LOCKS = "referral_affiliate_locks"
_LOCK_TTL_SECONDS = 5
_LOCK_RETRY_ATTEMPTS = 100
_LOCK_RETRY_DELAY_SECONDS = 0.01

REWARD_FIXED_POINTS = "fixed_points"
REWARD_INVOICE_PERCENTAGE = "invoice_percentage"
REWARD_TYPES = (REWARD_FIXED_POINTS, REWARD_INVOICE_PERCENTAGE)

_MAX_PERCENT = 99
_MAX_CODE_LENGTH = 16


class AffiliateError(Exception):
    """A refusal an owner should read verbatim — never a stack trace."""


def _positive_int(value: Any, *, field: str, minimum: int = 1) -> int:
    # bool is an int subclass in Python — `{"points": true}` must never be silently read as 1.
    # Same hardening as services/referrals' own app/core/rewards.py::_positive_int.
    if isinstance(value, bool):
        raise AffiliateError(f"{field}: قيمة غير صالحة")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise AffiliateError(f"{field}: قيمة غير صالحة")
    if isinstance(value, float) and value != n:
        raise AffiliateError(f"{field}: قيمة غير صالحة")
    if n < minimum:
        raise AffiliateError(f"{field}: يجب أن يكون {minimum} على الأقل")
    return n


def _percent(value: Any, *, field: str) -> int:
    n = _positive_int(value, field=field)
    if n > _MAX_PERCENT:
        raise AffiliateError(f"{field}: لا يمكن أن يتجاوز {_MAX_PERCENT}%")
    return n


_ELIGIBILITY_VALUES = {"new", "max_visits", "open"}


def _validate_beneficiary_eligibility(eligibility: str, max_visits: Any) -> tuple[str, int]:
    """Same three real values `core/referral_redemption.py::_check_beneficiary_eligibility`
    reads — validated here, at write time, so a bad value never reaches the engine at redeem
    time, where a refusal is a much worse moment to explain than a rejected admin form."""
    value = (eligibility or "new").strip()
    if value not in _ELIGIBILITY_VALUES:
        raise AffiliateError("قيمة غير صالحة لمن يقدر يستخدم كود هذا المسوّق")
    if value != "max_visits":
        return value, 0
    try:
        n = int(max_visits)
    except (TypeError, ValueError):
        raise AffiliateError("عدد الزيارات المسموح يجب أن يكون رقمًا") from None
    if n < 0:
        raise AffiliateError("عدد الزيارات المسموح يجب أن يكون صفرًا أو أكثر")
    return value, n


def validate_reward(reward_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """The affiliate's own per-sale reward — deliberately just these two shapes (a flat point
    count, or a percentage of the sale), never the full 8-type ordinary referral catalogue: an
    affiliate's terms are a single negotiated number, not a campaign configuration (plan doc §5:
    "مكافأة مخصصة بالكامل ... نقاط أو قيمة لكل عملية بيع")."""
    if not isinstance(params, dict):
        raise AffiliateError("مكافأة المسوّق: بيانات غير صالحة")
    if reward_type == REWARD_FIXED_POINTS:
        return {"points": _positive_int(params.get("points"), field="عدد نقاط المسوّق")}
    if reward_type == REWARD_INVOICE_PERCENTAGE:
        return {"percent": _percent(params.get("percent"), field="نسبة المسوّق من الفاتورة")}
    raise AffiliateError(f"نوع مكافأة غير معروف للمسوّق: {reward_type}")


@dataclass
class Affiliate:
    id: str
    tenant: str
    phone: str
    code: str
    discount_percent: int
    reward_type: str
    reward_params: dict[str, Any]
    created_at: int
    active: bool = True
    unsettled_points: int = 0
    total_earned_points: int = 0
    # WHO MAY REDEEM THIS AFFILIATE'S OWN CODE (owner instruction, 2026-09-27) — independent of
    # the tenant's ordinary campaign setting of the same shape
    # (services/referrals' own Campaign.beneficiary_eligibility): an affiliate's terms are already
    # fully independent of the campaign everywhere else in this fleet, and this is no exception.
    # See core/referral_redemption.py::_check_beneficiary_eligibility for the three real values
    # ("new" / "max_visits" / "open") and exactly what each means.
    beneficiary_eligibility: str = "new"
    beneficiary_max_visits: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "Affiliate":
        return Affiliate(
            id=row["id"], tenant=row["tenant"], phone=row["phone"], code=row["code"],
            discount_percent=int(row.get("discount_percent") or 0),
            reward_type=row["reward_type"], reward_params=dict(row.get("reward_params") or {}),
            created_at=int(row.get("created_at") or 0), active=bool(row.get("active", True)),
            unsettled_points=int(row.get("unsettled_points") or 0),
            total_earned_points=int(row.get("total_earned_points") or 0),
            # ABSENT ON ANY ROW ADDED BEFORE THIS SETTING EXISTED — defaults to "new", the exact
            # rule that already applied unconditionally, so an old affiliate's real behaviour never
            # silently changes underneath it.
            beneficiary_eligibility=str(row.get("beneficiary_eligibility") or "new"),
            beneficiary_max_visits=int(row.get("beneficiary_max_visits") or 0),
        )


@dataclass
class SettlementRecord:
    id: str
    tenant: str
    affiliate_id: str
    affiliate_phone: str
    points_settled: int
    full: bool
    note: str
    actor: str
    created_at: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "SettlementRecord":
        return SettlementRecord(
            id=row["id"], tenant=row["tenant"], affiliate_id=row["affiliate_id"],
            affiliate_phone=row.get("affiliate_phone") or "",
            points_settled=int(row.get("points_settled") or 0), full=bool(row.get("full")),
            note=row.get("note") or "", actor=row.get("actor") or "",
            created_at=int(row.get("created_at") or 0),
        )


class AffiliateService:
    def __init__(self, store: Any, *, default_cc: str) -> None:
        self._s = store
        self._cc = default_cc

    async def _lock(self, key: str) -> bool:
        """Retry-until-available, never a bare refuse — see this module's own docstring for why
        the three callers below cannot afford to silently skip their critical section."""
        for _ in range(_LOCK_RETRY_ATTEMPTS):
            won = await self._s.claim(_LOCKS, key, {}, ttl_seconds=_LOCK_TTL_SECONDS,
                                      now=time.time())
            if won:
                return True
            await asyncio.sleep(_LOCK_RETRY_DELAY_SECONDS)
        return False

    async def _unlock(self, key: str) -> None:
        await self._s.delete(_LOCKS, key)

    async def add(self, tenant: str, *, phone: str, code: str, discount_percent: Any,
                 reward_type: str, reward_params: dict[str, Any],
                 beneficiary_eligibility: str = "new", beneficiary_max_visits: Any = 0) -> Affiliate:
        canon_phone = canonical_phone(phone, default_cc=self._cc)
        if not canon_phone:
            raise AffiliateError("رقم جوال المسوّق مطلوب")

        norm_code = (code or "").strip().upper()
        if not norm_code:
            raise AffiliateError("كود المسوّق مطلوب")
        if len(norm_code) > _MAX_CODE_LENGTH:
            raise AffiliateError(f"كود المسوّق أطول من {_MAX_CODE_LENGTH} حرفاً")

        percent = _percent(discount_percent, field="نسبة خصم متابعي المسوّق")
        normalized_reward = validate_reward(reward_type, reward_params)
        eligibility, max_visits = _validate_beneficiary_eligibility(
            beneficiary_eligibility, beneficiary_max_visits)

        # TENANT-WIDE, DELIBERATELY (not per-phone/per-code separately) — `add()` is a rare,
        # owner-triggered admin action, never a high-throughput path, so the simplicity of ONE
        # lock closing BOTH uniqueness checks at once outweighs the (negligible) cost of two
        # different owners at the same shop never adding affiliates in the exact same instant.
        lock_key = f"{tenant}|add"
        if not await self._lock(lock_key):
            raise AffiliateError("جارٍ إضافة مسوّق آخر الآن — أعد المحاولة بعد لحظة")
        try:
            existing_by_phone = await self.get_by_phone(tenant, canon_phone)
            if existing_by_phone is not None:
                # NEVER BOTH ROLES, AND NEVER TWO ACTIVE AFFILIATE ROWS FOR ONE PHONE — the
                # owner's own instruction: one phone is either an affiliate or an ordinary
                # referrer/customer at this shop, never both, and never ambiguous between two
                # affiliate terms either.
                raise AffiliateError("هذا الرقم مسوّق نشط بالفعل عند هذا المتجر")

            existing_by_code = await self.get_by_code(tenant, norm_code, include_inactive=True)
            if existing_by_code is not None:
                raise AffiliateError("هذا الكود مستخدم لمسوّق آخر بهذا المتجر")

            affiliate = Affiliate(
                id=str(uuid.uuid4()), tenant=tenant, phone=canon_phone, code=norm_code,
                discount_percent=percent, reward_type=reward_type,
                reward_params=normalized_reward, created_at=int(time.time()),
                beneficiary_eligibility=eligibility, beneficiary_max_visits=max_visits,
            )
            await self._s.put(AFFILIATES, f"{tenant}|{affiliate.id}", affiliate.to_dict())
            return affiliate
        finally:
            await self._unlock(lock_key)

    async def get(self, tenant: str, affiliate_id: str) -> Affiliate | None:
        row = await self._s.get(AFFILIATES, f"{tenant}|{affiliate_id}")
        if row is None or row.get("tenant") != tenant:
            # NO CROSS-TENANT EXISTENCE LEAK — same posture every tenant-scoped read in this
            # fleet takes (see services/referrals' own CampaignService.get, coworking's resources).
            return None
        return Affiliate.from_dict(row)

    async def get_by_phone(self, tenant: str, phone: str) -> Affiliate | None:
        canon = canonical_phone(phone, default_cc=self._cc)
        if not canon:
            return None
        rows, _ = await self._s.find(AFFILIATES, {"tenant": tenant, "phone": canon}, limit=1000)
        active = [r for r in rows if r.get("active")]
        return Affiliate.from_dict(active[0]) if active else None

    async def get_by_code(self, tenant: str, code: str, *,
                          include_inactive: bool = False) -> Affiliate | None:
        norm = (code or "").strip().upper()
        if not norm:
            return None
        rows, _ = await self._s.find(AFFILIATES, {"tenant": tenant, "code": norm}, limit=1000)
        if not include_inactive:
            rows = [r for r in rows if r.get("active")]
        return Affiliate.from_dict(rows[0]) if rows else None

    async def list(self, tenant: str) -> list[Affiliate]:
        rows, _ = await self._s.find(AFFILIATES, {"tenant": tenant}, limit=1000,
                                     sort=("created_at", "desc"))
        return [Affiliate.from_dict(r) for r in rows]

    async def set_active(self, tenant: str, affiliate_id: str, *, active: bool) -> Affiliate:
        """The ONLY mutable term — same immutability discipline `CampaignService.set_active`
        already takes: a changed rate/reward is a new affiliate relationship, never a silent PATCH
        on the old one's numbers."""
        affiliate = await self.get(tenant, affiliate_id)
        if affiliate is None:
            raise AffiliateError("المسوّق غير موجود")
        if active and not affiliate.active:
            # Re-activating must not silently create a SECOND active row for a phone that picked
            # up a different active affiliate slot in the meantime — the SAME invariant `add()`
            # enforces, under the SAME tenant-wide lock, so a reactivation and a fresh `add()` for
            # the same phone can never both slip through at once.
            lock_key = f"{tenant}|add"
            if not await self._lock(lock_key):
                raise AffiliateError("جارٍ تعديل مسوّق آخر الآن — أعد المحاولة بعد لحظة")
            try:
                other = await self.get_by_phone(tenant, affiliate.phone)
                if other is not None and other.id != affiliate.id:
                    raise AffiliateError("هذا الرقم مسوّق نشط بالفعل عند هذا المتجر")
                affiliate.active = True
                await self._s.put(AFFILIATES, f"{tenant}|{affiliate.id}", affiliate.to_dict())
                return affiliate
            finally:
                await self._unlock(lock_key)
        affiliate.active = bool(active)
        await self._s.put(AFFILIATES, f"{tenant}|{affiliate.id}", affiliate.to_dict())
        return affiliate

    async def credit_sale(self, tenant: str, affiliate_id: str, points: int) -> Affiliate | None:
        """Called ONLY from `core/referral_redemption.py::redeem()`, once per redeemed grant —
        never exposed over HTTP. `points` is already validated positive by the caller (the same
        `points > 0` guard `redeem()` checks before ever calling `loyalty.award`).

        LOCKED, retry-until-available — two different new customers redeeming through the SAME
        affiliate at nearly the same moment must never lose one's increment to the other's
        overwrite (a classic lost-update on a plain read-modify-write)."""
        lock_key = f"{tenant}|{affiliate_id}"
        if not await self._lock(lock_key):
            # Best-effort, same posture `redeem()`'s own call site already takes for the loyalty
            # award beside it: a rare, transient failure here must never fail the customer's own
            # discount — it only means this one sale's points are missing from the affiliate's
            # settlement balance until a human notices.
            return None
        try:
            affiliate = await self.get(tenant, affiliate_id)
            if affiliate is None:
                return None
            affiliate.unsettled_points += int(points)
            affiliate.total_earned_points += int(points)
            await self._s.put(AFFILIATES, f"{tenant}|{affiliate.id}", affiliate.to_dict())
            return affiliate
        finally:
            await self._unlock(lock_key)

    async def settle(self, tenant: str, affiliate_id: str, *, points: int | None = None,
                     note: str = "", actor: str = "") -> tuple[Affiliate, SettlementRecord]:
        lock_key = f"{tenant}|{affiliate_id}"
        if not await self._lock(lock_key):
            raise AffiliateError("جارٍ تحديث رصيد هذا المسوّق الآن — أعد المحاولة بعد لحظة")
        try:
            return await self._settle_locked(tenant, affiliate_id, points=points, note=note,
                                             actor=actor)
        finally:
            await self._unlock(lock_key)

    async def _settle_locked(self, tenant: str, affiliate_id: str, *, points: int | None,
                             note: str, actor: str) -> tuple[Affiliate, SettlementRecord]:
        affiliate = await self.get(tenant, affiliate_id)
        if affiliate is None:
            raise AffiliateError("المسوّق غير موجود")

        if points is None:
            amount = affiliate.unsettled_points
            full = True
        else:
            amount = _positive_int(points, field="عدد النقاط المُسوَّاة")
            if amount > affiliate.unsettled_points:
                raise AffiliateError(
                    f"لا يمكن تسوية أكثر من الرصيد الحالي ({affiliate.unsettled_points} نقطة)")
            full = amount == affiliate.unsettled_points

        if amount <= 0:
            raise AffiliateError("لا يوجد رصيد لتسويته")

        affiliate.unsettled_points -= amount
        await self._s.put(AFFILIATES, f"{tenant}|{affiliate.id}", affiliate.to_dict())

        record = SettlementRecord(
            id=str(uuid.uuid4()), tenant=tenant, affiliate_id=affiliate.id,
            affiliate_phone=affiliate.phone, points_settled=amount, full=full, note=note or "",
            actor=actor or "", created_at=int(time.time()),
        )
        await self._s.put(SETTLEMENTS, f"{tenant}|{record.id}", record.to_dict())
        return affiliate, record

    async def list_settlements(self, tenant: str, affiliate_id: str) -> list[SettlementRecord]:
        rows, _ = await self._s.find(
            SETTLEMENTS, {"tenant": tenant, "affiliate_id": affiliate_id}, limit=1000,
            sort=("created_at", "desc"))
        return [SettlementRecord.from_dict(r) for r in rows]
