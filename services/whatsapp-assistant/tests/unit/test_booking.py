from app.adapters.datastore.memory import MemoryDataStore
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider, SlotNoLongerAvailable

TENANT = "t1"


def _cfg(**overrides) -> BookingConfig:
    base = dict(
        business_hours={"mon": ["09:00-11:00"], "tue": ["09:00-11:00"], "wed": ["09:00-11:00"],
                        "thu": ["09:00-11:00"], "fri": ["09:00-11:00"], "sat": ["09:00-11:00"],
                        "sun": ["09:00-11:00"]},
        default_duration_minutes=30, concurrency=1, max_lead_days=7,
        slot_granularity_minutes=30, service_durations={})
    base.update(overrides)
    return BookingConfig(**base)


async def test_availability_offers_slots_within_business_hours():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    import time
    slots = await provider.availability(tenant=TENANT, service_id="svc1",
                                        earliest=int(time.time()), horizon_days=7)
    assert len(slots) > 0
    for s in slots:
        assert s.duration_minutes == 30


async def test_confirmed_booking_reduces_availability_at_capacity_one():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg(concurrency=1))
    import time
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    assert slots
    target = slots[0]
    await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub1", service_id="svc1",
                                    starts_at=target.starts_at, idempotency_key="idem1")
    slots_after = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                              horizon_days=7)
    assert target.starts_at not in {s.starts_at for s in slots_after}


async def test_hold_and_confirm_is_idempotent_on_key():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    import time
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    target = slots[0]
    b1 = await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub1", service_id="svc1",
                                         starts_at=target.starts_at, idempotency_key="same-key")
    b2 = await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub1", service_id="svc1",
                                         starts_at=target.starts_at, idempotency_key="same-key")
    assert b1["id"] == b2["id"]


async def test_hold_and_confirm_rejects_slot_filled_between_read_and_write():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg(concurrency=1))
    import time
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    target = slots[0]
    await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub1", service_id="svc1",
                                    starts_at=target.starts_at, idempotency_key="first")
    try:
        await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub2", service_id="svc1",
                                        starts_at=target.starts_at, idempotency_key="second")
        assert False, "expected SlotNoLongerAvailable"
    except SlotNoLongerAvailable:
        pass


async def test_hold_and_confirm_serializes_concurrent_confirms_for_the_same_slot():
    """Regression for a real race: `hold_and_confirm` used to be a non-atomic read-check-write, so
    two customers confirming the same slot at nearly the same instant could both pass the capacity
    check and both get confirmed, exceeding the shop's configured concurrency. The per-slot claim
    lock closes this — fixed 2026-09-12."""
    import asyncio

    class SlowFindStore(MemoryDataStore):
        """Forces a genuine event-loop yield inside the read-check-write window, so concurrent
        `hold_and_confirm` calls actually interleave instead of running back-to-back with no real
        contention (a plain in-memory store with no real I/O never yields on its own)."""
        async def find(self, *a, **kw):
            await asyncio.sleep(0.01)
            return await super().find(*a, **kw)

    store = SlowFindStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg(concurrency=1))
    import time
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    target = slots[0]

    async def _confirm(key: str):
        try:
            return await provider.hold_and_confirm(
                tenant=TENANT, subject_ref=key, service_id="svc1",
                starts_at=target.starts_at, idempotency_key=key)
        except SlotNoLongerAvailable:
            return None

    results = await asyncio.gather(_confirm("a"), _confirm("b"), _confirm("c"))
    confirmed = [r for r in results if r is not None]
    assert len(confirmed) == 1, f"concurrency=1 slot over-confirmed: {confirmed}"
