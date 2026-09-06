"""handle_button_reply's two new deterministic branches — "carousel:{kind}:{item_id}" (a carousel
card's own button) and "slotpick:{kind}:{item_id}:{starts_at}" (a time picked from the list the
first branch may show). Neither ever asks the model; both end at the SAME RenderedProposal/
confirm-cancel flow test_tools_validation.py already proves."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary
from app.ports.booking_provider import Slot

TENANT = "t1"
ALLOWED = frozenset({"propose_booking"})


def _cfg() -> BookingConfig:
    return BookingConfig(
        business_hours={d: ["09:00-11:00"] for d in
                        ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        default_duration_minutes=30, concurrency=1, max_lead_days=7,
        slot_granularity_minutes=30, service_durations={})


def _engine(provider, **overrides):
    kwargs = dict(store=MemoryDataStore(), llm=None, booking_provider=provider,
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=12, allowed_tools=ALLOWED)
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


@dataclass
class _SingleSlotProvider:
    """Mimics RealBookingProvider's own shape: availability() returns AT MOST ONE slot,
    regardless of how many are asked for."""
    driver = "real"
    slot: Slot | None = None
    package_slot: Slot | None = None

    async def availability(self, *, tenant, service_id, earliest, horizon_days, branch_id="",
                           exclude_booking_id=""):
        return [self.slot] if self.slot is not None else []

    async def availability_for_package(self, *, tenant, package_id, earliest, branch_id=""):
        return [self.package_slot] if self.package_slot is not None else []

    async def hold_and_confirm(self, **kwargs):
        return {"id": "bkg_1", "state": "confirmed"}


async def test_a_single_available_slot_skips_straight_to_a_confirm_proposal():
    now = int(time.time())
    provider = _SingleSlotProvider(slot=Slot(starts_at=now + 3600, duration_minutes=30))
    engine = _engine(provider)

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:srv_1", auditor=None)

    assert plan.kind == "interactive"
    assert plan.proposal is not None
    assert len(plan.proposal.buttons) == 2


async def test_multiple_slots_render_a_list_the_customer_picks_from():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    engine = _engine(provider, store=store)

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:svc1", auditor=None)

    assert plan.kind == "list"
    assert plan.list_rows
    assert all(row["id"].startswith("slotpick:service:svc1:") for row in plan.list_rows)


async def test_picking_a_slot_from_the_list_renders_the_same_confirm_proposal():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    engine = _engine(provider, store=store)
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    target = slots[0]

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1",
        reply_id=f"slotpick:service:svc1:{target.starts_at}", auditor=None)

    assert plan.kind == "interactive"
    assert plan.proposal is not None


async def test_a_slot_that_is_no_longer_available_is_refused_not_a_crash():
    """Re-validated exactly like an LLM-proposed slot — a stale list tapped minutes later must
    not be trusted just because the id parses."""
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    engine = _engine(provider, store=store)

    # 3am is outside the configured 09:00-11:00 business hours — never a real slot.
    fake_starts_at = int(time.time()) - (int(time.time()) % 86400) + 3 * 3600

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1",
        reply_id=f"slotpick:service:svc1:{fake_starts_at}", auditor=None)

    assert plan.kind == "text"
    assert "تعذّر" in plan.text


async def test_zero_available_slots_says_so_plainly():
    now = int(time.time())
    provider = _SingleSlotProvider(slot=None)
    engine = _engine(provider)

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:srv_1", auditor=None)

    assert plan.kind == "text"
    assert "لا توجد مواعيد" in plan.text


async def test_a_package_carousel_pick_uses_availability_for_package():
    now = int(time.time())
    provider = _SingleSlotProvider(package_slot=Slot(starts_at=now + 3600, duration_minutes=30))
    engine = _engine(provider)

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:package:pkg_1", auditor=None)

    assert plan.kind == "interactive"


async def test_a_malformed_carousel_id_is_refused_not_an_unhandled_exception():
    provider = _SingleSlotProvider()
    engine = _engine(provider)

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:gadget:x", auditor=None)
    assert plan.kind == "text"
    assert plan.text == "لم أفهم هذا الرد."

    plan2 = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="slotpick:service:svc1:notanumber", auditor=None)
    assert plan2.kind == "text"
    assert plan2.text == "لم أفهم هذا الرد."


async def test_ordinary_confirm_cancel_replies_are_completely_unaffected():
    """The pre-existing confirm/cancel logic must still be reached unchanged for any reply_id that
    is NOT "carousel:"/"slotpick:" prefixed."""
    engine = _engine(_SingleSlotProvider())
    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="prp_nonexistent:confirm", auditor=None)
    assert plan.kind == "text"
    assert plan.text == "هذا الطلب لم يعد صالحًا."
