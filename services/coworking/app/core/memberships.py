"""`Membership` — a seat on a «month»/«year» resource (owner decision, 2026-10-06).

THE WHOLE POINT: a seat, NEVER a specific desk — `core/bookings.py` stays the engine for a
resource somebody occupies at an exact hour; this is for "how many members does this resource
hold right now", counted in whole periods instead. The two never mix: a resource is either
`rental_period="hourly"` (bookings.py's door) or `"month"`/`"year"` (this file's door) —
`ResourceService.update()` refuses to ever change which, so a row never needs to ask twice which
engine owns it.

TRACKING ONLY — NO MONEY MOVES THROUGH THIS SERVICE (owner's own explicit call, 2026-10-06, same
posture `models.py`'s own module doc already holds for `hourly_price_minor`). "تجديد تلقائي"
means the stored `period_end` moves forward on its own; nothing here ever charges anyone,
ever asks billing-service about anyone, and a lapsed membership is simply a row whose period
ran out — never a failed payment, because no payment was ever attempted.

THE TWO WAYS A MEMBERSHIP ENDS, AND WHY THEY ARE NEVER THE SAME CODE PATH (owner's own explicit
reasoning): someone who simply stops renewing is the ordinary case — `stop_renewal` flips one
flag, the membership keeps running until `period_end`, and nothing more is asked of anyone.
Someone who wants OUT RIGHT NOW, mid-period, is different — real money may already have changed
hands between the shop and the member for days neither will actually use, and "I never agreed to
leave early" is a real dispute this file exists to make impossible: `force_end` REQUIRES an
explicit acknowledgment (who agreed, and a note of what was actually agreed), stamped with the
time, and refuses outright without one.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from app.core.lock import SlotClaimBusy, claiming
from app.core.models import (
    MEMBERSHIP_ACTIVE,
    MEMBERSHIP_END_EXPIRED,
    MEMBERSHIP_END_FORCE_ENDED,
    MEMBERSHIP_ENDED,
    MEMBERSHIPS,
    RENTAL_PERIOD_SECONDS,
    Membership,
)

# ONE FIXED LANE PER RESOURCE, NEVER TIME-BUCKETED — `lock.py` was built for an hourly booking's
# own [starts_at, ends_at) span; a membership has no time-of-day span at all, so every join on the
# same resource claims the identical single lane, serialising them exactly like bookings.py does
# for one 15-minute bucket. `starts_at=0, ends_at=1` always lands on bucket 0 alone — one lane.


class MembershipError(Exception):
    """A refusal a caller should show verbatim — never a stack trace."""


class MembershipRefused(Exception):
    """Carries a stable machine-readable `reason`, same shape `BookingRefused` already holds —
    the public and admin routes both need it to decide what the caller should be told to do."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _key(membership_id: str) -> str:
    return membership_id


class MembershipService:
    def __init__(self, store: Any, *, resources: Any, joins: Any, pause: Any) -> None:
        self._store = store
        self._resources = resources
        self._joins = joins
        self._pause = pause

    async def _active_count(self, tenant: str, resource_id: str) -> int:
        rows, _ = await self._store.find(
            MEMBERSHIPS, {"tenant": tenant, "resource_id": resource_id, "status": MEMBERSHIP_ACTIVE},
            limit=5000)
        return len(rows)

    async def _own_active(self, tenant: str, resource_id: str, phone: str) -> dict | None:
        rows, _ = await self._store.find(
            MEMBERSHIPS,
            {"tenant": tenant, "resource_id": resource_id, "freelancer_phone": phone,
             "status": MEMBERSHIP_ACTIVE},
            limit=10)
        return rows[0] if rows else None

    async def join(self, tenant: str, *, resource_id: str, phone: str) -> dict:
        """The same refusal order `bookings.py::create` already documents — spec-identical join
        gate, capacity in place of a time-of-day slot. See that module's own docstring for why
        each reason is distinct rather than one generic refusal."""
        if not phone:
            raise MembershipRefused("BAD_PHONE", "رقم الجوال غير صالح")

        if await self._pause.is_paused(tenant):
            raise MembershipRefused("SHOP_PAUSED", "هذا المحل أوقف استقبال حجوزات جديدة مؤقتاً")

        resource = await self._resources.get(tenant, resource_id)
        if resource is None:
            raise MembershipRefused("RESOURCE_NOT_FOUND", "المورد غير موجود")
        if not resource.active:
            raise MembershipRefused("RESOURCE_INACTIVE", "هذا المورد متوقف حالياً عن استقبال طلبات جديدة")
        if resource.rental_period not in RENTAL_PERIOD_SECONDS:
            raise MembershipRefused("NOT_A_MEMBERSHIP_RESOURCE", "هذا المورد ليس عضوية — يُحجز بالساعة")

        from app.core.joins import JOIN_APPROVED, JOIN_BLOCKED, JOIN_PENDING

        status = await self._joins.status(tenant, phone)
        if status is None:
            await self._joins.ensure_pending(tenant, phone)
            raise MembershipRefused("JOIN_REQUIRED", "طلب انضمامك أُرسل لصاحب المحل بانتظار الموافقة")
        if status == JOIN_BLOCKED:
            raise MembershipRefused("BLOCKED", "هذا الرقم محظور من الاشتراك في هذا المحل")
        if status == JOIN_PENDING:
            raise MembershipRefused("PENDING_APPROVAL", "طلب انضمامك لا يزال بانتظار موافقة صاحب المحل")
        assert status == JOIN_APPROVED

        if await self._own_active(tenant, resource_id, phone) is not None:
            raise MembershipRefused("ALREADY_MEMBER", "لديك عضوية نشطة على هذا المورد بالفعل")

        # THE SAME LOCK-PLUS-RETRY SHAPE `bookings.py::create` USES, one fixed lane per resource
        # (see this module's own header) — found by the same class of hard concurrency test:
        # without it, N simultaneous joins on a resource with capacity < N can all read the same
        # "count so far" before any of them writes, and all N land. See
        # `test_capacity_race_...` in this feature's own test suite for the proof.
        deadline = time.time() + 2.0
        last_busy_exc: SlotClaimBusy | None = None
        while time.time() < deadline:
            now = time.time()
            try:
                async with claiming(self._store, tenant=tenant, resource_id=resource_id,
                                    starts_at=0, ends_at=1, now=now):
                    if await self._active_count(tenant, resource_id) >= resource.quantity:
                        raise MembershipRefused("FULL", "هذا المورد ممتلئ — لا مقاعد شاغرة حالياً")
                    started_at = int(now)
                    period_seconds = RENTAL_PERIOD_SECONDS[resource.rental_period]
                    membership = Membership(
                        id=str(uuid.uuid4()), tenant=tenant, resource_id=resource_id,
                        freelancer_phone=phone, started_at=started_at,
                        period_end=started_at + period_seconds, auto_renew=True,
                        status=MEMBERSHIP_ACTIVE, period_price_minor=resource.period_price_minor,
                        created_at=started_at)
                    await self._store.put(MEMBERSHIPS, membership.id, membership.to_dict())
                    return membership.to_dict()
            except SlotClaimBusy as exc:
                last_busy_exc = exc
                await asyncio.sleep(0)
                continue
        raise MembershipRefused(
            "FULL", str(last_busy_exc) if last_busy_exc else
            "تعذّر الاشتراك — حاول مرة أخرى")

    async def get(self, tenant: str, membership_id: str) -> dict | None:
        row = await self._store.get(MEMBERSHIPS, _key(membership_id))
        if row is None or row.get("tenant") != tenant:
            return None
        return row

    async def list_for_tenant(self, tenant: str, *, resource_id: str | None = None,
                              status: str | None = None) -> list[dict]:
        where: dict[str, Any] = {"tenant": tenant}
        if resource_id:
            where["resource_id"] = resource_id
        if status:
            where["status"] = status
        rows, _ = await self._store.find(MEMBERSHIPS, where, limit=5000,
                                         sort=("created_at", "asc"))
        return rows

    async def list_for_phone(self, tenant: str, phone: str) -> list[dict]:
        rows, _ = await self._store.find(
            MEMBERSHIPS, {"tenant": tenant, "freelancer_phone": phone}, limit=1000,
            sort=("created_at", "asc"))
        return rows

    async def stop_renewal(self, tenant: str, membership_id: str) -> dict:
        """THE ORDINARY PATH — takes effect at `period_end`, nothing more asked of anyone. Either
        side (the shop, or the member himself through the public portal) may call this; both read
        identically, because stopping a renewal is never a disputed fact the way ending one early
        is (see module doc)."""
        row = await self.get(tenant, membership_id)
        if row is None:
            raise MembershipError("العضوية غير موجودة")
        if row.get("status") != MEMBERSHIP_ACTIVE:
            raise MembershipError("هذه العضوية منتهية بالفعل")
        row = {**row, "auto_renew": False}
        await self._store.put(MEMBERSHIPS, membership_id, row)
        return row

    async def resume_renewal(self, tenant: str, membership_id: str) -> dict:
        """The undo — same-day regret stays cheap. Refused once the membership has already
        `ended` (the period genuinely ran out, or it was force-ended) — "resume" on a row with
        nothing left to resume reads as a new join, which is `join()`'s own door, not this one."""
        row = await self.get(tenant, membership_id)
        if row is None:
            raise MembershipError("العضوية غير موجودة")
        if row.get("status") != MEMBERSHIP_ACTIVE:
            raise MembershipError("هذه العضوية منتهية بالفعل — اشترك من جديد")
        row = {**row, "auto_renew": True}
        await self._store.put(MEMBERSHIPS, membership_id, row)
        return row

    async def force_end(self, tenant: str, membership_id: str, *, acknowledged: bool,
                        ack_by: str, note: str = "") -> dict:
        """END IT NOW, MID-PERIOD — see module doc. `acknowledged` must be `True`, explicitly,
        every call; there is no default that lets this run silently. `ack_by` is WHO is making
        this record (an operator's own subject, or the member's own phone when he ends his own
        membership through the public portal) — never blank, so "who agreed" is never a question
        the row itself cannot answer later."""
        if not acknowledged:
            raise MembershipError(
                "إنهاء فوري بمنتصف المدة يحتاج إقراراً صريحاً أن الطرفين متفقان — بدون تجديد قادم، "
                "وبلا أي مبلغ مسترجع")
        if not ack_by:
            raise MembershipError("لا بد من تسجيل من أقرّ بهذا الإنهاء")
        row = await self.get(tenant, membership_id)
        if row is None:
            raise MembershipError("العضوية غير موجودة")
        if row.get("status") != MEMBERSHIP_ACTIVE:
            raise MembershipError("هذه العضوية منتهية بالفعل")
        now = int(time.time())
        row = {**row, "status": MEMBERSHIP_ENDED, "ended_at": now,
              "end_reason": MEMBERSHIP_END_FORCE_ENDED, "auto_renew": False,
              "force_ack_by": ack_by, "force_ack_note": note.strip()}
        await self._store.put(MEMBERSHIPS, membership_id, row)
        return row

    async def renew_due(self, tenant: str | None = None, *, now: int | None = None) -> dict:
        """The cron sweep (`/internal/coworking/renew-memberships`) — every ACTIVE membership
        whose `period_end` has passed: extend it one more period if `auto_renew` is still true,
        or mark it `ended`/`expired` if the member (or the shop) already turned renewal off. Scans
        every tenant when `tenant` is empty, same "the whole fleet, one sweep" shape every other
        periodic job in this product already takes.

        NEVER CHARGES, NEVER ASKS BILLING ANYTHING — see module doc. Extending `period_end` is the
        entire act.
        """
        where: dict[str, Any] = {"status": MEMBERSHIP_ACTIVE}
        if tenant:
            where["tenant"] = tenant
        rows, _ = await self._store.find(MEMBERSHIPS, where, limit=20_000)
        current = int(now if now is not None else time.time())
        renewed = ended = 0
        for row in rows:
            if int(row.get("period_end") or 0) > current:
                continue
            resource = await self._resources.get(row["tenant"], row["resource_id"])
            period_seconds = RENTAL_PERIOD_SECONDS.get(
                resource.rental_period if resource is not None else "", 30 * 86400)
            if row.get("auto_renew", True):
                updated = {**row, "period_end": int(row["period_end"]) + period_seconds}
                await self._store.put(MEMBERSHIPS, row["id"], updated)
                renewed += 1
            else:
                updated = {**row, "status": MEMBERSHIP_ENDED, "ended_at": current,
                          "end_reason": MEMBERSHIP_END_EXPIRED}
                await self._store.put(MEMBERSHIPS, row["id"], updated)
                ended += 1
        return {"renewed": renewed, "ended": ended}
