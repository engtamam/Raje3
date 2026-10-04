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

    async def handle_order_followup(self, *, tenant, subject_ref, kind, text, from_number="", wamid=""):
        return None

    async def handle_inbound_text(self, *, tenant, subject_ref, from_number, text, branch_id=""):
        self.calls.append(("text", tenant, subject_ref, text, branch_id))
        return _ReplyPlan(kind="none")

    async def handle_button_reply(self, *, tenant, subject_ref, reply_id, auditor, now=None):
        self.calls.append(("button_reply", tenant, subject_ref, reply_id))
        return _ReplyPlan(kind="none")

    async def handle_triage_selection(self, *, tenant, subject_ref, reply_id):
        self.calls.append(("triage", tenant, subject_ref, reply_id))
        return _ReplyPlan(kind="none")


class _NullCustomerLookup:
    async def resolve(self, tenant, phone):
        return {"found": False, "subject_ref": "", "visit_count_90d": 0}


class _NullSender:
    def __init__(self):
        self.interactive_calls: list[dict] = []

    async def send_template(self, **kwargs):
        return ""

    async def send_list(self, **kwargs):
        return ""

    async def send_interactive(self, **kwargs):
        self.interactive_calls.append(kwargs)
        return ""


class _ScriptedConsentGate:
    """Answers whatever this test wants, and records exactly what it was asked — the difference
    between "we asked and got X" and "we never asked at all" (see the null adapter's own note)."""
    def __init__(self, status: str, reason: str = "test"):
        self.status = status
        self.reason = reason
        self.asked: list[tuple[str, str, str]] = []
        self.recorded: list[tuple[str, str, str, bool]] = []

    async def check(self, *, tenant, subject, purpose):
        self.asked.append((tenant, subject, purpose))
        return ConsentVerdict(status=self.status, reason=self.reason, purpose=purpose)

    async def record(self, *, tenant, subject, purpose, granted):
        self.recorded.append((tenant, subject, purpose, granted))
        return True


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
    licence: object = None


class _ScriptedLicence:
    """Answers whatever this test wants — the OFF case standing in for
    `core/licence.py::ToggleGatedLicence.allowed()` returning False, whatever combination of a
    lapsed entitlement, `AI_ASSISTANT_ENABLED=false`, or a per-shop toggle produced it."""
    def __init__(self, allowed: bool):
        self._allowed = allowed
        self.asked: list[str] = []

    async def allowed(self, tenant: str) -> bool:
        self.asked.append(tenant)
        return self._allowed


class _NullLogger:
    def warning(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


def _container(consent_gate, licence=None):
    store = MemoryDataStore()
    return _FakeContainer(datastore=store, inbound_store=build_inbound_store(store),
                          consent_gate=consent_gate, licence=licence)


def _settings(policy_on_unknown: str = "fail_open"):
    class S:
        PII_SALT = "salt"
        CONSENT_PURPOSE = "whatsapp_ai_assistant"
        CONSENT_PURPOSE_ORDERING = "whatsapp_catalog_ordering"
        CONSENT_POLICY_ON_UNKNOWN = policy_on_unknown
    return S()


def _ingest(container, settings, auditor):
    return ingest_inbound_message(
        container=container, logger=_NullLogger(), settings=settings, auditor=auditor,
        tenant=TENANT, wamid="wamid_1", from_number="+966500000000", kind="text",
        text="hi", reply_id="", raw_payload={"wamid": "wamid_1"})


def test_denied_asks_explicitly_instead_of_reaching_the_engine():
    """2026-09-19: DENIED (never asked before, or an on-record refusal — compliance-service's own
    default-deny means both look identical) no longer silently drops the message. It sends the
    interactive service-consent request and stops — the engine never sees this turn at all."""
    gate = _ScriptedConsentGate(DENIED, reason="no_consent_record")
    c = _container(gate)
    result = run(_ingest(c, _settings(), auditor=None))
    assert result == {"processed": True, "reason": "consent_requested"}
    assert c.engine.calls == []
    assert len(c.sender.interactive_calls) == 1
    call = c.sender.interactive_calls[0]
    assert call["to"] == "+966500000000"
    ids = {b["id"] for b in call["buttons"]}
    assert ids == {"consent:agree", "consent:end"}


def test_denied_is_asked_with_the_raw_phone_not_a_pseudonym():
    """The port's own docstring is explicit: a service holding only subject_ref cannot use this
    port without defeating the pseudonymisation. This proves the RAW number is what gets asked,
    before subject_ref is ever derived."""
    gate = _ScriptedConsentGate(ALLOWED)
    c = _container(gate)
    run(_ingest(c, _settings(), auditor=None))
    assert gate.asked == [(TENANT, "+966500000000", "whatsapp_ai_assistant")]


def test_denied_is_never_overridable_by_the_unknown_policy():
    """fail_open only ever governs UNKNOWN — an on-record denial never silently proceeds either,
    it is always asked explicitly regardless of what CONSENT_POLICY_ON_UNKNOWN says."""
    gate = _ScriptedConsentGate(DENIED)
    c = _container(gate)
    result = run(_ingest(c, _settings(policy_on_unknown="fail_open"), auditor=None))
    assert result["reason"] == "consent_requested"
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


def test_a_per_branch_composite_tenant_is_split_before_anything_asks_consent():
    """Phase 1 of the branch work: `ingest_inbound_message` must split the composite
    `tenant:branch_id` sending-identity string BEFORE the real tenant is used anywhere — the
    consent check included. A gate asked with the raw composite string would be asking
    compliance-service about a tenant that does not exist."""
    gate = _ScriptedConsentGate(ALLOWED)
    c = _container(gate)
    result = run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_settings(), auditor=None,
        tenant="shop1:brn-jeddah", wamid="wamid_branch", from_number="+966500000000",
        kind="text", text="hi", reply_id="", raw_payload={"wamid": "wamid_branch"}))
    assert result == {"processed": True, "reason": ""}
    # ASKED WITH THE REAL TENANT, NOT THE COMPOSITE — the whole point of splitting before the
    # consent check, not after.
    assert gate.asked == [("shop1", "+966500000000", "whatsapp_ai_assistant")]
    # AND THE ENGINE RECEIVES BOTH HALVES SEPARATELY: the real tenant as `tenant`, the branch as
    # its own field — never the composite string leaking through as if it were a tenant id.
    assert len(c.engine.calls) == 1
    kind, tenant, subject_ref, text, branch_id = c.engine.calls[0]
    assert (kind, tenant, text, branch_id) == ("text", "shop1", "hi", "brn-jeddah")


def test_a_central_shops_plain_tenant_reaches_the_engine_with_an_empty_branch():
    gate = _ScriptedConsentGate(ALLOWED)
    c = _container(gate)
    run(ingest_inbound_message(
        container=c, logger=_NullLogger(), settings=_settings(), auditor=None,
        tenant="shop1", wamid="wamid_central", from_number="+966500000000",
        kind="text", text="hi", reply_id="", raw_payload={"wamid": "wamid_central"}))
    assert gate.asked == [("shop1", "+966500000000", "whatsapp_ai_assistant")]
    kind, tenant, subject_ref, text, branch_id = c.engine.calls[0]
    assert (tenant, branch_id) == ("shop1", "")


def test_an_allowed_message_records_attribution_never_the_text():
    """A message that actually gets processed still writes an audit line — tenant, this
    customer's own pseudonym, the wamid — so it can still be attributed after
    CHAT_RETENTION_DAYS purges the message's own content. Never the text itself."""
    gate = _ScriptedConsentGate(ALLOWED)
    auditor = _RecordingAuditor()
    c = _container(gate)
    run(_ingest(c, _settings(), auditor=auditor))
    assert len(auditor.calls) == 1
    action, kwargs = auditor.calls[0]
    assert action == "whatsapp_assistant.message_attributed"
    assert kwargs["tenant"] == "shop1"
    assert kwargs["resource"].startswith("wamid:")
    # THE ACTOR IS THE PSEUDONYM, and it is the only identifying thing in the whole call —
    # nowhere in the recorded kwargs does the raw phone number or the message text appear.
    assert "actor" in kwargs and kwargs["actor"]
    assert "+9665" not in str(kwargs)
    assert "hi" not in str(kwargs.get("metadata", {}))


def test_a_consent_request_records_a_non_critical_audit_entry():
    gate = _ScriptedConsentGate(DENIED, reason="no_consent_record")
    auditor = _RecordingAuditor()
    c = _container(gate)
    run(_ingest(c, _settings(), auditor=auditor))
    assert len(auditor.calls) == 1
    action, kwargs = auditor.calls[0]
    assert action == "whatsapp_assistant.consent_requested"
    assert kwargs["metadata"]["reason"] == "no_consent_record"


def test_a_consent_request_is_still_marked_processed_so_it_is_never_retried_forever():
    """A message that triggered the consent request must not be redelivered on every catch-up
    sweep as if it were still pending — see app/core/inbound_ingest.py's own
    `finally: mark_processed` for the normal path; this gate needs the same guarantee, taken
    explicitly since it returns before reaching that `finally`."""
    gate = _ScriptedConsentGate(DENIED)
    c = _container(gate)
    run(_ingest(c, _settings(), auditor=None))
    row = run(c.inbound_store.get(TENANT, "wamid_1"))
    assert row is not None and row["processed"] is True


# ── the customer's own live reply to the consent request ──────────────────────────────────────
def _ingest_reply(container, settings, auditor, reply_id):
    return ingest_inbound_message(
        container=container, logger=_NullLogger(), settings=settings, auditor=auditor,
        tenant=TENANT, wamid="wamid_2", from_number="+966500000000", kind="button_reply",
        text="", reply_id=reply_id, raw_payload={"wamid": "wamid_2"})


def test_tapping_agree_records_the_grant_and_reaches_the_engine_the_same_turn():
    gate = _ScriptedConsentGate(DENIED)  # irrelevant here — a `consent:*` reply never calls check()
    c = _container(gate)
    result = run(_ingest_reply(c, _settings(), auditor=None, reply_id="consent:agree"))
    assert result == {"processed": True, "reason": ""}
    assert len(c.engine.calls) == 1
    assert gate.recorded == [(TENANT, "+966500000000", "whatsapp_ai_assistant", True)]


def test_tapping_end_records_the_withdrawal_and_never_reaches_the_engine():
    gate = _ScriptedConsentGate(DENIED)
    auditor = _RecordingAuditor()
    c = _container(gate)
    result = run(_ingest_reply(c, _settings(), auditor=auditor, reply_id="consent:end"))
    assert result == {"processed": False, "reason": "consent_denied"}
    assert c.engine.calls == []
    assert gate.recorded == [(TENANT, "+966500000000", "whatsapp_ai_assistant", False)]
    action, kwargs = auditor.calls[0]
    assert action == "whatsapp_assistant.consent_refused"
    assert kwargs["metadata"]["reason"] == "customer_declined"


def test_a_failed_record_call_never_blocks_the_customers_own_answer_from_taking_effect():
    """The write to compliance-service is best-effort here — a subject who just tapped «متابعة»
    must not be stuck re-answering the same prompt forever because of a transient record()
    failure; the customer's own turn proceeds regardless, exactly like every other best-effort
    audit call in this file."""
    class _BrokenRecord(_ScriptedConsentGate):
        async def record(self, **kwargs):
            raise RuntimeError("compliance-service down")

    gate = _BrokenRecord(DENIED)
    c = _container(gate)
    result = run(_ingest_reply(c, _settings(), auditor=None, reply_id="consent:agree"))
    assert result == {"processed": True, "reason": ""}
    assert len(c.engine.calls) == 1


# ── the licence/toggle kill switch — must be checked BEFORE `_GATES`, never inside them ─────────
def test_licence_off_never_sends_a_consent_request_or_records_anything():
    """2026-09-19 fix: a toggled-off tenant's brand-new customer used to still get a real
    `send_interactive` consent ask and a real `consent_gate.check()` call, before this tenant's
    licence was ever consulted. `core/licence.py::ToggleGatedLicence`'s own docstring is explicit
    that OFF must read exactly like never-subscribed — an unsubscribed shop's stranger never gets
    asked anything either."""
    gate = _ScriptedConsentGate(DENIED)  # would ask/send if ever reached
    licence = _ScriptedLicence(allowed=False)
    c = _container(gate, licence=licence)
    result = run(_ingest(c, _settings(), auditor=None))
    assert licence.asked == [TENANT]
    assert gate.asked == []
    assert gate.recorded == []
    assert c.sender.interactive_calls == []
    # Falls through to the engine exactly as an allowed tenant would — `conversation.py`'s own
    # door gate is what actually answers a disallowed tenant, not a new refusal invented here.
    assert len(c.engine.calls) == 1


def test_licence_on_reaches_consent_exactly_as_before():
    """No regression for the ordinary path: an allowed tenant still goes through `_gate_consent`
    unchanged."""
    gate = _ScriptedConsentGate(DENIED, reason="no_consent_record")
    licence = _ScriptedLicence(allowed=True)
    c = _container(gate, licence=licence)
    result = run(_ingest(c, _settings(), auditor=None))
    assert licence.asked == [TENANT]
    assert result == {"processed": True, "reason": "consent_requested"}
    assert len(c.sender.interactive_calls) == 1


def test_no_licence_wired_behaves_exactly_as_before_this_fix():
    """`container.licence` is `None` on a deployment with no licence adapter wired at all (tests,
    local runs) — must behave exactly as it did before this fix, never refuse."""
    gate = _ScriptedConsentGate(ALLOWED)
    c = _container(gate, licence=None)
    result = run(_ingest(c, _settings(), auditor=None))
    assert result == {"processed": True, "reason": ""}
    assert len(c.engine.calls) == 1
