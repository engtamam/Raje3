"""WhatsApp Direct Ordering -- true end-to-end: `ingest_inbound_message` itself (the real top-level
entry point app/main.py's bus subscription calls), wired to a REAL `ConversationEngine`, not a fake
one -- consent, dedup, the order-licence gate, the order flow's own state machine, and the final
`sender.send_text` call all participate together, exactly as they would in production. Every other
test in this package exercises one layer at a time; this file proves the seam between them."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.inbound_store.datastore_backed import build as build_inbound_store
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.inbound_ingest import ingest_inbound_message
from app.core.points import NullPointsSummary
from app.ports.consent_gate import ALLOWED, ConsentVerdict

TENANT = "shop_e2e"
FROM = "+966500000000"


def run(c):
    return asyncio.run(c)


class _FakeOrders:
    def __init__(self, *, pay_url: str = "https://pay.example/r/e2e", discount_minor: int = 0,
                discount_source: str = ""):
        self.calls: list[dict] = []
        self._pay_url = pay_url
        self._discount_minor = discount_minor
        self._discount_source = discount_source

    async def create(self, **kwargs):
        from app.ports.orders import CreatedOrder
        self.calls.append(kwargs)
        return CreatedOrder(order_id="ord_e2e000001", branch_id="br1", total_minor=5000,
                           pay_url=self._pay_url, discount_minor=self._discount_minor,
                           discount_source=self._discount_source)


class _NullCustomerLookup:
    async def resolve(self, tenant, phone):
        return {"found": False, "subject_ref": "", "visit_count_90d": 0}


class _AllowConsentGate:
    async def check(self, *, tenant, subject, purpose):
        return ConsentVerdict(status=ALLOWED, reason="test", purpose=purpose)


class _RecordingSender:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_template(self, **kwargs):
        self.sent.append({**kwargs, "_method": "send_template"})
        return "dlv_1"

    async def send_list(self, **kwargs):
        self.sent.append({**kwargs, "_method": "send_list"})
        return "dlv_1"

    async def send_location_request(self, **kwargs):
        self.sent.append({**kwargs, "_method": "send_location_request"})
        return "dlv_1"


@dataclass
class _Container:
    datastore: MemoryDataStore
    inbound_store: object
    engine: object
    customer_lookup: object = field(default_factory=_NullCustomerLookup)
    sender: object = field(default_factory=_RecordingSender)
    consent_gate: object = field(default_factory=_AllowConsentGate)
    rate_limiter: object = None
    points_summary: object = None
    licence: object = None


class _MemoryRateLimiter:
    async def check(self, *a, **kw):
        @dataclass
        class _V:
            allowed: bool = True
        return _V()


class _NullLogger:
    def warning(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


class _Settings:
    PII_SALT = "salt"
    CONSENT_PURPOSE = "whatsapp_ai_assistant"
    CONSENT_PURPOSE_ORDERING = "whatsapp_catalog_ordering"
    CONSENT_POLICY_ON_UNKNOWN = "fail_open"
    CONVERSATION_OUTBOUND_MAX_PER_10MIN = 999
    OUTBOUND_MAX_PER_NUMBER_PER_HOUR = 999


def _real_engine(store, *, orders=None, order_licence=None):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    return ConversationEngine(
        store=store, llm=None, booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=4,
        allowed_tools=frozenset(), orders=orders or _FakeOrders(), order_licence=order_licence)


def _container(*, orders=None, order_licence=None):
    store = MemoryDataStore()
    engine = _real_engine(store, orders=orders, order_licence=order_licence)
    return _Container(datastore=store, inbound_store=build_inbound_store(store), engine=engine,
                      rate_limiter=_MemoryRateLimiter())


def _order_payload(items, catalog_id="cat1"):
    return json.dumps({"catalog_id": catalog_id,
                       "items": [{"retailer_id": r, "quantity": q} for r, q in items]})


def test_the_full_customer_journey_cart_to_pay_link_through_the_real_dispatch_pipeline():
    """Order message arrives -> the real engine asks for a location (never the LLM, never a
    chat reply) -> the location arrives -> the real engine creates the order and the pay link is
    the ACTUAL text handed to the sender -- no layer mocked out except the operations peer call
    itself."""
    orders = _FakeOrders(pay_url="https://pay.example/r/final")
    c = _container(orders=orders)

    r1 = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_Settings(), auditor=None,
        tenant=TENANT, wamid="wamid_order", from_number=FROM, kind="order",
        text=_order_payload([("srv1", 2)]), reply_id="", raw_payload={"wamid": "wamid_order"}))
    assert r1["processed"] is True
    assert len(c.sender.sent) == 1
    assert c.sender.sent[0]["_method"] == "send_location_request"

    r2 = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_Settings(), auditor=None,
        tenant=TENANT, wamid="wamid_location", from_number=FROM, kind="location",
        text="24.7136,46.6753", reply_id="", raw_payload={"wamid": "wamid_location"}))
    assert r2["processed"] is True
    assert len(c.sender.sent) == 2
    final = c.sender.sent[1]
    assert final["_method"] == "send_template"
    assert "https://pay.example/r/final" in final["variables"][0]
    assert "استلام" not in final["variables"][0]

    # THE PEER CALL ITSELF GOT THE REAL CART AND THE ORDER MESSAGE'S OWN wamid, NOT THE
    # LOCATION'S -- idempotency must identify the cart, never the delivery attempt.
    assert orders.calls[0]["items"] == [("srv1", 2)]
    assert orders.calls[0]["idempotency_key"] == "wamid_order"


def test_a_discount_the_customer_is_holding_is_never_dropped_from_the_pay_message():
    """A discount reaches operations' response and must reach the customer's own message, never
    only the pay link -- the owner's own rule against advertising an unenforceable discount
    applies equally to under-communicating a REAL one."""
    orders = _FakeOrders(pay_url="https://pay.example/r/disc", discount_minor=2_000,
                        discount_source="campaign:snd_1")
    c = _container(orders=orders)

    run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_Settings(), auditor=None,
        tenant=TENANT, wamid="wamid_order2", from_number=FROM, kind="order",
        text=_order_payload([("srv1", 1)]), reply_id="", raw_payload={"wamid": "wamid_order2"}))
    run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_Settings(), auditor=None,
        tenant=TENANT, wamid="wamid_location2", from_number=FROM, kind="location",
        text="24.7136,46.6753", reply_id="", raw_payload={"wamid": "wamid_location2"}))

    final = c.sender.sent[-1]
    assert "https://pay.example/r/disc" in final["variables"][0]
    assert "20.00" in final["variables"][0] and "خصم" in final["variables"][0]


def test_a_webhook_redelivery_of_the_order_message_itself_is_deduplicated_before_it_ever_reaches_the_engine():
    """Meta's own at-least-once delivery guarantee can redeliver the ORDER message itself (not
    just the location) -- `inbound_store.record_if_new` must stop the duplicate before the engine
    ever sees it a second time, independent of anything `handle_order` itself does."""
    c = _container()
    r1 = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_Settings(), auditor=None,
        tenant=TENANT, wamid="wamid_dup", from_number=FROM, kind="order",
        text=_order_payload([("srv1", 1)]), reply_id="", raw_payload={"wamid": "wamid_dup"}))
    r2 = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_Settings(), auditor=None,
        tenant=TENANT, wamid="wamid_dup", from_number=FROM, kind="order",
        text=_order_payload([("srv1", 1)]), reply_id="", raw_payload={"wamid": "wamid_dup"}))
    assert r1["processed"] is True
    assert r2 == {"processed": False, "reason": "duplicate"}
    assert len(c.sender.sent) == 1, "the duplicate webhook must never produce a second reply"


def test_an_unsubscribed_shop_produces_true_silence_through_the_full_pipeline():
    class _RefuseLicence:
        async def allowed(self, tenant):
            return False

    c = _container(order_licence=_RefuseLicence())
    r = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_Settings(), auditor=None,
        tenant=TENANT, wamid="wamid_order", from_number=FROM, kind="order",
        text=_order_payload([("srv1", 1)]), reply_id="", raw_payload={"wamid": "wamid_order"}))
    assert r["processed"] is True
    assert c.sender.sent == [], "an unsubscribed shop's customer must receive nothing at all"
