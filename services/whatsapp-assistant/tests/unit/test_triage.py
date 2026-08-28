"""Mandatory first-message triage gate — state transitions, and that free text before a pick never
reaches the LLM (a stub that records every call it gets, asserted empty)."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary

TENANT = "t1"
SUBJECT = "sub1"


def _engine(store, llm=None, **overrides):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    kwargs = dict(store=store, llm=llm or StubLlm(), booking_provider=provider,
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=12,
                 allowed_tools=frozenset({"check_availability", "propose_booking",
                                         "get_customer_points_summary",
                                         "suggest_redeemable_offer"}))
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


async def test_a_fresh_conversation_is_gated_into_awaiting_triage_not_batching():
    store = MemoryDataStore()
    engine = _engine(store)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text="مرحبا", now=1000)
    assert plan.kind == "list"
    # Exactly two rows — inquiry/booking and complaint/suggestion. Neither label names what runs
    # behind it ("AI"/"موظف") — see app/core/conversation.py's TRIAGE_ROWS docstring.
    assert len(plan.list_rows) == 2
    titles = [row["title"] for row in plan.list_rows]
    assert all("AI" not in t and "موظف" not in t for t in titles)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "awaiting_triage"


async def test_free_text_before_a_triage_pick_never_reaches_the_llm_and_resends_the_list():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="أول رسالة", now=1000)
    plan = await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                            text="كم سعر الغسيل؟", now=1010)
    assert plan.kind == "list"
    assert llm.calls == []                      # NEVER forwarded to the model
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "awaiting_triage"       # still gated
    assert conv.raw_window == []                 # never recorded into the batching machinery either


async def test_inquiry_selection_transitions_to_idle_ready_for_normal_flow():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    plan = await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:inquiry", now=1010)
    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "idle"
    # and normal flow resumes exactly as before triage existed
    text_plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text="أبي أحجز غسيل", now=1020)
    assert text_plan.kind == "none"              # forwarded into batching, no synchronous reply
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "batching"


async def test_complaint_stops_the_ai_and_never_touches_the_llm_or_tool_allowlist():
    """Escalation is NOT a ticket-service ticket (a real design error, corrected — see
    core/conversation.py::_escalate_to_human's docstring): it is the AI stopping, on a shop
    number provisioned in WhatsApp coexistence mode so the shop's own staff already see the same
    thread directly. This test asserts the two things that are actually true of escalation: the
    LLM/tool path is never touched, and the session closes."""
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    plan = await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:complaint", now=1010)
    assert plan.kind == "text"
    assert "تحويل" in plan.text or "موظف" in plan.text
    assert llm.calls == []
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "closed"
    assert conv.escalated is True


async def test_a_stale_triage_reply_id_for_a_conversation_not_awaiting_triage_is_refused():
    store = MemoryDataStore()
    engine = _engine(store)
    # Never entered awaiting_triage — a fresh, never-seen conversation defaults to "idle".
    plan = await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:inquiry", now=1000)
    assert plan.kind == "list"                   # refused, not trusted
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "idle"


async def test_a_new_session_after_a_closed_one_is_gated_again():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:inquiry", now=1010)
    closed = await engine.sweep_timed_out(TENANT, now=1010 + 2500)
    assert SUBJECT in closed
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text="مرحبا مجددًا", now=1010 + 2600)
    assert plan.kind == "list"                   # gated again for the new session


async def test_a_mid_conversation_request_for_a_human_escalates_without_calling_the_llm():
    """A customer already past triage, mid-conversation, can still ask for a human at any point —
    the SAME escalation path as the ceiling/frustration triggers, checked every turn, not only at
    the first message."""
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:inquiry", now=1010)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="أبي أتكلم مع موظف بشري", now=1020)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1030)
    assert plan.kind == "text"
    assert "تحويل" in plan.text or "موظف" in plan.text
    assert llm.calls == []                       # the request itself never reached the model
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.escalated is True


async def test_branch_id_is_stamped_at_session_creation_and_survives_the_whole_session():
    """Phase 1 of the multi-branch work: a per_branch shop's number splits into (tenant,
    branch_id) before this engine ever sees it (core/inbound_ingest.py); this proves the engine's
    OWN half — once handed a branch_id, a fresh session stamps it and every later call for the
    SAME session keeps it, even though only the very first call actually passed one."""
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="مرحبا", branch_id="brn-jeddah", now=1000)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.branch_id == "brn-jeddah"

    # A LATER CALL IN THE SAME SESSION NEVER OVERWRITES IT — handle_triage_selection doesn't even
    # accept a branch_id parameter; the stored one must simply survive being loaded and re-saved.
    await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:inquiry", now=1010)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.branch_id == "brn-jeddah"


async def test_a_central_shops_session_has_no_branch_id_at_all():
    store = MemoryDataStore()
    engine = _engine(store)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="مرحبا", now=1000)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.branch_id == ""
