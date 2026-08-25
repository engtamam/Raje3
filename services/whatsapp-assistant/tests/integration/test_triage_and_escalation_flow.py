"""Full flow: new conversation -> triage list sent -> free text ignored/re-prompted -> selection
made -> normal flow, with NO raw turn ceiling (a conversation runs however many turns it takes) ->
a frustration signal or a direct human request triggers a stop (no ticket-service ticket -- a shop
WhatsApp number is provisioned in Meta coexistence mode, so the shop's own staff already see the
same thread directly; see core/conversation.py::_escalate_to_human's docstring) -> customer
notified -> Auditor recorded whatsapp_assistant.escalated_to_human. A separate suite covers the
wallet-depletion stop (a different, non-escalation condition)."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.auditable_actions import AUDITABLE_ACTIONS
from app.core.audit import Auditor
from app.core.auditable import critical_actions, declared_actions, validate
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary

TENANT = "shop1"
SUBJECT = "sub_customer_1"


class _AcceptingAuditSink:
    driver = "http"

    def __init__(self):
        self.events = []

    async def emit(self, event):
        from app.ports.audit_sink import ACCEPTED, AuditReceipt

        self.events.append(event)
        return AuditReceipt(status=ACCEPTED, seq=len(self.events), hash="deadbeef")


def _auditor(sink):
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    return Auditor(sink=sink, service="whatsapp-assistant",
                   critical_actions=critical_actions(actions),
                   declared_actions=declared_actions(actions), fail_closed=True)


def _provider(store):
    cfg = BookingConfig(business_hours={}, default_duration_minutes=30, concurrency=1,
                        max_lead_days=7, slot_granularity_minutes=15, service_durations={})
    return ConfigDrivenAvailabilityProvider(store=store, cfg=cfg)


async def test_a_long_conversation_runs_many_turns_with_no_ceiling_then_frustration_stops_it():
    store = MemoryDataStore()
    llm = StubLlm()
    sink = _AcceptingAuditSink()
    auditor = _auditor(sink)

    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=999,
        allowed_tools=frozenset({"check_availability", "propose_booking",
                                "get_customer_points_summary", "suggest_redeemable_offer"}),
        auditor=auditor,
        # A generous duplicate threshold so the FIRST several ordinary turns genuinely do not
        # trip frustration — only the deliberately-repeated question near the end does.
        frustration_unconfirmed_proposals_threshold=99, frustration_duplicate_messages_threshold=3)

    now = 1_000_000

    # ── step 1: a brand-new conversation is gated straight into the triage list ────────────────
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+966500000000", text="السلام عليكم", now=now)
    assert plan.kind == "list"
    assert len(plan.list_rows) == 2

    # ── step 2: free text before a pick is ignored — re-sent the same list, never reaches the LLM
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+966500000000", text="أبي أحجز", now=now + 5)
    assert plan.kind == "list"
    assert llm.calls == []

    # ── step 3: the customer picks "inquiry" — normal flow opens ───────────────────────────────
    plan = await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:inquiry", now=now + 10)
    assert plan.kind == "text"

    # ── step 4+: FIVE ordinary text turns — well past any old ceiling of 12/2/whatever, proving
    # there is none — each still answered normally by the (unhelpful) stub LLM ─────────────────
    t = now + 20
    for i in range(5):
        await engine.handle_inbound_text(
            tenant=TENANT, subject_ref=SUBJECT, from_number="+966500000000",
            text=f"سؤال فريد {i}", now=t)
        reply_plan = await engine.compose_reply(TENANT, SUBJECT, now=t + 180)
        assert reply_plan.kind == "text"
        t += 200

    assert len(llm.calls) == 5   # every one of the five turns reached the model — no ceiling

    # ── step 5: the SAME question repeated three times reads as "the bot didn't understand" —
    # the frustration heuristic stops the ai, still never a ticket ─────────────────────────────
    for _ in range(3):
        await engine.handle_inbound_text(
            tenant=TENANT, subject_ref=SUBJECT, from_number="+966500000000",
            text="نفس السؤال بالضبط", now=t)
        t += 200
    escalation_plan = await engine.compose_reply(TENANT, SUBJECT, now=t)

    assert escalation_plan.kind == "text"
    assert "تحويل" in escalation_plan.text or "موظف" in escalation_plan.text
    assert len(llm.calls) == 5   # the model was NOT called for the frustrating turn

    # ── customer notified (the ReplyPlan text IS what main.py sends via the sender adapter) ─────
    assert escalation_plan.text

    # ── Auditor recorded the critical escalation action ─────────────────────────────────────────
    assert any(e.action == "whatsapp_assistant.escalated_to_human" for e in sink.events)
    recorded = next(e for e in sink.events if e.action == "whatsapp_assistant.escalated_to_human")
    assert recorded.tenant == TENANT

    conv = await engine._get(TENANT, SUBJECT)
    assert conv.escalated is True
    assert conv.state == "closed"

    # ── a further tick is a no-op for the same closed session ──────────────────────────────────
    again = await engine.compose_reply(TENANT, SUBJECT, now=t + 300)
    assert again.kind == "none"          # not "batching" anymore — closed
    escalated_events = [e for e in sink.events if e.action == "whatsapp_assistant.escalated_to_human"]
    assert len(escalated_events) == 1    # not recorded a second time for the same session


async def test_complaint_triage_pick_stops_the_ai_without_ever_calling_the_llm():
    store = MemoryDataStore()
    llm = StubLlm()
    sink = _AcceptingAuditSink()
    auditor = _auditor(sink)

    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12,
        allowed_tools=frozenset({"check_availability", "propose_booking",
                                "get_customer_points_summary", "suggest_redeemable_offer"}),
        auditor=auditor)

    now = 2_000_000
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT,
                                     from_number="+966511111111", text="hi", now=now)
    plan = await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:complaint", now=now + 5)

    assert plan.kind == "text"
    assert llm.calls == []
    assert any(e.action == "whatsapp_assistant.escalated_to_human" for e in sink.events)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.escalated is True
    assert conv.state == "closed"
