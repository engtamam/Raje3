"""A reward rides on a REAL booking now (`propose_booking`'s own `reward_id`), never a standalone
unconditional-on-confirm spend — the structural fix for a no-show costing the shop a reward with
nothing to show for it. `intended_reward_id` is INTENT ONLY, stamped on the booking; nothing is
actually spent until the shop marks the customer attended (bookings-service's own `attend()`,
unchanged by this service)."""
import time

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider

TENANT = "t1"
ALLOWED = frozenset({"propose_booking", "suggest_redeemable_offer"})


class _StaticPoints:
    driver = "static"

    def __init__(self, offers):
        self._offers = offers

    async def offers(self, *, tenant, subject_ref):
        return list(self._offers)

    async def redeemable_offer(self, *, tenant, subject_ref):
        return dict(self._offers[0]) if self._offers else None


class _RecordingBookingProvider:
    """Wraps a real ConfigDrivenAvailabilityProvider for availability(), but records every
    hold_and_confirm() call's kwargs — the thing this test actually needs to see."""
    driver = "recording"

    def __init__(self, inner):
        self._inner = inner
        self.confirm_calls: list[dict] = []

    async def availability(self, **kw):
        return await self._inner.availability(**kw)

    async def hold_and_confirm(self, **kw):
        self.confirm_calls.append(kw)
        return {"id": "bkg_1", "status": "booked"}


def _cfg() -> BookingConfig:
    return BookingConfig(
        business_hours={d: ["09:00-11:00"] for d in
                        ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        default_duration_minutes=30, concurrency=1, max_lead_days=7,
        slot_granularity_minutes=30, service_durations={})


def _iso(starts_at: int) -> str:
    import datetime as dt
    return dt.datetime.fromtimestamp(starts_at, dt.timezone.utc).isoformat()


class _FakeAuditor:
    async def record(self, *a, **kw):
        pass


async def test_suggest_redeemable_offer_is_read_only_no_proposal_no_buttons():
    store = MemoryDataStore()
    points = _StaticPoints([{"reward_id": "rwd1", "reward_name": "قهوة مجانية", "points": 100}])
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
        tool="suggest_redeemable_offer", args={}, allowed_tools=ALLOWED, store=store,
        booking_provider=None, points_summary=points, proposal_ttl_seconds=1800)
    assert isinstance(result, str)
    assert "قهوة مجانية" in result
    # NOTHING PERSISTED — a read-only tool leaves no PendingProposal behind at all.
    assert (await store.find("pending_proposals", {"tenant": TENANT}, limit=10))[0] == []


async def test_propose_booking_with_a_real_reward_id_attaches_it_as_intent():
    store = MemoryDataStore()
    inner = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    provider = _RecordingBookingProvider(inner)
    now = int(time.time())
    slots = await inner.availability(tenant=TENANT, service_id="svc1", earliest=now, horizon_days=7)
    target = slots[0]
    points = _StaticPoints([{"reward_id": "rwd1", "reward_name": "قهوة مجانية",
                             "points_cost": 50, "points_balance": 100, "expires_at": ""}])

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": _iso(target.starts_at), "reward_id": "rwd1"},
        allowed_tools=ALLOWED, store=store, booking_provider=provider, points_summary=points,
        proposal_ttl_seconds=1800)
    assert isinstance(proposal, T.RenderedProposal)
    assert "مكافأتك" in proposal.body

    await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
        booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_1",
        branch_id="brn-main", from_number="+9665")

    assert provider.confirm_calls[0]["intended_reward_id"] == "rwd1"


async def test_propose_booking_with_an_invalid_reward_id_still_proposes_the_booking():
    """A reward the model half-remembers, since spent or expired — dropped, never a reason to
    fail the whole booking."""
    store = MemoryDataStore()
    inner = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    provider = _RecordingBookingProvider(inner)
    now = int(time.time())
    slots = await inner.availability(tenant=TENANT, service_id="svc1", earliest=now, horizon_days=7)
    target = slots[0]
    points = _StaticPoints([])   # customer holds NO real offers any more

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": _iso(target.starts_at),
             "reward_id": "rwd_stale"},
        allowed_tools=ALLOWED, store=store, booking_provider=provider, points_summary=points,
        proposal_ttl_seconds=1800)
    assert isinstance(proposal, T.RenderedProposal)
    assert "تعذّر إرفاق" in proposal.body

    await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
        booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_1",
        branch_id="brn-main", from_number="+9665")
    assert provider.confirm_calls[0]["intended_reward_id"] == ""


async def test_propose_booking_with_no_reward_id_confirms_normally():
    store = MemoryDataStore()
    inner = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    provider = _RecordingBookingProvider(inner)
    now = int(time.time())
    slots = await inner.availability(tenant=TENANT, service_id="svc1", earliest=now, horizon_days=7)
    target = slots[0]

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": _iso(target.starts_at)},
        allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=_StaticPoints([]), proposal_ttl_seconds=1800)
    assert "مكافأتك" not in proposal.body and "تعذّر إرفاق" not in proposal.body

    await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
        booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_1",
        branch_id="brn-main", from_number="+9665")
    assert provider.confirm_calls[0]["intended_reward_id"] == ""
