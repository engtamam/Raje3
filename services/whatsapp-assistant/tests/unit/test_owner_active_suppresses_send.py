"""ingest_inbound_message's own coexistence check — the message is always ingested/attributed, only
the SEND is held back while the owner is active (app/core/owner_presence.py)."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.inbound_store.datastore_backed import build as build_inbound_store
from app.core.inbound_ingest import ingest_inbound_message
from app.core.owner_presence import note_owner_reply
from app.ports.consent_gate import ALLOWED, ConsentVerdict

TENANT = "shop1"
FROM = "+966500000000"


def run(c):
    return asyncio.run(c)


class _NullCustomerLookup:
    async def resolve(self, tenant, phone):
        return {"found": False, "subject_ref": "", "visit_count_90d": 0}


@dataclass
class _ReplyPlan:
    kind: str = "text"
    text: str = "رد الذكاء الاصطناعي"
    list_button_text: str = ""
    list_rows: list | None = None


class _TextReplyEngine:
    async def handle_inbound_text(self, *, tenant, subject_ref, from_number, text, branch_id=""):
        return _ReplyPlan()


class _RecordingSender:
    def __init__(self):
        self.sent: list[str] = []

    async def send_template(self, **kwargs):
        self.sent.append(kwargs.get("to", ""))
        return "wamid_out"

    async def send_list(self, **kwargs):
        self.sent.append(kwargs.get("to", ""))
        return "wamid_out"


class _AllowConsentGate:
    async def check(self, *, tenant, subject, purpose):
        return ConsentVerdict(status=ALLOWED, reason="test", purpose=purpose)


@dataclass
class _RateLimiter:
    async def check(self, *a, **kw):
        @dataclass
        class _V:
            allowed: bool = True
        return _V()


@dataclass
class _FakeContainer:
    datastore: MemoryDataStore
    inbound_store: object
    customer_lookup: object = field(default_factory=_NullCustomerLookup)
    engine: object = field(default_factory=_TextReplyEngine)
    sender: object = field(default_factory=_RecordingSender)
    consent_gate: object = field(default_factory=_AllowConsentGate)
    rate_limiter: object = field(default_factory=_RateLimiter)
    points_summary: object = None


class _NullLogger:
    def warning(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


class _FakeSettings:
    PII_SALT = "salt"
    CONSENT_PURPOSE = "whatsapp_ai_assistant"
    CONSENT_POLICY_ON_UNKNOWN = "fail_open"
    CONVERSATION_OUTBOUND_MAX_PER_10MIN = 999
    OUTBOUND_MAX_PER_NUMBER_PER_HOUR = 999


def _container():
    store = MemoryDataStore()
    return _FakeContainer(datastore=store, inbound_store=build_inbound_store(store))


def test_a_normal_reply_sends_when_the_owner_is_not_active():
    c = _container()
    result = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_FakeSettings(), auditor=None,
        tenant=TENANT, wamid="w1", from_number=FROM, kind="text", text="hi", reply_id="",
        raw_payload={}))
    assert result["processed"] is True
    assert c.sender.sent == [FROM]


def test_the_send_is_suppressed_while_the_owner_is_active_but_the_message_still_processes():
    c = _container()
    run(note_owner_reply(c, tenant=TENANT, contact=FROM, now=int(time.time()),
                         cooldown_seconds=1800))
    result = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_FakeSettings(), auditor=None,
        tenant=TENANT, wamid="w1", from_number=FROM, kind="text", text="hi", reply_id="",
        raw_payload={}))
    # THE CONVERSATION STILL ADVANCES — dedup'd, attributed, marked processed — only the outbound
    # send never happened. A caller checking `processed` alone must not mistake this for a drop.
    assert result["processed"] is True
    assert c.sender.sent == []


def test_a_different_customer_of_the_same_tenant_is_unaffected():
    c = _container()
    run(note_owner_reply(c, tenant=TENANT, contact="+9665_other", now=int(time.time()),
                         cooldown_seconds=1800))
    result = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_FakeSettings(), auditor=None,
        tenant=TENANT, wamid="w1", from_number=FROM, kind="text", text="hi", reply_id="",
        raw_payload={}))
    assert result["processed"] is True
    assert c.sender.sent == [FROM]
