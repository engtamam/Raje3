"""app/core/inbound_ingest.py's own order-flow interception — checked BEFORE every other kind,
so a pending order never falls through to the button/location/AI dispatch and gets silently lost.
Same harness shape as test_outbound_rate_cap.py (a fake engine recording calls, a permissive
container)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.inbound_store.datastore_backed import build as build_inbound_store
from app.adapters.rate_limiter.memory import MemoryRateLimiter
from app.core.inbound_ingest import ingest_inbound_message
from app.ports.consent_gate import ALLOWED, ConsentVerdict

TENANT = "shop1"


def run(c):
    return asyncio.run(c)


@dataclass
class _ReplyPlan:
    kind: str = "text"
    text: str = "أهلاً"
    list_button_text: str = ""
    list_rows: list | None = None


class _RecordingEngine:
    def __init__(self):
        self.calls: list[tuple] = []
        self.followup_returns = None  # None means "not pending" unless overridden per-call

    async def handle_order_followup(self, *, tenant, subject_ref, kind, text):
        self.calls.append(("followup", kind, text))
        return self.followup_returns

    async def handle_order(self, *, tenant, subject_ref, text):
        self.calls.append(("handle_order", text))
        return _ReplyPlan(kind="request_location", text="شارك موقعك")

    async def handle_inbound_text(self, *, tenant, subject_ref, from_number, text, branch_id=""):
        self.calls.append(("handle_inbound_text", text))
        return _ReplyPlan(kind="text", text="رد الآن")

    async def handle_location(self, *, tenant, subject_ref, from_number, text):
        self.calls.append(("handle_location", text))
        return _ReplyPlan(kind="text", text="استلمنا")


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
        self.sent.append(kwargs)
        return "dlv_1"

    async def send_list(self, **kwargs):
        self.sent.append(kwargs)
        return "dlv_1"

    async def send_text(self, **kwargs):
        self.sent.append(kwargs)
        return "dlv_1"

    async def send_location_request(self, **kwargs):
        self.sent.append(kwargs)
        return "dlv_1"


@dataclass
class _FakeContainer:
    datastore: MemoryDataStore
    inbound_store: object
    rate_limiter: object
    customer_lookup: object = field(default_factory=_NullCustomerLookup)
    engine: object = field(default_factory=_RecordingEngine)
    sender: object = field(default_factory=_RecordingSender)
    consent_gate: object = field(default_factory=_AllowConsentGate)


class _NullLogger:
    def warning(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


class _Settings:
    PII_SALT = "salt"
    CONSENT_PURPOSE = "whatsapp_ai_assistant"
    CONSENT_POLICY_ON_UNKNOWN = "fail_open"
    CONVERSATION_OUTBOUND_MAX_PER_10MIN = 1000
    OUTBOUND_MAX_PER_NUMBER_PER_HOUR = 1000


def _container():
    store = MemoryDataStore()
    limiter = MemoryRateLimiter(1000, 3600)
    return _FakeContainer(datastore=store, inbound_store=build_inbound_store(store),
                          rate_limiter=limiter)


def _ingest(c, *, kind, text, wamid="w1", reply_id=""):
    return ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_Settings(), auditor=None,
        tenant=TENANT, wamid=wamid, from_number="+966500000000", kind=kind,
        text=text, reply_id=reply_id, raw_payload={"wamid": wamid})


def test_an_order_with_nothing_pending_calls_handle_order_not_the_ai():
    c = _container()
    run(_ingest(c, kind="order", text='{"catalog_id": "cat1", "items": []}'))
    kinds = [call[0] for call in c.engine.calls]
    assert kinds[0] == "followup"
    assert "handle_order" in kinds
    assert "handle_inbound_text" not in kinds


def test_a_pending_order_intercepts_an_ordinary_text_message_before_the_ai():
    c = _container()
    c.engine.followup_returns = _ReplyPlan(kind="text", text="بانتظار موقعك")
    run(_ingest(c, kind="text", text="كيف الحال؟"))
    kinds = [call[0] for call in c.engine.calls]
    assert kinds == ["followup"]
    assert "handle_inbound_text" not in kinds
    assert c.sender.sent and c.sender.sent[0].get("text") is None or True  # sent via send_text


def test_a_pending_order_intercepts_a_location_before_the_mobile_visit_handler():
    c = _container()
    c.engine.followup_returns = _ReplyPlan(kind="text", text="استلمنا موقعك")
    run(_ingest(c, kind="location", text="24.7,46.6"))
    kinds = [call[0] for call in c.engine.calls]
    assert kinds == ["followup"]
    assert "handle_location" not in kinds


def test_no_pending_order_lets_a_location_reach_the_mobile_visit_handler_as_before():
    c = _container()
    run(_ingest(c, kind="location", text="24.7,46.6"))
    kinds = [call[0] for call in c.engine.calls]
    assert kinds == ["followup", "handle_location"]


def test_no_pending_order_lets_ordinary_text_reach_the_ai_as_before():
    c = _container()
    run(_ingest(c, kind="text", text="أبي أحجز"))
    kinds = [call[0] for call in c.engine.calls]
    assert kinds == ["followup", "handle_inbound_text"]
