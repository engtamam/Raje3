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
from app.core.models import CONVERSATIONS, ConversationState, as_row
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


async def _shown(store, subject_ref, *item_ids):
    """Seed the conversation as if a carousel naming these item_ids was just sent — the real
    precondition `_handle_carousel_pick`/`_handle_slot_pick` now require (whatsapp-assistant-003,
    QA audit 2026-09-12) before either reply-id is honoured."""
    conv = ConversationState(tenant=TENANT, subject_ref=subject_ref, state="idle",
                             shown_carousel_ids=list(item_ids))
    await store.put(CONVERSATIONS, f"{TENANT}|{subject_ref}", as_row(conv))


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
    store = MemoryDataStore()
    engine = _engine(provider, store=store)
    await _shown(store, "sub1", "srv_1")

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:srv_1", auditor=None)

    assert plan.kind == "interactive"
    assert plan.proposal is not None
    assert len(plan.proposal.buttons) == 2


async def test_multiple_slots_render_a_list_the_customer_picks_from():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    engine = _engine(provider, store=store)
    await _shown(store, "sub1", "svc1")

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:svc1", auditor=None)

    assert plan.kind == "list"
    assert plan.list_rows
    assert all(row["id"].startswith("slotpick:service:svc1:") for row in plan.list_rows)


async def test_picking_a_slot_from_the_list_renders_the_same_confirm_proposal():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    engine = _engine(provider, store=store)
    await _shown(store, "sub1", "svc1")
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
    await _shown(store, "sub1", "svc1")

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
    store = MemoryDataStore()
    engine = _engine(provider, store=store)
    await _shown(store, "sub1", "srv_1")

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:srv_1", auditor=None)

    assert plan.kind == "text"
    assert "لا توجد مواعيد" in plan.text


async def test_a_package_carousel_pick_uses_availability_for_package():
    now = int(time.time())
    provider = _SingleSlotProvider(package_slot=Slot(starts_at=now + 3600, duration_minutes=30))
    store = MemoryDataStore()
    engine = _engine(provider, store=store)
    await _shown(store, "sub1", "pkg_1")

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:package:pkg_1", auditor=None)

    assert plan.kind == "interactive"


async def test_a_malformed_carousel_id_is_refused_not_an_unhandled_exception():
    provider = _SingleSlotProvider()
    store = MemoryDataStore()
    engine = _engine(provider, store=store)
    await _shown(store, "sub1", "svc1")

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


# ── whatsapp-assistant-003: the id must be bound to what THIS session was actually shown ────────
async def test_a_carousel_id_for_an_item_this_session_was_never_shown_is_refused():
    now = int(time.time())
    provider = _SingleSlotProvider(slot=Slot(starts_at=now + 3600, duration_minutes=30))
    store = MemoryDataStore()
    engine = _engine(provider, store=store)
    await _shown(store, "sub1", "some_other_service")

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:srv_1", auditor=None)

    assert plan.kind == "text"
    assert plan.text == "هذا الخيار لم يعد صالحًا."


async def test_a_carousel_id_probed_before_any_carousel_was_ever_shown_is_refused():
    """A fresh conversation (never shown any carousel at all — `shown_carousel_ids` empty) must
    refuse the id exactly the same way as one shown a DIFFERENT item."""
    now = int(time.time())
    provider = _SingleSlotProvider(slot=Slot(starts_at=now + 3600, duration_minutes=30))
    engine = _engine(provider)

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:srv_1", auditor=None)

    assert plan.kind == "text"
    assert plan.text == "هذا الخيار لم يعد صالحًا."


async def test_a_slotpick_id_for_an_item_this_session_was_never_shown_is_refused():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    engine = _engine(provider, store=store)
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    target = slots[0]
    await _shown(store, "sub1", "some_other_service")

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1",
        reply_id=f"slotpick:service:svc1:{target.starts_at}", auditor=None)

    assert plan.kind == "text"
    assert plan.text == "هذا الخيار لم يعد صالحًا."


# ── register_carousel_shown (2026-09-13) — the door a campaign's own carousel walks through ─────
#
# A campaign's carousel (services/campaigns) is sent OUTSIDE any live conversation this engine
# ever ran — the customer was never triaged, `_shown` above was never called for them. This is the
# write that makes the SAME binding check `_handle_carousel_pick` already enforces pass for a card
# that arrived that way instead.
async def test_registering_shown_ids_lets_a_cold_customer_tap_the_carousel_button():
    now = int(time.time())
    provider = _SingleSlotProvider(slot=Slot(starts_at=now + 3600, duration_minutes=30))
    store = MemoryDataStore()
    engine = _engine(provider, store=store)

    # NO PRIOR SESSION AT ALL for this subject — a customer who never texted the bot.
    await engine.register_carousel_shown(tenant=TENANT, subject_ref="sub1", item_ids=["srv_1"])

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:srv_1", auditor=None)

    assert plan.kind == "interactive"
    assert plan.proposal is not None


async def test_an_id_never_registered_still_refuses_even_after_registering_a_different_one():
    now = int(time.time())
    provider = _SingleSlotProvider(slot=Slot(starts_at=now + 3600, duration_minutes=30))
    store = MemoryDataStore()
    engine = _engine(provider, store=store)

    await engine.register_carousel_shown(tenant=TENANT, subject_ref="sub1",
                                         item_ids=["some_other_service"])

    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="carousel:service:srv_1", auditor=None)

    assert plan.kind == "text"
    assert plan.text == "هذا الخيار لم يعد صالحًا."


async def test_registering_merges_onto_ids_the_model_itself_already_showed():
    """A customer already mid-conversation, shown one carousel by the model, must not lose those
    cards off the list when a campaign also targets them — only ADDS."""
    store = MemoryDataStore()
    await _shown(store, "sub1", "model_shown")
    provider = _SingleSlotProvider(slot=Slot(starts_at=int(time.time()) + 3600, duration_minutes=30))
    engine = _engine(provider, store=store)

    await engine.register_carousel_shown(tenant=TENANT, subject_ref="sub1",
                                         item_ids=["campaign_shown"])

    conv = await engine._get(TENANT, "sub1")           # noqa: SLF001 — reading internal test state
    assert set(conv.shown_carousel_ids) == {"model_shown", "campaign_shown"}


async def test_branch_id_is_stamped_only_on_a_brand_new_row():
    store = MemoryDataStore()
    provider = _SingleSlotProvider()
    engine = _engine(provider, store=store)

    await engine.register_carousel_shown(tenant=TENANT, subject_ref="sub_new",
                                         item_ids=["srv_1"], branch_id="br_campaign")
    conv = await engine._get(TENANT, "sub_new")        # noqa: SLF001
    assert conv.branch_id == "br_campaign"


async def test_branch_id_never_overwrites_an_existing_conversations_own_branch():
    store = MemoryDataStore()
    conv = ConversationState(tenant=TENANT, subject_ref="sub_old", state="idle",
                             branch_id="br_from_real_chat")
    await store.put(CONVERSATIONS, f"{TENANT}|sub_old", as_row(conv))
    provider = _SingleSlotProvider()
    engine = _engine(provider, store=store)

    await engine.register_carousel_shown(tenant=TENANT, subject_ref="sub_old",
                                         item_ids=["srv_1"], branch_id="br_campaign")
    reloaded = await engine._get(TENANT, "sub_old")    # noqa: SLF001
    assert reloaded.branch_id == "br_from_real_chat"
