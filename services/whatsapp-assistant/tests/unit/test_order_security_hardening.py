"""WhatsApp Direct Ordering -- robustness/security hardening for the order-parsing and flow-
dispatch boundary (core/conversation.py). Every case here is a Meta webhook payload or a customer
message this service must never trust blindly: a tampered/buggy `order` payload, a replayed event,
or a message crafted to slip past the one-shot `awaiting_order_location` gate. See
test_order_flow.py for the happy-path/TTL/cancel coverage this file does not repeat."""
from __future__ import annotations

import json

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import (
    ConversationEngine, ORDER_LOCATION_TTL_SECONDS, _MAX_ORDER_ITEMS)
from app.core.points import NullPointsSummary

TENANT = "t1"
SUBJECT = "sub1"


class _FakeOrders:
    def __init__(self):
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        from app.ports.orders import CreatedOrder
        self.calls.append(kwargs)
        return CreatedOrder(order_id="ord_abc123", branch_id="br1", total_minor=5000,
                           pay_url="https://pay.example/r/x")


def _engine(store, *, orders=None):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    return ConversationEngine(
        store=store, llm=StubLlm(), booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=4,
        allowed_tools=frozenset(), orders=orders or _FakeOrders())


async def _order_rejected(payload: dict) -> None:
    store = MemoryDataStore()
    engine = _engine(store)
    plan = await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=json.dumps(payload), now=1000)
    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is False
    assert conv.pending_order_items == []


async def test_an_oversized_item_list_is_rejected_not_silently_truncated():
    payload = {"catalog_id": "cat1",
              "items": [{"retailer_id": f"s{i}", "quantity": 1}
                       for i in range(_MAX_ORDER_ITEMS + 1)]}
    await _order_rejected(payload)


async def test_exactly_the_maximum_item_count_is_still_accepted():
    store = MemoryDataStore()
    engine = _engine(store)
    payload = {"catalog_id": "cat1",
              "items": [{"retailer_id": f"s{i}", "quantity": 1}
                       for i in range(_MAX_ORDER_ITEMS)]}
    plan = await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT, text=json.dumps(payload), now=1000)
    assert plan.kind == "request_location"


async def test_a_zero_quantity_item_is_rejected():
    await _order_rejected({"catalog_id": "cat1",
                           "items": [{"retailer_id": "s1", "quantity": 0}]})


async def test_a_negative_quantity_item_is_rejected():
    await _order_rejected({"catalog_id": "cat1",
                           "items": [{"retailer_id": "s1", "quantity": -1}]})


async def test_a_quantity_given_as_a_string_is_rejected_not_coerced():
    """A string that merely LOOKS numeric must never slip through — this is the one boundary
    deciding what operations' own Pydantic model later sees."""
    await _order_rejected({"catalog_id": "cat1",
                           "items": [{"retailer_id": "s1", "quantity": "2"}]})


async def test_a_boolean_quantity_is_rejected():
    """`bool` is a subclass of `int` in Python -- `True`/`False` passing an `isinstance(x, int)`
    check is the exact trap this validation must not fall into."""
    await _order_rejected({"catalog_id": "cat1",
                           "items": [{"retailer_id": "s1", "quantity": True}]})


async def test_a_very_large_quantity_is_not_rejected_here_operations_owns_that_ceiling():
    """`MAX_LINE_QUANTITY` is operations' own number, the ONE place it is decided -- this layer
    only rejects shapes that could never be a real quantity, never duplicates that business limit
    (see `_MAX_ORDER_ITEMS`'s own module-level comment on why)."""
    store = MemoryDataStore()
    engine = _engine(store)
    plan = await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT,
        text=json.dumps({"catalog_id": "cat1",
                         "items": [{"retailer_id": "s1", "quantity": 999999}]}), now=1000)
    assert plan.kind == "request_location"


async def test_a_blank_retailer_id_is_rejected():
    await _order_rejected({"catalog_id": "cat1",
                           "items": [{"retailer_id": "   ", "quantity": 1}]})


async def test_a_non_string_retailer_id_is_rejected():
    await _order_rejected({"catalog_id": "cat1",
                           "items": [{"retailer_id": 12345, "quantity": 1}]})


async def test_a_non_dict_item_in_the_list_is_rejected():
    await _order_rejected({"catalog_id": "cat1", "items": ["srv1", "srv2"]})


async def test_a_non_list_items_field_is_rejected():
    await _order_rejected({"catalog_id": "cat1", "items": {"retailer_id": "s1", "quantity": 1}})


async def test_a_customer_supplied_price_field_is_silently_dropped_never_reaches_the_order():
    """The catalog is the ONLY source of price (see `inbound_parse.py`'s own docstring) -- a
    tampered payload naming its own `item_price` must not even survive parsing into
    `pending_order_items`, let alone reach `OrderService.create`."""
    store = MemoryDataStore()
    orders = _FakeOrders()
    engine = _engine(store, orders=orders)
    payload = {"catalog_id": "cat1",
              "items": [{"retailer_id": "s1", "quantity": 1, "item_price": "0.01"}]}
    await engine.handle_order(tenant=TENANT, subject_ref=SUBJECT, text=json.dumps(payload),
                              now=1000)
    await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753",
        from_number="+966500000000", wamid="w1", now=1100)
    assert orders.calls[0]["items"] == [("s1", 1)]


async def test_the_cancel_keyword_does_not_trigger_as_a_substring_of_a_longer_message():
    """`text.strip() in _ORDER_CANCEL_KEYWORDS` must be an EXACT match -- a customer typing
    "لا تلغي طلبي" (please don't cancel my order) containing the literal word must not be read as
    a cancel."""
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT,
        text=json.dumps({"catalog_id": "cat1", "items": [{"retailer_id": "s1", "quantity": 1}]}),
        now=1000)
    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="text", text="لا تلغي طلبي أرجوك", now=1100)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is True, "a substring match would have wrongly cancelled it"
    assert plan.kind == "text"


async def test_a_location_with_trailing_garbage_after_the_coordinates_is_rejected():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT,
        text=json.dumps({"catalog_id": "cat1", "items": [{"retailer_id": "s1", "quantity": 1}]}),
        now=1000)
    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753,extra_junk",
        now=1100)
    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_order_location is True, "a malformed location must not be accepted"


async def test_a_location_exactly_at_the_ttl_boundary_is_still_accepted_not_expired():
    """`now - pending_order_at > TTL` -- exactly AT the boundary (`==`) must still be live; only
    strictly PAST it expires."""
    store = MemoryDataStore()
    orders = _FakeOrders()
    engine = _engine(store, orders=orders)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT,
        text=json.dumps({"catalog_id": "cat1", "items": [{"retailer_id": "s1", "quantity": 1}]}),
        now=1000)
    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753",
        from_number="+966500000000", wamid="w1", now=1000 + ORDER_LOCATION_TTL_SECONDS)
    assert len(orders.calls) == 1, "exactly-at-the-boundary must still be treated as live"
    assert plan.text != ""


async def test_one_past_the_ttl_boundary_is_expired():
    store = MemoryDataStore()
    orders = _FakeOrders()
    engine = _engine(store, orders=orders)
    await engine.handle_order(
        tenant=TENANT, subject_ref=SUBJECT,
        text=json.dumps({"catalog_id": "cat1", "items": [{"retailer_id": "s1", "quantity": 1}]}),
        now=1000)
    plan = await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753",
        from_number="+966500000000", wamid="w1", now=1000 + ORDER_LOCATION_TTL_SECONDS + 1)
    assert len(orders.calls) == 0
    assert "انتهت" in plan.text


async def test_duplicate_retailer_ids_within_one_cart_are_kept_as_separate_lines_not_merged_here():
    """Merging duplicate lines is `OrderService.create`'s own job (priced, server-side) -- this
    layer must pass the cart through faithfully, never silently deduping/summing on its own."""
    store = MemoryDataStore()
    orders = _FakeOrders()
    engine = _engine(store, orders=orders)
    payload = {"catalog_id": "cat1",
              "items": [{"retailer_id": "s1", "quantity": 1}, {"retailer_id": "s1", "quantity": 2}]}
    await engine.handle_order(tenant=TENANT, subject_ref=SUBJECT, text=json.dumps(payload),
                              now=1000)
    await engine.handle_order_followup(
        tenant=TENANT, subject_ref=SUBJECT, kind="location", text="24.7136,46.6753",
        from_number="+966500000000", wamid="w1", now=1100)
    assert orders.calls[0]["items"] == [("s1", 1), ("s1", 2)]
