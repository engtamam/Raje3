"""consent_gate — the first real caller of app/ports/consent_gate.py anywhere on this platform.

Every other service wired the port (adapter, container field, registry entry) and never actually
asked — see the port's own docstring. This file proves app/core/inbound_ingest.py's own call
site: a DENIED verdict blocks processing before the engine or subject_ref ever exist, an UNKNOWN
verdict follows CONSENT_POLICY_ON_UNKNOWN's own declared posture, and an ALLOWED verdict changes
nothing about the flow every other suite already exercises.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.inbound_store.datastore_backed import build as build_inbound_store
from app.core.inbound_ingest import ingest_inbound_message
from app.ports.consent_gate import ALLOWED, DENIED, UNKNOWN, ConsentVerdict

TENANT = "shop1"


def run(c):
    return asyncio.run(c)


@dataclass
class _ReplyPlan:
    kind: str = "none"
    text: str = ""
    list_button_text: str = ""
    list_rows: list | None = None


class _RecordingEngine:
    def __init__(self):
        self.calls: list[tuple] = []

    async def handle_inbound_text(self, *, tenant, subject_ref, from_number, text):
        self.calls.append(("text", tenant, subject_ref, text))
        return _ReplyPlan(kind="none")

    async def handle_button_reply(self, *, tenant, subject_ref, reply_id, redeemer, auditor):
        self.calls.append(("button_reply", tenant, subject_ref, reply_id))
        return _ReplyPlan(kind="none")

    async def handle_triage_selection(self, *, tenant, subject_ref, reply_id):
        self.calls.append(("triage", tenant, subject_ref, reply_id))
        return _ReplyPlan(kind="none")


class _NullCustomerLookup:
    async def resolve(self, tenant, phone):
        return {"found": False, "subject_ref": "", "visit_count_90d": 0}


class _NullSender:
    async def send_template(self, **kwargs):
        return ""

    async def send_list(self, **kwargs):
        return ""


class _ScriptedConsentGate:
    """Answers whatever this test wants, and records exactly what it was asked — the difference
    between "we asked and got X" and "we never asked at all" (see the null adapter's own note)."""
    def __init__(self, status: str, reason: str = "test"):
        self.status = status
        self.reason = reason
        self.asked: list[tuple[str, str, str]] = []

    async def check(self, *, tenant, subject, purpose):
        self.asked.append((tenant, subject, purpose))
        return ConsentVerdict(status=self.status, reason=self.reason, purpose=purpose)


class _RecordingAuditor:
    def __init__(self):
        self.calls: list[tuple] = []

    async def record(self, action, **kwargs):
        self.calls.append((action, kwargs))


@dataclass
class _FakeContainer:
    datastore: MemoryDataStore
    inbound_store: object
    consent_gate: object
    customer_lookup: object = field(default_factory=_NullCustomerLookup)
    engine: object = field(default_factory=_RecordingEngine)
    sender: object = field(default_factory=_NullSender)
    points_summary: object = None


class _NullLogger:
    def warning(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


def _container(consent_gate):
    store = MemoryDataStore()
    return _FakeContainer(datastore=store, inbound_store=build_inbound_store(store),
                          consent_gate=consent_gate)


def _settings(policy_on_unknown: str = "fail_open"):
    class S:
        PII_SALT = "salt"
        CONSENT_PURPOSE = "whatsapp_ai_assistant"
        CONSENT_POLICY_ON_UNKNOWN = policy_on_unknown
    return S()


def _ingest(container, settings, auditor):
    return ingest_inbound_message(
        container=container, logger=_NullLogger(), settings=settings, auditor=auditor,
        tenant=TENANT, wamid="wamid_1", from_number="+966500000000", kind="text",
        text="hi", reply_id="", raw_payload={"wamid": "wamid_1"})


def test_denied_blocks_processing_before_the_engine_ever_sees_it():
    gate = _ScriptedConsentGate(DENIED, reason="withdrawn")
    c = _container(gate)
    result = run(_ingest(c, _settings(), auditor=None))
    assert result == {"processed": False, "reason": "consent_denied"}
    assert c.engine.calls == []


def test_denied_is_asked_with_the_raw_phone_not_a_pseudonym():
    """The port's own docstring is explicit: a service holding only subject_ref cannot use this
    port without defeating the pseudonymisation. This proves the RAW number is what gets asked,
    before subject_ref is ever derived."""
    gate = _ScriptedConsentGate(ALLOWED)
    c = _container(gate)
    run(_ingest(c, _settings(), auditor=None))
    assert gate.asked == [(TENANT, "+966500000000", "whatsapp_ai_assistant")]


def test_denied_is_never_overridable_by_the_unknown_policy():
    """fail_open only ever governs UNKNOWN — an on-record denial holds regardless."""
    gate = _ScriptedConsentGate(DENIED)
    c = _container(gate)
    result = run(_ingest(c, _settings(policy_on_unknown="fail_open"), auditor=None))
    assert result["reason"] == "consent_denied"
    assert c.engine.calls == []


def test_unknown_with_fail_open_proceeds_exactly_as_allowed_would():
    gate = _ScriptedConsentGate(UNKNOWN, reason="compliance-service unreachable")
    c = _container(gate)
    result = run(_ingest(c, _settings(policy_on_unknown="fail_open"), auditor=None))
    assert result == {"processed": True, "reason": ""}
    assert len(c.engine.calls) == 1


def test_unknown_with_fail_closed_blocks_processing():
    gate = _ScriptedConsentGate(UNKNOWN, reason="compliance-service unreachable")
    c = _container(gate)
    result = run(_ingest(c, _settings(policy_on_unknown="fail_closed"), auditor=None))
    assert result == {"processed": False, "reason": "consent_unknown"}
    assert c.engine.calls == []


def test_allowed_reaches_the_engine_normally():
    gate = _ScriptedConsentGate(ALLOWED)
    c = _container(gate)
    result = run(_ingest(c, _settings(), auditor=None))
    assert result == {"processed": True, "reason": ""}
    assert len(c.engine.calls) == 1


def test_a_refusal_records_a_non_critical_audit_entry():
    gate = _ScriptedConsentGate(DENIED, reason="withdrawn")
    auditor = _RecordingAuditor()
    c = _container(gate)
    run(_ingest(c, _settings(), auditor=auditor))
    assert len(auditor.calls) == 1
    action, kwargs = auditor.calls[0]
    assert action == "whatsapp_assistant.consent_refused"
    assert kwargs["metadata"]["status"] == "denied"
    assert kwargs["metadata"]["reason"] == "withdrawn"


def test_a_refusal_is_still_marked_processed_so_it_is_never_retried_forever():
    """A denied/unknown-blocked message must not be redelivered on every catch-up sweep as if it
    were still pending — see app/core/inbound_ingest.py's own `finally: mark_processed` for the
    normal path; the refusal path needs the same guarantee, taken explicitly since it returns
    before reaching that `finally`."""
    gate = _ScriptedConsentGate(DENIED)
    c = _container(gate)
    run(_ingest(c, _settings(), auditor=None))
    row = run(c.inbound_store.get(TENANT, "wamid_1"))
    assert row is not None and row["processed"] is True
