"""Full flow: fake inbound whatsapp.message event -> conversation state -> LLM proposes a tool
call (stub LLM) -> interactive message payload built correctly -> button reply -> the real
state-changing action executes -> Auditor recorded it.
"""
import time

from app.adapters.audit_sink.null import NullAuditSink
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.adapters.whatsapp_sender.direct import NullDirectSender
from app.auditable_actions import AUDITABLE_ACTIONS
from app.core.audit import Auditor
from app.core.auditable import critical_actions, declared_actions, validate
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary
from app.core.tools import RenderedProposal

TENANT = "shop1"
SUBJECT = "sub_customer_1"


def _booking_provider(store):
    cfg = BookingConfig(
        business_hours={d: ["09:00-11:00"] for d in
                        ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        default_duration_minutes=30, concurrency=1, max_lead_days=7,
        slot_granularity_minutes=30, service_durations={})
    return ConfigDrivenAvailabilityProvider(store=store, cfg=cfg)


class _AcceptingAuditSink:
    """A sink that DOES record — a receipt an Auditor treats as witnessed."""
    driver = "http"

    def __init__(self):
        self.events = []

    async def emit(self, event):
        from app.ports.audit_sink import ACCEPTED, AuditReceipt

        self.events.append(event)
        return AuditReceipt(status=ACCEPTED, seq=len(self.events), hash="deadbeef")


async def test_full_flow_from_inbound_message_to_confirmed_booking_and_audit_record():
    store = MemoryDataStore()
    provider = _booking_provider(store)
    llm = StubLlm()

    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=12,
        allowed_tools=frozenset({"check_availability", "propose_booking",
                                "get_customer_points_summary", "suggest_redeemable_offer"}))

    sink = _AcceptingAuditSink()
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    auditor = Auditor(sink=sink, service="whatsapp-assistant",
                      critical_actions=critical_actions(actions),
                      declared_actions=declared_actions(actions), fail_closed=True)

    # ── step 1: a fake inbound whatsapp.message event arrives (as main.py's subscriber would
    # hand it to the engine after wamid-dedup and customer-lookup) ────────────────────────────
    now = int(time.time())
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+966500000000",
                                 text="أبي أحجز غسيل بكرا", now=now)

    # ── step 2: the debounce window elapses; the model proposes a booking tool call ──────────
    slots = await provider.availability(tenant=TENANT, service_id="wash", earliest=now,
                                        horizon_days=7)
    assert slots, "the availability provider must offer at least one slot for this test to mean anything"
    target = slots[0]
    import datetime as dt
    iso = dt.datetime.fromtimestamp(target.starts_at, dt.timezone.utc).isoformat()
    llm.queue_tool_call("propose_booking", service_id="wash", starts_at_iso=iso)

    plan = await engine.compose_reply(TENANT, SUBJECT, now=now + 180)

    # ── step 3: the interactive proposal was built correctly — button ids map to the proposal ─
    assert plan.kind == "interactive"
    assert isinstance(plan.proposal, RenderedProposal)
    proposal_id = plan.proposal.proposal_id
    confirm_id = f"{proposal_id}:confirm"
    assert any(b["id"] == confirm_id for b in plan.proposal.buttons)

    sender = NullDirectSender()
    await sender.send_interactive(tenant=TENANT, to="+966500000000", body=plan.proposal.body,
                                  buttons=plan.proposal.buttons, idempotency_key=proposal_id)
    assert sender.sent and sender.sent[0]["buttons"][0]["id"] == confirm_id

    # ── step 4: the button reply comes back — THE ONLY thing that can fire the real write ─────
    reply_plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref=SUBJECT, reply_id=confirm_id, auditor=auditor, now=now + 200)

    assert reply_plan.kind == "text"
    assert "تم تأكيد" in reply_plan.text

    # ── step 5: the booking actually exists, and the Auditor recorded it ──────────────────────
    from app.core.models import BOOKINGS

    rows, _ = await store.find(BOOKINGS, {"tenant": TENANT, "subject_ref": SUBJECT}, limit=10)
    assert len(rows) == 1
    assert rows[0]["starts_at"] == target.starts_at

    assert any(e.action == "whatsapp_assistant.booking_confirmed" for e in sink.events)
    recorded = next(e for e in sink.events if e.action == "whatsapp_assistant.booking_confirmed")
    assert recorded.tenant == TENANT

    # ── the pending proposal is consumed — a replayed confirm must not double-book ────────────
    second_attempt = await engine.handle_button_reply(
        tenant=TENANT, subject_ref=SUBJECT, reply_id=confirm_id, auditor=auditor, now=now + 210)
    rows_after, _ = await store.find(BOOKINGS, {"tenant": TENANT, "subject_ref": SUBJECT}, limit=10)
    assert len(rows_after) == 1   # still exactly one booking


async def test_the_customer_still_hears_confirmed_when_the_audit_sink_is_down_at_that_instant():
    """The booking write succeeds; the audit witness fails right after. The customer must still
    get told the truth (their booking IS confirmed) rather than the whole reply vanishing behind
    an unhandled AuditUnavailable — see core/tools.py::execute_confirmed_proposal's own note."""
    from app.ports.audit_sink import FAILED, AuditReceipt

    store = MemoryDataStore()
    provider = _booking_provider(store)
    llm = StubLlm()
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=12,
        allowed_tools=frozenset({"check_availability", "propose_booking",
                                "get_customer_points_summary", "suggest_redeemable_offer"}))

    class _DownAuditSink:
        driver = "http"

        async def emit(self, event):
            return AuditReceipt(status=FAILED, detail="audit-service unreachable (simulated)")

    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    down_auditor = Auditor(sink=_DownAuditSink(), service="whatsapp-assistant",
                           critical_actions=critical_actions(actions),
                           declared_actions=declared_actions(actions), fail_closed=True)

    now = int(time.time())
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+966500000001",
                                 text="أبي أحجز غسيل بكرا", now=now)
    slots = await provider.availability(tenant=TENANT, service_id="wash", earliest=now, horizon_days=7)
    import datetime as dt
    iso = dt.datetime.fromtimestamp(slots[0].starts_at, dt.timezone.utc).isoformat()
    llm.queue_tool_call("propose_booking", service_id="wash", starts_at_iso=iso)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=now + 180)
    confirm_id = f"{plan.proposal.proposal_id}:confirm"

    reply_plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref=SUBJECT, reply_id=confirm_id, auditor=down_auditor, now=now + 200)

    # NO EXCEPTION — a real reply, and it tells the truth: the booking succeeded.
    assert reply_plan.kind == "text"
    assert "تم تأكيد" in reply_plan.text
    from app.core.models import BOOKINGS
    rows, _ = await store.find(BOOKINGS, {"tenant": TENANT, "subject_ref": SUBJECT}, limit=10)
    assert len(rows) == 1   # the booking IS real, audit gap or not
