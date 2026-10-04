"""WhatsApp Direct Ordering's Step 3: a catalog order (`kind="order"`) is received deterministically
(never through the LLM), asks for a location, and the next message is intercepted by
`handle_order_followup` until that location arrives, an explicit cancel, a fresh cart, or the
30-minute TTL settles it — mirrors test_mobile_visit_flow.py's own shape for the
mobile-visit-request flow this is deliberately NOT routed through."""
from __future__ import annotations

import json

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine, ORDER_LOCATION_TTL_SECONDS
from app.core.points import NullPointsSummary

TENANT = "t1"
SUBJECT = "sub1"


def _order_text(items: list[tuple[str, int]], catalog_id: str = "cat1") -> str:
    return json.dumps({"catalog_id": catalog_id,
                       "items": [{"retailer_id": r, "quantity": q} for r, q in items]})


class _FakeOrders:
    """Step 4's own peer -- see test_order_creation.py for the dedicated coverage of this call
    itself; this file only needs it to exist so handle_order_followup's location branch has
    somewhere real (if trivial) to call."""

    def __init__(self, *, fail: bool = False, pay_url: str = "https://pay.example/r/abc123"):
        self.calls: list[dict] = []
        self._fail = fail
        self._pay_url = pay_url

    async def create(self, **kwargs):
        from app.ports.orders import CreatedOrder, OrderFailed
        self.calls.append(kwargs)
        if self._fail:
            raise OrderFailed("لا يوجد فرع يغطي هذا الموقع")
        return CreatedOrder(order_id="ord_test123456", branch_id="br1", total_minor=5000,
                           pay_url=self._pay_url)


def _engine(store, *, orders=None):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    return ConversationEngine(
        store=store, llm=StubLlm(), booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=4,
        allowed_tools=frozenset(), orders=orders or _FakeOrders())


# ── handle_order ──────────────────────────────────────────────────────────────────────────────

async def test_a_real_order_asks_for_a_location_and_remembers_the_cart():
    store = MemoryDataStore()
    engine = _engine(store)

    plan = await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 2), ("srv2", 1)]), now=1000)

    assert plan.kind == "request_location"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is True
    assert conv.pending_order_items == [{"retailer_id": "srv1", "quantity": 2},
                                        {"retailer_id": "srv2", "quantity": 1}]
    assert conv.pending_order_catalog_id == "cat1"
    assert conv.pending_order_at == 1000


async def test_an_unreadable_order_payload_never_sets_any_pending_state():
    store = MemoryDataStore()
    engine = _engine(store)

    plan = await engine.handle_order(tenant=TENANT, subject_ref=SUBJECT, text="not json", now=1000)

    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_items == []


# ── handle_order_followup: pass-through when nothing is pending ────────────────────────────────

async def test_followup_returns_none_when_nothing_is_pending():
    store = MemoryDataStore()
    engine = _engine(store)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="text", text="مرحبا")

    assert plan is None


# ── handle_order_followup: the location arrives ─────────────────────────────────────────────────

async def test_sharing_the_location_clears_awaiting_and_stores_the_coordinates():
    store = MemoryDataStore()
    orders = _FakeOrders()
    engine = _engine(store, orders=orders)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000, )

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753",
        from_number="+966500000000", wamid="wamid_loc", now=1100)

    assert plan.kind == "text"
    # NEVER "تم استلام" -- the order is not received until it is paid; the pay link itself
    # must be in the very first reply.
    assert "استلام" not in plan.text
    assert "https://pay.example/r/abc123" in plan.text
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_lat == 24.7136
    assert conv.pending_order_lng == 46.6753
    # THE PENDING STATE IS FULLY CLEARED BEFORE THE PEER CALL -- the Order itself is now the
    # single source of truth for the cart, not the conversation record.
    assert conv.pending_order_items == []
    assert conv.pending_order_catalog_id == ""
    assert conv.pending_order_wamid == ""
    assert len(orders.calls) == 1
    assert orders.calls[0]["items"] == [("srv1", 1)]
    assert orders.calls[0]["lat"] == 24.7136
    assert orders.calls[0]["lng"] == 46.6753


async def test_the_order_wamid_used_for_idempotency_is_the_cart_message_not_the_location():
    store = MemoryDataStore()
    orders = _FakeOrders()
    engine = _engine(store, orders=orders)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), wamid="wamid_cart",
        now=1000)

    await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753",
        from_number="+966500000000", wamid="wamid_location_event", now=1100)

    assert orders.calls[0]["idempotency_key"] == "wamid_cart"


async def test_a_failed_order_creation_relays_the_refusal_and_still_clears_the_pending_state():
    store = MemoryDataStore()
    orders = _FakeOrders(fail=True)
    engine = _engine(store, orders=orders)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753",
        from_number="+966500000000", wamid="wamid_loc", now=1100)

    assert plan.kind == "text"
    # VERBATIM, NO PREFIX -- operations' own refusal (e.g. the geo-gate's "موقعك خارج نطاق
    # التوصيل") is already a complete, polite customer sentence; a "تعذّر إتمام طلبك:" prefix on
    # top of it read as two apologies stacked on a structural refusal, not a glitch.
    assert plan.text == "لا يوجد فرع يغطي هذا الموقع"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_items == []


class _RefuseLicence:
    async def allowed(self, tenant):
        return False


async def test_an_unsubscribed_tenant_is_refused_before_any_order_even_starts():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    engine = ConversationEngine(
        store=store, llm=StubLlm(), booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=4,
        allowed_tools=frozenset(), orders=_FakeOrders(), order_licence=_RefuseLicence())

    plan = await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    # SILENT, NOT A REFUSAL MESSAGE -- a shop that never bought this app must not have its
    # customer told anything exists to be refused from.
    assert plan.kind == "none"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_items == []


async def test_a_lapsed_subscription_refuses_an_already_pending_order_too():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    allow_then_refuse = _FakeOrders()
    engine = ConversationEngine(
        store=store, llm=StubLlm(), booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=4,
        allowed_tools=frozenset(), orders=allow_then_refuse, order_licence=None)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)
    engine._order_licence = _RefuseLicence()

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753", now=1100)

    assert plan.kind == "none"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_items == []
    assert allow_then_refuse.calls == []


async def test_a_created_order_with_no_pay_link_never_claims_the_order_was_received():
    """The order itself can exist (operations' own idempotency already recorded it) while the
    pay-link mint fails (no gateway connected, payments-service unreachable) -- the customer must
    be told to retry, never congratulated on an order that is not actually confirmed yet."""
    store = MemoryDataStore()
    orders = _FakeOrders(pay_url="")
    engine = _engine(store, orders=orders)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753",
        from_number="+966500000000", wamid="wamid_loc", now=1100)

    assert plan.kind == "text"
    assert "استلام" not in plan.text
    assert "تعذّر إنشاء رابط الدفع" in plan.text


async def test_with_no_orders_peer_wired_the_reply_says_so_plainly_not_a_silent_success():
    store = MemoryDataStore()
    engine = _engine(store, orders=None)
    engine._orders = None  # simulate a deployment where the peer was never configured
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753", now=1100)

    assert plan.kind == "text"
    assert "غير متاحة" in plan.text
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_items == []


async def test_an_unparseable_location_is_answered_plainly_state_unchanged():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="garbage", now=1100)

    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is True  # unchanged -- still waiting on a real one


async def test_an_out_of_range_location_is_refused_not_trusted():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="999,46.6753", now=1100)

    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is True


# ── handle_order_followup: explicit cancel ──────────────────────────────────────────────────────

async def test_the_cancel_keyword_clears_everything():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="text", text="إلغاء", now=1100)

    assert plan.kind == "text"
    assert "إلغاء" in plan.text
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_items == []
    assert conv.pending_order_catalog_id == ""


async def test_the_alternate_cancel_spelling_also_works():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="text", text="الغاء", now=1100)

    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False


# ── handle_order_followup: anything else gets a reminder, never silently dropped ────────────────

async def test_an_unrelated_message_gets_the_reminder_not_a_silent_ai_answer():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="text", text="كم السعر؟", now=1100)

    assert plan.kind == "text"
    assert "موقع" in plan.text
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is True  # still pending, nothing was lost


# ── handle_order_followup: a second cart replaces the first ────────────────────────────────────

async def test_a_fresh_order_while_pending_replaces_the_cart_and_resets_the_timer():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="order",
        text=_order_text([("srv2", 3)], catalog_id="cat1"), now=1100)

    assert plan.kind == "request_location"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is True
    assert conv.pending_order_items == [{"retailer_id": "srv2", "quantity": 3}]
    assert conv.pending_order_at == 1100


# ── handle_order_followup: the 30-minute TTL ────────────────────────────────────────────────────

async def test_an_expired_pending_order_refuses_a_late_location():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    late = 1000 + ORDER_LOCATION_TTL_SECONDS + 1
    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753", now=late)

    assert plan.kind == "text"
    assert "انتهت" in plan.text
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_lat == 0.0  # the late location was never actually used


async def test_an_expired_pending_order_lets_a_fresh_order_through_clean():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    late = 1000 + ORDER_LOCATION_TTL_SECONDS + 1
    followup = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="order", text=_order_text([("srv2", 1)]),
        now=late)
    # THE FOLLOWUP ITSELF CLEARS THE EXPIRED STATE AND DEFERS -- the caller
    # (inbound_ingest.py) is the one that then calls handle_order fresh, same as this test does.
    assert followup is None

    plan = await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv2", 1)]), now=late)
    assert plan.kind == "request_location"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.pending_order_items == [{"retailer_id": "srv2", "quantity": 1}]


async def test_an_order_never_touches_the_ai_assistants_own_session_state():
    """`conv.state`/`conv.session_closed_at` belong to the AI assistant's own state machine
    (`feature.whatsapp`, a separate app) -- a customer mid-AI-booking who also places a catalog
    order must not have that unrelated session silently closed by this flow."""
    store = MemoryDataStore()
    orders = _FakeOrders()
    engine = _engine(store, orders=orders)
    conv = await engine._get(TENANT, SUBJECT)
    conv.state = "awaiting_confirmation"
    conv.session_closed_at = 0
    await engine._save(conv)

    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "awaiting_confirmation"
    assert conv.session_closed_at == 0

    await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753", now=1100)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "awaiting_confirmation"
    assert conv.session_closed_at == 0


async def test_an_expired_pending_order_on_an_unrelated_message_just_falls_through():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=_order_text([("srv1", 1)]), now=1000)

    late = 1000 + ORDER_LOCATION_TTL_SECONDS + 1
    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="text", text="مرحبا", now=late)

    assert plan is None
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False  # the stale state was cleared regardless
