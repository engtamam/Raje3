"""`app/core/memberships.py` — the seat-membership engine (owner decision 2026-10-06): join gate,
capacity, renewal sweep, and the two distinct ways a membership ends.

`_SlowStore` is the same trick `test_bookings.py` already uses — makes `find`/`get` genuinely
yield the event loop so a concurrent-join test interleaves for real instead of racing to
completion one at a time.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.joins import JoinRegistry
from app.core.memberships import MembershipError, MembershipRefused, MembershipService
from app.core.models import (
    MEMBERSHIP_ACTIVE,
    MEMBERSHIP_END_EXPIRED,
    MEMBERSHIP_END_FORCE_ENDED,
    MEMBERSHIP_ENDED,
    RENTAL_MONTH,
    RENTAL_YEAR,
)
from app.core.pause import PauseSettings
from app.core.resources import ResourceService

TENANT = "shop1"
PHONE = "+966501234567"
PHONE2 = "+966502222222"
PHONE3 = "+966503333333"


class _SlowStore:
    def __init__(self, inner: MemoryDataStore) -> None:
        self._inner = inner

    async def find(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.find(*a, **kw)

    async def get(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.get(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _services(store):
    resources = ResourceService(store=store)
    joins = JoinRegistry(store=store)
    pause = PauseSettings(store=store)
    memberships = MembershipService(store=store, resources=resources, joins=joins, pause=pause)
    return resources, joins, pause, memberships


async def _membership_resource(resources, tenant=TENANT, *, quantity=1, period=RENTAL_MONTH,
                               price=50000):
    return await resources.create(tenant, name="عضوية مقعد مشترك", rental_period=period,
                                  quantity=quantity, period_price_minor=price)


async def _approved(joins, tenant, phone):
    await joins.ensure_pending(tenant, phone)
    await joins.approve(tenant, phone)


# ── the join gate — same acceptance table bookings.py's own tests already hold ─────────────────
def test_first_join_attempt_becomes_a_join_request_not_a_membership():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources)
        with pytest.raises(MembershipRefused) as exc:
            await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert exc.value.reason == "JOIN_REQUIRED"
        assert await joins.status(TENANT, PHONE) == "pending"

    asyncio.run(run())


def test_pending_phone_is_refused_distinctly():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources)
        await joins.ensure_pending(TENANT, PHONE)
        with pytest.raises(MembershipRefused) as exc:
            await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert exc.value.reason == "PENDING_APPROVAL"

    asyncio.run(run())


def test_blocked_phone_is_refused_distinctly():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources)
        await joins.block(TENANT, PHONE)
        with pytest.raises(MembershipRefused) as exc:
            await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert exc.value.reason == "BLOCKED"

    asyncio.run(run())


def test_shop_paused_refuses_new_memberships():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources)
        await _approved(joins, TENANT, PHONE)
        await pause.set_paused(TENANT, True)
        with pytest.raises(MembershipRefused) as exc:
            await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert exc.value.reason == "SHOP_PAUSED"

    asyncio.run(run())


def test_disabled_resource_refuses_new_memberships():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources)
        await resources.update(TENANT, r.id, active=False)
        await _approved(joins, TENANT, PHONE)
        with pytest.raises(MembershipRefused) as exc:
            await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert exc.value.reason == "RESOURCE_INACTIVE"

    asyncio.run(run())


def test_hourly_resource_refuses_a_membership_join():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await resources.create(TENANT, name="قاعة اجتماعات")  # default rental_period=hourly
        await _approved(joins, TENANT, PHONE)
        with pytest.raises(MembershipRefused) as exc:
            await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert exc.value.reason == "NOT_A_MEMBERSHIP_RESOURCE"

    asyncio.run(run())


def test_approved_phone_joins_successfully_and_price_is_snapshotted():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, price=60000)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert m["status"] == MEMBERSHIP_ACTIVE
        assert m["period_price_minor"] == 60000
        assert m["auto_renew"] is True
        assert m["period_end"] > m["started_at"]

        # the shop raises the price AFTER joining — the member's own stamped rate must never
        # silently change (same "historical fact" discipline hourly_price_minor already holds).
        await resources.update(TENANT, r.id, period_price_minor=999999)
        rows = await memberships.list_for_tenant(TENANT)
        assert rows[0]["period_price_minor"] == 60000

    asyncio.run(run())


def test_a_second_join_on_the_same_resource_by_the_same_phone_is_refused():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=5)
        await _approved(joins, TENANT, PHONE)
        await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        with pytest.raises(MembershipRefused) as exc:
            await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert exc.value.reason == "ALREADY_MEMBER"

    asyncio.run(run())


# ── capacity ──────────────────────────────────────────────────────────────────────────────────
def test_capacity_lets_exactly_quantity_members_in_and_refuses_the_next():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=3)
        for phone in (PHONE, PHONE2, PHONE3):
            await _approved(joins, TENANT, phone)
            m = await memberships.join(TENANT, resource_id=r.id, phone=phone)
            assert m["status"] == MEMBERSHIP_ACTIVE
        fourth = "+966504444444"
        await _approved(joins, TENANT, fourth)
        with pytest.raises(MembershipRefused) as exc:
            await memberships.join(TENANT, resource_id=r.id, phone=fourth)
        assert exc.value.reason == "FULL"

    asyncio.run(run())


def test_force_ending_one_membership_frees_a_seat():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        first = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)

        await _approved(joins, TENANT, PHONE2)
        with pytest.raises(MembershipRefused):
            await memberships.join(TENANT, resource_id=r.id, phone=PHONE2)

        await memberships.force_end(TENANT, first["id"], acknowledged=True, ack_by="owner1",
                                    note="اتفقنا على الخروج")
        second = await memberships.join(TENANT, resource_id=r.id, phone=PHONE2)
        assert second["status"] == MEMBERSHIP_ACTIVE

    asyncio.run(run())


def test_capacity_race_exactly_quantity_concurrent_joins_succeed_the_rest_refused():
    """The hard version — N phones joining a quantity-capacity resource AT ONCE must leave
    EXACTLY `quantity` members, never more (the lock doing nothing) and never fewer (the lock
    refusing everyone but the first, same bug this exact shape caught in bookings.py)."""
    QUANTITY = 4
    CONTENDERS = 9

    async def run():
        store = _SlowStore(MemoryDataStore())
        resources = ResourceService(store=store)
        joins = JoinRegistry(store=store)
        pause = PauseSettings(store=store)
        memberships = MembershipService(store=store, resources=resources, joins=joins, pause=pause)
        r = await _membership_resource(resources, quantity=QUANTITY)
        phones = [f"+96650{i:07d}" for i in range(CONTENDERS)]
        for phone in phones:
            await joins.ensure_pending(TENANT, phone)
            await joins.approve(TENANT, phone)

        out = await asyncio.gather(
            *[memberships.join(TENANT, resource_id=r.id, phone=p) for p in phones],
            return_exceptions=True)
        joined = [o for o in out if not isinstance(o, Exception)]
        refused = [o for o in out if isinstance(o, Exception)]
        return joined, refused

    joined, refused = asyncio.run(run())
    assert len(joined) == QUANTITY, (
        f"expected exactly {QUANTITY} members for a {QUANTITY}-seat resource under "
        f"{CONTENDERS}-way contention, got {len(joined)}")
    assert len(refused) == CONTENDERS - QUANTITY
    assert all(isinstance(e, MembershipRefused) and e.reason == "FULL" for e in refused)


def test_different_resources_do_not_queue_behind_each_other():
    async def run():
        store = _SlowStore(MemoryDataStore())
        resources = ResourceService(store=store)
        joins = JoinRegistry(store=store)
        pause = PauseSettings(store=store)
        memberships = MembershipService(store=store, resources=resources, joins=joins, pause=pause)
        r1 = await _membership_resource(resources, quantity=1)
        r2 = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)

        out = await asyncio.gather(
            memberships.join(TENANT, resource_id=r1.id, phone=PHONE),
            memberships.join(TENANT, resource_id=r2.id, phone=PHONE),
            return_exceptions=True)
        return [o for o in out if isinstance(o, Exception)]

    errors = asyncio.run(run())
    assert errors == [], "two different resources' capacity must not contend"


# ── the two ways a membership ends ───────────────────────────────────────────────────────────
def test_stop_renewal_never_ends_the_membership_immediately():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        stopped = await memberships.stop_renewal(TENANT, m["id"])
        assert stopped["auto_renew"] is False
        assert stopped["status"] == MEMBERSHIP_ACTIVE, "stopping renewal must not end it today"

    asyncio.run(run())


def test_resume_renewal_undoes_a_stop():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        await memberships.stop_renewal(TENANT, m["id"])
        resumed = await memberships.resume_renewal(TENANT, m["id"])
        assert resumed["auto_renew"] is True

    asyncio.run(run())


def test_force_end_refuses_without_explicit_acknowledgment():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        with pytest.raises(MembershipError):
            await memberships.force_end(TENANT, m["id"], acknowledged=False, ack_by="owner1")
        # STILL ACTIVE — a refused force-end must change nothing.
        row = await memberships.get(TENANT, m["id"])
        assert row["status"] == MEMBERSHIP_ACTIVE

    asyncio.run(run())


def test_force_end_refuses_with_no_one_named_as_having_acknowledged():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        with pytest.raises(MembershipError):
            await memberships.force_end(TENANT, m["id"], acknowledged=True, ack_by="")

    asyncio.run(run())


def test_force_end_records_who_acknowledged_and_the_reason_distinctly_from_expiry():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        ended = await memberships.force_end(TENANT, m["id"], acknowledged=True,
                                            ack_by=PHONE, note="اتفقنا على الخروج اليوم")
        assert ended["status"] == MEMBERSHIP_ENDED
        assert ended["end_reason"] == MEMBERSHIP_END_FORCE_ENDED
        assert ended["force_ack_by"] == PHONE
        assert ended["force_ack_note"] == "اتفقنا على الخروج اليوم"
        assert ended["auto_renew"] is False
        assert ended["ended_at"] > 0

    asyncio.run(run())


def test_cannot_force_end_an_already_ended_membership():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        await memberships.force_end(TENANT, m["id"], acknowledged=True, ack_by="owner1")
        with pytest.raises(MembershipError):
            await memberships.force_end(TENANT, m["id"], acknowledged=True, ack_by="owner1")

    asyncio.run(run())


def test_after_ending_a_membership_the_same_phone_can_rejoin_immediately():
    """«لو خرج يقدر يوقف التجديد ويدخل ثاني مرة مباشرة» — no cooldown, no lockout, the join gate
    is shop-wide (joins.py's own module doc) and untouched by a membership ending."""
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        first = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        await memberships.force_end(TENANT, first["id"], acknowledged=True, ack_by=PHONE)
        second = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        assert second["status"] == MEMBERSHIP_ACTIVE
        assert second["id"] != first["id"]

    asyncio.run(run())


# ── renewal sweep ─────────────────────────────────────────────────────────────────────────────
def test_renew_due_extends_an_auto_renewing_membership_whose_period_ran_out():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1, period=RENTAL_MONTH)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        past_end = m["period_end"]

        result = await memberships.renew_due(TENANT, now=past_end + 1)
        assert result["renewed"] == 1
        assert result["ended"] == 0
        row = await memberships.get(TENANT, m["id"])
        assert row["status"] == MEMBERSHIP_ACTIVE
        assert row["period_end"] == past_end + 30 * 86400

    asyncio.run(run())


def test_renew_due_ends_a_membership_whose_renewal_was_stopped():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1, period=RENTAL_MONTH)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        await memberships.stop_renewal(TENANT, m["id"])
        past_end = m["period_end"]

        result = await memberships.renew_due(TENANT, now=past_end + 1)
        assert result["renewed"] == 0
        assert result["ended"] == 1
        row = await memberships.get(TENANT, m["id"])
        assert row["status"] == MEMBERSHIP_ENDED
        assert row["end_reason"] == MEMBERSHIP_END_EXPIRED

    asyncio.run(run())


def test_renew_due_never_touches_a_membership_whose_period_has_not_ended_yet():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        result = await memberships.renew_due(TENANT, now=m["started_at"] + 10)
        assert result == {"renewed": 0, "ended": 0}
        row = await memberships.get(TENANT, m["id"])
        assert row["period_end"] == m["period_end"], "an untouched row must not have moved"

    asyncio.run(run())


def test_renew_due_uses_the_resources_own_period_not_a_guessed_default():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        r = await _membership_resource(resources, quantity=1, period=RENTAL_YEAR)
        await _approved(joins, TENANT, PHONE)
        m = await memberships.join(TENANT, resource_id=r.id, phone=PHONE)
        past_end = m["period_end"]
        await memberships.renew_due(TENANT, now=past_end + 1)
        row = await memberships.get(TENANT, m["id"])
        assert row["period_end"] == past_end + 365 * 86400

    asyncio.run(run())


def test_renew_due_sweeps_every_tenant_when_none_is_named():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        rA = await _membership_resource(resources, tenant="shopA", quantity=1)
        rB = await _membership_resource(resources, tenant="shopB", quantity=1)
        await joins.ensure_pending("shopA", PHONE)
        await joins.approve("shopA", PHONE)
        await joins.ensure_pending("shopB", PHONE)
        await joins.approve("shopB", PHONE)
        mA = await memberships.join("shopA", resource_id=rA.id, phone=PHONE)
        mB = await memberships.join("shopB", resource_id=rB.id, phone=PHONE)
        result = await memberships.renew_due(now=max(mA["period_end"], mB["period_end"]) + 1)
        assert result["renewed"] == 2

    asyncio.run(run())


def test_cross_tenant_memberships_never_leak():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        rA = await _membership_resource(resources, tenant="shopA", quantity=1)
        rB = await _membership_resource(resources, tenant="shopB", quantity=1)
        await joins.ensure_pending("shopA", PHONE)
        await joins.approve("shopA", PHONE)
        await joins.ensure_pending("shopB", PHONE)
        await joins.approve("shopB", PHONE)
        await memberships.join("shopA", resource_id=rA.id, phone=PHONE)
        await memberships.join("shopB", resource_id=rB.id, phone=PHONE)

        mine_a = await memberships.list_for_phone("shopA", PHONE)
        mine_b = await memberships.list_for_phone("shopB", PHONE)
        assert len(mine_a) == 1 and mine_a[0]["tenant"] == "shopA"
        assert len(mine_b) == 1 and mine_b[0]["tenant"] == "shopB"

    asyncio.run(run())


def test_cannot_stop_renewal_or_force_end_another_tenants_membership():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, memberships = _services(store)
        rA = await _membership_resource(resources, tenant="shopA", quantity=1)
        await joins.ensure_pending("shopA", PHONE)
        await joins.approve("shopA", PHONE)
        m = await memberships.join("shopA", resource_id=rA.id, phone=PHONE)

        with pytest.raises(MembershipError):
            await memberships.stop_renewal("shopB", m["id"])
        with pytest.raises(MembershipError):
            await memberships.force_end("shopB", m["id"], acknowledged=True, ack_by="x")

    asyncio.run(run())
