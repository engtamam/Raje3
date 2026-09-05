"""OUTBOUND_MAX_PER_TENANT_PER_HOUR — the belt beside notification-service's own ceiling (see
config.py's own note on the setting). A runaway conversation loop or a bug that keeps re-proposing
the same reply must not spend a shop's whole WhatsApp allowance by itself. Proves the cap is
actually consulted by app/core/inbound_ingest.py's send path, not just declared.
"""
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
    async def handle_inbound_text(self, *, tenant, subject_ref, from_number, text, branch_id=""):
        return _ReplyPlan(kind="text", text="رد الآن")


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
    def __init__(self):
        self.warnings: list[tuple] = []

    def warning(self, msg, **kwargs):
        self.warnings.append((msg, kwargs))

    def info(self, *a, **k):
        pass


class _Settings:
    PII_SALT = "salt"
    CONSENT_PURPOSE = "whatsapp_ai_assistant"
    CONSENT_POLICY_ON_UNKNOWN = "fail_open"
    OUTBOUND_MAX_PER_TENANT_PER_HOUR = 1


def _container(limit=1):
    store = MemoryDataStore()
    limiter = MemoryRateLimiter(1000, 3600)
    return _FakeContainer(datastore=store, inbound_store=build_inbound_store(store),
                          rate_limiter=limiter)


def _ingest(c, logger, wamid="w1"):
    return ingest_inbound_message(
        container=c, logger=logger, settings=_Settings(), auditor=None,
        tenant=TENANT, wamid=wamid, from_number="+966500000000", kind="text",
        text="hi", reply_id="", raw_payload={"wamid": wamid})


def test_a_reply_under_the_cap_is_sent():
    c = _container()
    logger = _NullLogger()
    result = run(_ingest(c, logger, wamid="w1"))
    assert result == {"processed": True, "reason": ""}
    assert len(c.sender.sent) == 1


def test_a_reply_over_the_hourly_cap_is_capped_not_sent():
    """OUTBOUND_MAX_PER_TENANT_PER_HOUR=1 in _Settings — the second distinct inbound message in
    the same tenant/hour must not reach the sender at all."""
    c = _container()
    logger = _NullLogger()
    run(_ingest(c, logger, wamid="w1"))
    result = run(_ingest(c, logger, wamid="w2"))
    assert result == {"processed": True, "reason": ""}   # capped, not a processing failure
    assert len(c.sender.sent) == 1                        # the second send never happened
    assert any(msg == "whatsapp_outbound_capped" for msg, _ in logger.warnings)


def test_the_cap_is_a_separate_budget_per_tenant():
    c = _container()
    logger = _NullLogger()
    run(_ingest(c, logger, wamid="w1"))
    result = run(ingest_inbound_message(
        container=c, logger=logger, settings=_Settings(), auditor=None,
        tenant="shop2", wamid="w2", from_number="+966500000001", kind="text",
        text="hi", reply_id="", raw_payload={"wamid": "w2"}))
    assert result == {"processed": True, "reason": ""}
    assert len(c.sender.sent) == 2
