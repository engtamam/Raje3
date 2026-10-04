"""InboundPoller — the durable catch-up sweep against notification-service's
GET /internal/whatsapp/inbound (platform v0.16.38, commit 31e556e).

THE REPLAY-SAFETY GUARANTEE THIS FILE EXISTS TO PROVE: a message delivered via BOTH the live bus
subscription (app/main.py) AND this catch-up sweep must be processed exactly once, never twice —
they dedup through the SAME inbound_store, keyed by wamid (see app/core/inbound_ingest.py).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.inbound_store.datastore_backed import build as build_inbound_store
from app.core.inbound_ingest import ingest_inbound_message
from app.core.inbound_poll import InboundPoller
from app.ports.consent_gate import ALLOWED, ConsentVerdict

TENANT = "shop1"


def run(c):
    return asyncio.run(c)


class _NullCustomerLookup:
    async def resolve(self, tenant, phone):
        return {"found": False, "subject_ref": "", "visit_count_90d": 0}


@dataclass
class _ReplyPlan:
    kind: str = "none"
    text: str = ""
    list_button_text: str = ""
    list_rows: list | None = None


class _RecordingEngine:
    """Records every distinct call it receives — a duplicate delivery reaching the engine twice
    is exactly what this suite must never see."""
    def __init__(self):
        self.calls: list[tuple] = []

    async def handle_order_followup(self, *, tenant, subject_ref, kind, text):
        return None

    async def handle_inbound_text(self, *, tenant, subject_ref, from_number, text, branch_id=""):
        self.calls.append(("text", tenant, subject_ref, text))
        return _ReplyPlan(kind="none")

    async def handle_button_reply(self, *, tenant, subject_ref, reply_id, redeemer, auditor):
        self.calls.append(("button_reply", tenant, subject_ref, reply_id))
        return _ReplyPlan(kind="none")

    async def handle_triage_selection(self, *, tenant, subject_ref, reply_id):
        self.calls.append(("triage", tenant, subject_ref, reply_id))
        return _ReplyPlan(kind="none")


class _NullSender:
    async def send_template(self, **kwargs):
        return ""

    async def send_list(self, **kwargs):
        return ""


class _AllowConsentGate:
    """This suite is about dedup/replay, not consent — always ALLOWED so ingest proceeds exactly
    as it did before consent_gate existed. See test_consent_gate (if added) for denial behavior."""
    async def check(self, *, tenant, subject, purpose):
        return ConsentVerdict(status=ALLOWED, reason="test", purpose=purpose)


@dataclass
class _FakeContainer:
    datastore: MemoryDataStore
    inbound_store: object
    customer_lookup: object = field(default_factory=_NullCustomerLookup)
    engine: object = field(default_factory=_RecordingEngine)
    sender: object = field(default_factory=_NullSender)
    consent_gate: object = field(default_factory=_AllowConsentGate)
    points_summary: object = None
    inbound_feed: object = None


class _NullLogger:
    def warning(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


class _FakeSettings:
    PII_SALT = "salt"
    CONSENT_PURPOSE = "whatsapp_ai_assistant"
    CONSENT_POLICY_ON_UNKNOWN = "fail_open"


def _container():
    store = MemoryDataStore()
    return _FakeContainer(datastore=store, inbound_store=build_inbound_store(store))


def _row(wamid: str, text: str = "hi", cursor: str = "c1"):
    return {"wamid": wamid, "from": "+966500000000", "tenant": TENANT,
            "message": {"type": "text", "text": {"body": text}}}


class _FakeFeed:
    """Serves fixed pages, one per call, then empties out — same contract as HttpInboundFeed."""
    configured = True

    def __init__(self, pages: list[dict]):
        self._pages = list(pages)

    async def messages(self, *, after: str = ""):
        if not self._pages:
            return {"messages": [], "cursor": after}
        return self._pages.pop(0)


def test_the_poller_ingests_a_page_and_persists_the_cursor_after_the_writes():
    c = _container()
    c.inbound_feed = _FakeFeed([{"messages": [_row("wamid_1")], "cursor": "cursor_1"}])
    poller = InboundPoller(container=c, settings=_FakeSettings(), logger=_NullLogger())

    result = run(poller.run(auditor=None))

    assert result == {"read": 1, "ingested": 1, "duplicates": 0, "pages": 1, "configured": True}
    assert c.engine.calls == [("text", TENANT, c.engine.calls[0][2], "hi")]
    assert run(c.datastore.get("wa_inbound_watermarks", "inbound_poll"))["cursor"] == "cursor_1"


def test_a_second_sweep_resumes_from_the_persisted_cursor():
    c = _container()
    c.inbound_feed = _FakeFeed([{"messages": [_row("wamid_1")], "cursor": "cursor_1"}])
    poller = InboundPoller(container=c, settings=_FakeSettings(), logger=_NullLogger())
    run(poller.run(auditor=None))

    seen_after = {}

    class _CapturingFeed(_FakeFeed):
        async def messages(self, *, after: str = ""):
            seen_after["after"] = after
            return await super().messages(after=after)

    c.inbound_feed = _CapturingFeed([{"messages": [], "cursor": "cursor_1"}])
    run(poller.run(auditor=None))
    assert seen_after["after"] == "cursor_1"


def test_a_message_delivered_via_both_the_bus_and_the_catchup_poll_is_processed_once():
    """THE SECURITY/REPLAY GUARANTEE. The bus handler (app/main.py) sees `wamid_dup` first and
    ingests it; the catch-up sweep later serves the SAME wamid (a message that lived on the bus
    and is now also being reconciled). It must be a no-op the second time — the engine must see
    exactly one call for this wamid, not two."""
    c = _container()

    # ── the bus path processes it first ────────────────────────────────────────────────────
    run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_FakeSettings(), auditor=None,
        tenant=TENANT, wamid="wamid_dup", from_number="+966500000000", kind="text",
        text="hi", reply_id="", raw_payload={"wamid": "wamid_dup"}))
    assert len(c.engine.calls) == 1

    # ── the catch-up sweep later serves the same wamid ─────────────────────────────────────
    c.inbound_feed = _FakeFeed([{"messages": [_row("wamid_dup")], "cursor": "cursor_1"}])
    poller = InboundPoller(container=c, settings=_FakeSettings(), logger=_NullLogger())
    result = run(poller.run(auditor=None))

    assert result["ingested"] == 0
    assert result["duplicates"] == 1
    assert len(c.engine.calls) == 1, "the engine must not see this wamid a second time"


def test_an_unreadable_feed_does_not_advance_the_cursor():
    c = _container()

    class _BrokenFeed:
        configured = True

        async def messages(self, *, after: str = ""):
            return {}

    c.inbound_feed = _BrokenFeed()
    poller = InboundPoller(container=c, settings=_FakeSettings(), logger=_NullLogger())
    result = run(poller.run(auditor=None))

    assert result == {"read": 0, "ingested": 0, "duplicates": 0, "pages": 0, "configured": True,
                      "unreadable": True}
    assert run(c.datastore.get("wa_inbound_watermarks", "inbound_poll")) is None


def test_not_configured_is_said_out_loud_not_a_silent_zero():
    c = _container()

    class _Unconfigured:
        configured = False

    c.inbound_feed = _Unconfigured()
    poller = InboundPoller(container=c, settings=_FakeSettings(), logger=_NullLogger())
    result = run(poller.run(auditor=None))

    assert result["configured"] is False
