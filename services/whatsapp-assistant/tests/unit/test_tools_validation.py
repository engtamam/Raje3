"""core/tools.py — the server-side re-validation gate rejects a stale/invalid model proposal."""
import time

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.points import NullPointsSummary

TENANT = "t1"
ALLOWED = frozenset({"check_availability", "propose_booking", "get_customer_points_summary",
                     "suggest_redeemable_offer"})


def _cfg() -> BookingConfig:
    return BookingConfig(
        business_hours={d: ["09:00-11:00"] for d in
                        ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        default_duration_minutes=30, concurrency=1, max_lead_days=7,
        slot_granularity_minutes=30, service_durations={})


async def test_propose_booking_for_real_available_slot_renders_interactive_proposal():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    target = slots[0]
    import datetime as dt
    iso = dt.datetime.fromtimestamp(target.starts_at, dt.timezone.utc).isoformat()

    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": iso}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800)

    assert isinstance(result, T.RenderedProposal)
    assert len(result.buttons) == 2
    assert result.proposal_id in result.buttons[0]["id"]


async def test_propose_booking_for_a_slot_that_does_not_exist_is_rejected():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    # A time deep in the middle of the night, outside business hours — the model hallucinated it.
    bogus = int(time.time()) + 3 * 86400
    import datetime as dt
    iso = dt.datetime.fromtimestamp(bogus, dt.timezone.utc).replace(hour=3).isoformat()

    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
            args={"service_id": "svc1", "starts_at_iso": iso}, allowed_tools=ALLOWED, store=store,
            booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_tool_outside_allowlist_is_rejected_even_if_it_has_a_handler():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="get_customer_points_summary",
            args={}, allowed_tools=frozenset({"check_availability"}), store=store,
            booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_execute_confirmed_proposal_rejects_a_slot_that_filled_after_proposal():
    """A slot re-validated at proposal time can still fill before the customer taps confirm — the
    gap this test exercises. execute_confirmed_proposal must re-check AGAIN, not trust the earlier
    validated_snapshot."""
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    target = slots[0]
    import datetime as dt
    iso = dt.datetime.fromtimestamp(target.starts_at, dt.timezone.utc).isoformat()

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": iso}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800)

    # SOMEONE ELSE took the slot between the proposal and this customer's confirm tap.
    await provider.hold_and_confirm(tenant=TENANT, subject_ref="someone-else", service_id="svc1",
                                    starts_at=target.starts_at, idempotency_key="race-winner")

    class _FakeAuditor:
        async def record(self, *a, **kw):
            pass

    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, redeemer=None, auditor=_FakeAuditor(),
            idempotency_key="btn_1")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_execute_confirmed_proposal_rejects_unknown_or_cross_tenant_proposal():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())

    class _FakeAuditor:
        async def record(self, *a, **kw):
            pass

    try:
        await T.execute_confirmed_proposal(
            tenant="tenant-B", proposal_id="prp_does_not_exist", store=store,
            booking_provider=provider, redeemer=None, auditor=_FakeAuditor(),
            idempotency_key="btn_x")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass
