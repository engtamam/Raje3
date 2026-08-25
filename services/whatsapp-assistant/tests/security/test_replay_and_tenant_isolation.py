"""Replay protection (wamid dedup) and tenant isolation."""
import time

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.inbound_store.datastore_backed import DataStoreInboundMessageStore
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.models import CONVERSATIONS


async def test_redelivered_wamid_is_dropped_not_reprocessed():
    """The bus is non-durable and at-most-once, but a redelivery can still happen (two replicas
    both subscribed, a retry). The SECOND delivery of the same wamid must be recognisable as a
    duplicate before any conversation state changes."""
    store = MemoryDataStore()
    inbound = DataStoreInboundMessageStore(store)

    first = await inbound.record_if_new("t1", "wamid_ABC123", {"text": "hi", "from": "+9665"})
    second = await inbound.record_if_new("t1", "wamid_ABC123", {"text": "hi", "from": "+9665"})

    assert first is True
    assert second is False


async def test_wamid_uniqueness_is_scoped_per_tenant_key_but_never_confused_cross_tenant():
    store = MemoryDataStore()
    inbound = DataStoreInboundMessageStore(store)
    a = await inbound.record_if_new("tenant-A", "wamid_shared", {"text": "hi"})
    b = await inbound.record_if_new("tenant-B", "wamid_shared", {"text": "hi"})
    # Meta's wamid is globally unique in practice, but the store keys on (tenant, wamid) anyway —
    # never trusting that global uniqueness is this service's OWN safety property to hold.
    assert a is True
    assert b is True   # two different tenants, not treated as the same message


async def test_availability_provider_never_returns_another_tenants_confirmed_bookings():
    store = MemoryDataStore()
    cfg = BookingConfig(business_hours={d: ["09:00-11:00"] for d in
                                        ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
                        default_duration_minutes=30, concurrency=1, max_lead_days=7,
                        slot_granularity_minutes=30, service_durations={})
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=cfg)
    now = int(time.time())
    slots = await provider.availability(tenant="tenant-A", service_id="wash", earliest=now,
                                        horizon_days=7)
    target = slots[0]
    await provider.hold_and_confirm(tenant="tenant-A", subject_ref="subA", service_id="wash",
                                    starts_at=target.starts_at, idempotency_key="a1")

    # tenant-B's availability for the SAME slot must be UNAFFECTED by tenant-A's booking.
    slots_b = await provider.availability(tenant="tenant-B", service_id="wash", earliest=now,
                                          horizon_days=7)
    assert target.starts_at in {s.starts_at for s in slots_b}


async def test_a_conversation_row_never_leaks_across_tenants_for_the_same_subject_ref():
    """Two different shops' customers could, in principle, hash to visually similar refs, but the
    datastore key is `tenant|subject_ref` — a query for one tenant's conversation must never
    return the other's row even if a caller reused a subject_ref by mistake."""
    store = MemoryDataStore()
    await store.put(CONVERSATIONS, "tenant-A|subX", {"tenant": "tenant-A", "subject_ref": "subX",
                                                     "state": "idle", "summary": "tenant A's data"})
    await store.put(CONVERSATIONS, "tenant-B|subX", {"tenant": "tenant-B", "subject_ref": "subX",
                                                     "state": "idle", "summary": "tenant B's data"})
    rows_a, _ = await store.find(CONVERSATIONS, {"tenant": "tenant-A"}, limit=10)
    assert len(rows_a) == 1
    assert rows_a[0]["summary"] == "tenant A's data"
