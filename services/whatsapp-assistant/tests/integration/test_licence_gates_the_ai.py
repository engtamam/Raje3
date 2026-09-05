"""ConversationEngine wired to a licence — `feature.whatsapp` gates the AI assistant at TWO points
(core/licence.py's own docstring): as early as possible (before even the free triage list, since
the triage gate is itself part of the assistant, not an ordinary service message) and again right
before the LLM call, so a subscription that lapses mid-conversation stops the very next reply
rather than waiting for a fresh session.
"""
from __future__ import annotations

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.auditable_actions import AUDITABLE_ACTIONS
from app.core.audit import Auditor
from app.core.auditable import critical_actions, declared_actions, validate
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary

TENANT = "shop1"


def _provider(store):
    cfg = BookingConfig(business_hours={}, default_duration_minutes=30, concurrency=1,
                        max_lead_days=7, slot_granularity_minutes=15, service_durations={})
    return ConfigDrivenAvailabilityProvider(store=store, cfg=cfg)


def _auditor():
    class _Sink:
        driver = "http"

        def __init__(self):
            self.events = []

        async def emit(self, event):
            from app.ports.audit_sink import ACCEPTED, AuditReceipt
            self.events.append(event)
            return AuditReceipt(status=ACCEPTED, seq=len(self.events), hash="deadbeef")

    sink = _Sink()
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    auditor = Auditor(sink=sink, service="whatsapp-assistant",
                      critical_actions=critical_actions(actions),
                      declared_actions=declared_actions(actions), fail_closed=True)
    return auditor, sink


class _ToggleableLicence:
    """A licence whose answer can flip mid-test — standing in for a subscription that is bought,
    then lapses, between two turns of the same conversation."""
    driver = "fake"

    def __init__(self, allowed: bool) -> None:
        self.answer = allowed
        self.calls = 0

    async def allowed(self, tenant: str) -> bool:
        self.calls += 1
        return self.answer


def _engine(store, llm, licence, auditor=None, **overrides):
    kwargs = dict(store=store, llm=llm, booking_provider=_provider(store),
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=12,
                 allowed_tools=frozenset({"check_availability", "propose_booking",
                                         "get_customer_points_summary",
                                         "suggest_redeemable_offer"}),
                 auditor=auditor, licence=licence)
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


async def test_a_subscribed_shop_reaches_the_triage_list_as_normal():
    store = MemoryDataStore()
    licence = _ToggleableLicence(allowed=True)
    engine = _engine(store, StubLlm(), licence)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref="sub1", from_number="+9665", text="hi", now=1000)
    assert plan.kind == "list"
    assert licence.calls == 1


async def test_an_unsubscribed_shop_never_reaches_the_triage_list_and_no_state_is_saved():
    store = MemoryDataStore()
    licence = _ToggleableLicence(allowed=False)
    engine = _engine(store, StubLlm(), licence)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref="sub1", from_number="+9665", text="hi", now=1000)
    assert plan.kind == "text"
    assert "متوقفة" in plan.text
    # No conversation record was ever created — a shop that has not bought this must not
    # accumulate a session for it either.
    conv = await engine._get(TENANT, "sub1")
    assert conv.state == "idle"          # the fresh/never-seen default, untouched


async def test_a_subscription_that_lapses_mid_conversation_stops_the_next_reply():
    store = MemoryDataStore()
    licence = _ToggleableLicence(allowed=True)
    llm = StubLlm()
    auditor, sink = _auditor()
    engine = _engine(store, llm, licence, auditor=auditor)

    await engine.handle_inbound_text(tenant=TENANT, subject_ref="sub1", from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(
        tenant=TENANT, subject_ref="sub1", reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref="sub1", from_number="+9665",
                                 text="أبي أحجز غسيل", now=1010)

    # The subscription lapses NOW, before the debounce tick fires compose_reply.
    licence.answer = False

    reply = await engine.compose_reply(TENANT, "sub1", now=1200)
    assert reply.kind == "text"
    assert "متوقفة" in reply.text
    assert llm.calls == []               # the model was never called
    conv = await engine._get(TENANT, "sub1")
    assert conv.state == "closed"
    assert conv.licence_stopped is True
    stops = [e for e in sink.events if e.action == "whatsapp_assistant.stopped_not_subscribed"]
    assert len(stops) == 1
    assert stops[0].tenant == TENANT

    # A further tick for the same session does not re-record the same fact.
    again = await engine.compose_reply(TENANT, "sub1", now=1400)
    assert again.kind == "none"
    stops_after = [e for e in sink.events
                   if e.action == "whatsapp_assistant.stopped_not_subscribed"]
    assert len(stops_after) == 1


async def test_no_licence_configured_never_blocks():
    """Pre-existing test constructors and a deployment with no BILLING_SERVICE_URL both leave
    licence=None — must behave exactly as before this gate existed."""
    store = MemoryDataStore()
    engine = _engine(store, StubLlm(), licence=None)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref="sub1", from_number="+9665", text="hi", now=1000)
    assert plan.kind == "list"
