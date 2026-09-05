"""core/conversation.py — batching debounce, session timeout, and rolling summary fold."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary

TENANT = "t1"
SUBJECT = "sub1"


def _engine(store, llm, **overrides):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    kwargs = dict(store=store, llm=llm, booking_provider=provider,
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=4,
                 allowed_tools=frozenset({"check_availability", "propose_booking",
                                         "get_customer_points_summary",
                                         "suggest_redeemable_offer"}))
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


async def test_second_message_inside_debounce_window_extends_it_not_a_second_reply():
    store = MemoryDataStore()
    engine = _engine(store, StubLlm())
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="مرحبا", now=1000)
    assert not await engine.due_for_reply(TENANT, SUBJECT, now=1100)   # inside 180s window
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="متى تفتحون؟", now=1100)
    # New deadline is relative to the SECOND message, not the first.
    assert not await engine.due_for_reply(TENANT, SUBJECT, now=1200)
    assert await engine.due_for_reply(TENANT, SUBJECT, now=1100 + 180)


async def test_debounced_burst_costs_exactly_one_llm_call():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_text("أهلاً بك")
    engine = _engine(store, llm)
    for i, now in enumerate((1000, 1050, 1090)):
        await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text=f"msg{i}", now=now)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1090 + 180)
    assert plan.kind == "text"
    assert len(llm.calls) == 1
    # All three batched messages reached the model as one user turn.
    assert "msg0" in llm.calls[0]["user_message"]
    assert "msg2" in llm.calls[0]["user_message"]


async def test_raw_window_folds_into_summary_once_it_exceeds_the_configured_size():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, raw_window_messages=2)
    for i, now in enumerate((1000, 1010, 1020, 1030)):
        await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text=f"msg{i}", now=now)
    conv = await engine._get(TENANT, SUBJECT)
    assert len(conv.raw_window) <= 2
    assert conv.summary != ""
    assert "msg0" in conv.summary   # the oldest message was folded, not dropped


async def test_session_timeout_closes_a_silent_conversation():
    store = MemoryDataStore()
    engine = _engine(store, StubLlm(), session_timeout_seconds=100)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="hi", now=1000)
    closed_early = await engine.sweep_timed_out(TENANT, now=1050)
    assert SUBJECT not in closed_early
    closed_late = await engine.sweep_timed_out(TENANT, now=1000 + 101)
    assert SUBJECT in closed_late
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "closed"


async def test_max_duration_closes_a_conversation_that_never_goes_silent():
    """CONVERSATION_MAX_DURATION_SECONDS is a ceiling UNDER the silence timeout, not a
    replacement for it — a conversation kept alive by constant activity (a stuck confirmation
    loop, a chatty back-and-forth) would otherwise never trip session_timeout_seconds and would
    stay open forever."""
    store = MemoryDataStore()
    engine = _engine(store, StubLlm(), session_timeout_seconds=100_000, max_duration_seconds=500)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="hi", now=1000)
    # Kept "active" the whole time — last_activity_at is fresh, so silence alone never closes it.
    still_open = await engine.sweep_timed_out(TENANT, now=1000 + 400)
    assert SUBJECT not in still_open
    closed = await engine.sweep_timed_out(TENANT, now=1000 + 501)
    assert SUBJECT in closed
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "closed"


async def test_max_duration_zero_disables_the_ceiling():
    """0 (the default when unset) must not close every conversation immediately — it means "no
    ceiling", not "ceiling of zero seconds"."""
    store = MemoryDataStore()
    engine = _engine(store, StubLlm(), session_timeout_seconds=100_000, max_duration_seconds=0)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="hi", now=1000)
    still_open = await engine.sweep_timed_out(TENANT, now=1000 + 99_999)
    assert SUBJECT not in still_open


async def test_a_conversation_with_a_pending_proposal_is_not_offered_a_second_state_changing_tool():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm)
    conv = await engine._get(TENANT, SUBJECT)
    conv.pending_proposal_id = "prp_existing"
    conv.state = "batching"
    conv.batch_deadline = 1000
    conv.raw_window = [{"role": "user", "text": "hi", "at": 900}]
    await engine._save(conv)
    llm.queue_text("ok")
    await engine.compose_reply(TENANT, SUBJECT, now=1000)
    allowed = llm.calls[0]["allowed_tools"]
    assert "propose_booking" not in allowed
    assert "suggest_redeemable_offer" not in allowed
