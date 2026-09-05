"""Booking a PACKAGE through the WhatsApp chat itself — check_availability/propose_booking take an
optional package_id (mutually exclusive with service_id), and execute_confirmed_proposal dispatches
to `hold_and_confirm_package` on button confirm. Real-driver only (ConfigDrivenAvailabilityProvider
has no concept of a package) — a deployment on the config driver refuses cleanly, never crashes.
"""
from __future__ import annotations

import datetime as dt
import time

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.points import NullPointsSummary
from app.ports.booking_provider import Slot

TENANT = "t1"
ALLOWED = frozenset({"check_availability", "propose_booking"})


class _FakeRealProvider:
    """A stand-in for RealBookingProvider — carries the two package-only methods, same shape as
    the real one, so tools.py's `getattr` dispatch is exercised properly."""
    driver = "real"

    def __init__(self, *, slots: list[Slot], confirm_answer: dict | None = None) -> None:
        self._slots = slots
        self._confirm_answer = confirm_answer or {"id": "bkg_1"}
        self.confirm_calls: list[dict] = []

    async def availability(self, **kwargs) -> list[Slot]:
        raise AssertionError("plain availability() must not be called for a package request")

    async def hold_and_confirm(self, **kwargs) -> dict:
        raise AssertionError("plain hold_and_confirm() must not be called for a package request")

    async def availability_for_package(self, *, tenant: str, package_id: str, earliest: int,
                                       branch_id: str = "", exclude_booking_id: str = "") -> list[Slot]:
        return [s for s in self._slots if s.starts_at >= earliest]

    async def hold_and_confirm_package(self, **kwargs) -> dict:
        self.confirm_calls.append(kwargs)
        return self._confirm_answer


def _cfg() -> BookingConfig:
    return BookingConfig(
        business_hours={d: ["09:00-11:00"] for d in
                        ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        default_duration_minutes=30, concurrency=1, max_lead_days=7,
        slot_granularity_minutes=30, service_durations={})


def _iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


async def test_check_availability_for_a_package_uses_the_package_only_method():
    now = int(time.time())
    provider = _FakeRealProvider(slots=[Slot(starts_at=now + 3600, duration_minutes=0)])
    store = MemoryDataStore()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="check_availability",
        args={"package_id": "pkg1"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800)
    assert "المواعيد المتاحة" in result


async def test_check_availability_refuses_both_service_and_package_together():
    store = MemoryDataStore()
    provider = _FakeRealProvider(slots=[])
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="check_availability",
            args={"service_id": "svc1", "package_id": "pkg1"}, allowed_tools=ALLOWED, store=store,
            booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_check_availability_for_a_package_on_the_config_driver_refuses_cleanly():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="check_availability",
            args={"package_id": "pkg1"}, allowed_tools=ALLOWED, store=store,
            booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError as exc:
        assert "not available" in str(exc)


async def test_propose_booking_for_a_package_renders_a_proposal_carrying_package_id():
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[Slot(starts_at=starts_at, duration_minutes=0)])
    store = MemoryDataStore()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"package_id": "pkg1", "starts_at_iso": _iso(starts_at)}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800)
    assert isinstance(result, T.RenderedProposal)

    from app.core.models import PENDING_PROPOSALS
    row = await store.get(PENDING_PROPOSALS, result.proposal_id)
    assert row["args"]["package_id"] == "pkg1"
    assert "service_id" not in row["args"]


async def test_a_package_slot_that_no_longer_holds_is_rejected():
    now = int(time.time())
    provider = _FakeRealProvider(slots=[])          # nothing free — the day no longer offers it
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
            args={"package_id": "pkg1", "starts_at_iso": _iso(now + 3600)}, allowed_tools=ALLOWED,
            store=store, booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_confirming_a_package_proposal_calls_hold_and_confirm_package():
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[Slot(starts_at=starts_at, duration_minutes=0)])
    store = MemoryDataStore()

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"package_id": "pkg1", "starts_at_iso": _iso(starts_at)}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800)

    class _Auditor:
        async def record(self, *a, **kw) -> None:
            return None

    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
        booking_provider=provider, auditor=_Auditor(), idempotency_key="btn_1",
        branch_id="b1", from_number="+9665")

    assert result["kind"] == "booking"
    assert provider.confirm_calls[0]["package_id"] == "pkg1"


async def test_confirming_a_package_proposal_on_the_config_driver_refuses_cleanly():
    """A deployment that somehow had a package proposal rendered (should never happen given the
    checks above) must still refuse at confirm time rather than crash with an AttributeError."""
    now = int(time.time())
    starts_at = now + 3600
    store = MemoryDataStore()
    from app.core.models import PENDING_PROPOSALS, PendingProposal, as_row
    proposal = PendingProposal(
        id="prp_x", tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
        tool="propose_booking", args={"package_id": "pkg1", "starts_at": starts_at},
        validated_snapshot={"validated_at": now}, created_at=now, expires_at=now + 1800)
    await store.put(PENDING_PROPOSALS, proposal.id, as_row(proposal))

    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())

    class _Auditor:
        async def record(self, *a, **kw) -> None:
            return None

    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.id, store=store, booking_provider=provider,
            auditor=_Auditor(), idempotency_key="btn_1", branch_id="b1", from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError as exc:
        assert "not available" in str(exc)


# ── deep robustness pass (100-test confidence sweep) ─────────────────────────────────────────────

async def test_check_availability_with_neither_service_nor_package_is_rejected():
    store = MemoryDataStore()
    provider = _FakeRealProvider(slots=[])
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="check_availability",
            args={}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_propose_booking_with_neither_service_nor_package_is_rejected():
    now = int(time.time())
    store = MemoryDataStore()
    provider = _FakeRealProvider(slots=[])
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
            args={"starts_at_iso": _iso(now + 3600)}, allowed_tools=ALLOWED, store=store,
            booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_propose_booking_refuses_both_service_and_package_together():
    now = int(time.time())
    store = MemoryDataStore()
    provider = _FakeRealProvider(slots=[Slot(starts_at=now + 3600, duration_minutes=0)])
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
            args={"service_id": "svc1", "package_id": "pkg1", "starts_at_iso": _iso(now + 3600)},
            allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_a_package_proposal_can_still_carry_a_real_reward_id():
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[Slot(starts_at=starts_at, duration_minutes=0)])
    store = MemoryDataStore()

    class _PointsWithOffer:
        async def offers(self, *, tenant: str, subject_ref: str) -> list[dict]:
            return [{"reward_id": "r1", "reward_name": "غسيل مجاني"}]

    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"package_id": "pkg1", "starts_at_iso": _iso(starts_at), "reward_id": "r1"},
        allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=_PointsWithOffer(), proposal_ttl_seconds=1800)

    from app.core.models import PENDING_PROPOSALS
    row = await store.get(PENDING_PROPOSALS, result.proposal_id)
    assert row["args"]["package_id"] == "pkg1"
    assert row["args"]["reward_id"] == "r1"


async def test_confirming_a_package_booking_passes_the_reward_id_through():
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[Slot(starts_at=starts_at, duration_minutes=0)])
    store = MemoryDataStore()

    class _PointsWithOffer:
        async def offers(self, *, tenant: str, subject_ref: str) -> list[dict]:
            return [{"reward_id": "r1", "reward_name": "غسيل مجاني"}]

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"package_id": "pkg1", "starts_at_iso": _iso(starts_at), "reward_id": "r1"},
        allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=_PointsWithOffer(), proposal_ttl_seconds=1800)

    class _Auditor:
        async def record(self, *a, **kw) -> None:
            return None

    await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_Auditor(), idempotency_key="btn_1", branch_id="b1", from_number="+9665")
    assert provider.confirm_calls[0]["intended_reward_id"] == "r1"


async def test_a_double_tap_confirm_on_a_package_proposal_only_confirms_once():
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[Slot(starts_at=starts_at, duration_minutes=0)])
    store = MemoryDataStore()

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"package_id": "pkg1", "starts_at_iso": _iso(starts_at)}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800)

    class _Auditor:
        async def record(self, *a, **kw) -> None:
            return None

    await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_Auditor(), idempotency_key="btn_1", branch_id="b1", from_number="+9665")
    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, auditor=_Auditor(), idempotency_key="btn_1",
            branch_id="b1", from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError as exc:
        assert "consumed" in str(exc)
    assert len(provider.confirm_calls) == 1
