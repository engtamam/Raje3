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
            booking_provider=provider, auditor=_FakeAuditor(),
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
            booking_provider=provider, auditor=_FakeAuditor(),
            idempotency_key="btn_x")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


# ── request_mobile_visit / check_mobile_visit_hours ─────────────────────────────────────────────
class _FakeServiceCatalog:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    async def list_active(self, tenant: str) -> list[dict]:
        return [{"id": sid, "name": sid} for sid in self._ids]


# 2026-09-14 is a Monday in Riyadh time — real anchors for the working-hours tests below.
_MONDAY_NOON_ISO = "2026-09-14T12:00:00+03:00"
_MONDAY_NOON_EPOCH = 1789376400
_MONDAY_11PM_ISO = "2026-09-14T23:00:00+03:00"
_SUNDAY_NOON_ISO = "2026-09-13T12:00:00+03:00"

_OPEN_MON_TO_SAT = {
    str(d): {"closed": False, "start_minute": 9 * 60, "end_minute": 21 * 60} for d in range(6)
} | {"6": {"closed": True, "start_minute": 0, "end_minute": 0}}


class _FakeMobileRequests:
    """Same shape as app/ports/mobile_requests.py — only `.hours()` is exercised here, `.create`
    is core/conversation.py::handle_location's own concern (see test_mobile_visit_flow.py)."""

    def __init__(self, weekly: dict | None) -> None:
        self._weekly = weekly

    async def hours(self, tenant: str) -> dict | None:
        return self._weekly


async def test_request_mobile_visit_for_real_services_returns_a_location_request_not_a_proposal():
    store = MemoryDataStore()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="request_mobile_visit",
        args={"service_ids": ["svc_wash", "svc_wax"], "starts_at_iso": _MONDAY_NOON_ISO},
        allowed_tools=frozenset({"request_mobile_visit"}), store=store, booking_provider=None,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        service_catalog=_FakeServiceCatalog(["svc_wash", "svc_wax"]),
        mobile_requests=_FakeMobileRequests(_OPEN_MON_TO_SAT))

    assert isinstance(result, T.MobileLocationRequest)
    assert result.service_ids == ["svc_wash", "svc_wax"]
    assert result.requested_time == _MONDAY_NOON_EPOCH
    # NEVER a PendingProposal — nothing here is confirmable by a button yet, so nothing should
    # have been written to the store at all.
    assert await store.get("wa_pending_proposals", "anything") is None


async def test_request_mobile_visit_rejects_a_service_id_the_catalogue_does_not_have():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
            tool="request_mobile_visit",
            args={"service_ids": ["svc_invented"], "starts_at_iso": _MONDAY_NOON_ISO},
            allowed_tools=frozenset({"request_mobile_visit"}), store=store, booking_provider=None,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            service_catalog=_FakeServiceCatalog(["svc_wash"]))
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_request_mobile_visit_requires_at_least_one_service_id():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
            tool="request_mobile_visit",
            args={"service_ids": [], "starts_at_iso": _MONDAY_NOON_ISO},
            allowed_tools=frozenset({"request_mobile_visit"}), store=store, booking_provider=None,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            service_catalog=_FakeServiceCatalog(["svc_wash"]))
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_request_mobile_visit_requires_a_real_starts_at_iso():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
            tool="request_mobile_visit", args={"service_ids": ["svc_wash"]},
            allowed_tools=frozenset({"request_mobile_visit"}), store=store, booking_provider=None,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            service_catalog=_FakeServiceCatalog(["svc_wash"]))
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_request_mobile_visit_with_no_catalogue_wired_is_refused_not_a_crash():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
            tool="request_mobile_visit",
            args={"service_ids": ["svc_wash"], "starts_at_iso": _MONDAY_NOON_ISO},
            allowed_tools=frozenset({"request_mobile_visit"}), store=store, booking_provider=None,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, service_catalog=None)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_request_mobile_visit_rejects_a_time_outside_working_hours():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
            tool="request_mobile_visit",
            args={"service_ids": ["svc_wash"], "starts_at_iso": _MONDAY_11PM_ISO},
            allowed_tools=frozenset({"request_mobile_visit"}), store=store, booking_provider=None,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            service_catalog=_FakeServiceCatalog(["svc_wash"]),
            mobile_requests=_FakeMobileRequests(_OPEN_MON_TO_SAT))
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_request_mobile_visit_rejects_a_time_on_a_closed_day():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
            tool="request_mobile_visit",
            args={"service_ids": ["svc_wash"], "starts_at_iso": _SUNDAY_NOON_ISO},
            allowed_tools=frozenset({"request_mobile_visit"}), store=store, booking_provider=None,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            service_catalog=_FakeServiceCatalog(["svc_wash"]),
            mobile_requests=_FakeMobileRequests(_OPEN_MON_TO_SAT))
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_request_mobile_visit_with_no_hours_peer_wired_skips_the_check():
    """Same fail-open posture operations' own validate_requested_time() documents — an
    unreachable/unconfigured peer must not block every proposal, only leave the final check to
    operations' own create() once the location arrives."""
    store = MemoryDataStore()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="request_mobile_visit",
        args={"service_ids": ["svc_wash"], "starts_at_iso": _MONDAY_11PM_ISO},
        allowed_tools=frozenset({"request_mobile_visit"}), store=store, booking_provider=None,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        service_catalog=_FakeServiceCatalog(["svc_wash"]), mobile_requests=None)
    assert isinstance(result, T.MobileLocationRequest)


async def test_check_mobile_visit_hours_formats_every_day():
    store = MemoryDataStore()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
        tool="check_mobile_visit_hours", args={},
        allowed_tools=frozenset({"check_mobile_visit_hours"}), store=store, booking_provider=None,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        mobile_requests=_FakeMobileRequests(_OPEN_MON_TO_SAT))
    assert isinstance(result, str)
    assert "09:00" in result and "21:00" in result
    assert "إجازة" in result   # Sunday, closed


async def test_check_mobile_visit_hours_with_no_peer_wired_is_refused_not_a_crash():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
            tool="check_mobile_visit_hours", args={},
            allowed_tools=frozenset({"check_mobile_visit_hours"}), store=store,
            booking_provider=None, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            mobile_requests=None)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_check_mobile_visit_hours_with_unreachable_peer_answers_honestly():
    store = MemoryDataStore()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
        tool="check_mobile_visit_hours", args={},
        allowed_tools=frozenset({"check_mobile_visit_hours"}), store=store, booking_provider=None,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        mobile_requests=_FakeMobileRequests(None))
    assert isinstance(result, str)
    assert "09:00" not in result   # no invented hours — an honest "cannot verify" instead
