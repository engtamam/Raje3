"""core/conversation.py — batching debounce, session timeout, and rolling summary fold."""
import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary
from app.ports.llm import LlmReply

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


class _SlowLlm(StubLlm):
    """An LLM call that does not resolve until told to — widens compose_reply's own in-flight
    window so a genuinely concurrent on_inbound_text can be raced against it deterministically."""

    def __init__(self, release: asyncio.Event) -> None:
        super().__init__()
        self._release = release

    async def respond(self, **kwargs):
        await self._release.wait()
        return await super().respond(**kwargs)


async def test_a_message_that_arrives_mid_composition_is_never_lost():
    """whatsapp-assistant-001 (QA audit, 2026-09-12): compose_reply used to hold its own snapshot
    across the whole LLM round trip and then do an unconditional save — a message on_inbound_text
    appended to raw_window WHILE that LLM call was still in flight could be silently overwritten by
    compose_reply's later, stale save. The conv lock must make on_inbound_text wait for
    compose_reply's save instead of racing it, so the new message survives either way."""
    store = MemoryDataStore()
    release = asyncio.Event()
    llm = _SlowLlm(release)
    engine = _engine(store, llm)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أول رسالة", now=1000)

    async def compose():
        return await engine.compose_reply(TENANT, SUBJECT, now=1200)

    async def send_second_message():
        # Give compose_reply a moment to acquire the lock and start waiting on the LLM, then send
        # a second message — this must be forced to wait for the lock (compose_reply is still
        # holding it), not race the save.
        await asyncio.sleep(0.02)
        await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="رسالة ثانية أثناء التفكير", now=1201)

    async def release_llm_soon():
        # Let compose_reply's LLM call keep the lock a while longer — long enough that
        # send_second_message is genuinely blocked waiting on it — before letting it finish.
        await asyncio.sleep(0.1)
        release.set()

    compose_task = asyncio.ensure_future(compose())
    second_task = asyncio.ensure_future(send_second_message())
    release_task = asyncio.ensure_future(release_llm_soon())
    await asyncio.gather(compose_task, second_task, release_task)

    conv = await engine._get(TENANT, SUBJECT)
    texts = [m["text"] for m in conv.raw_window]
    assert "رسالة ثانية أثناء التفكير" in texts
    # The second message waited for compose_reply's own save, so it is batching FRESH — not lost,
    # not silently folded into a conversation compose_reply had already marked idle/closed.
    assert conv.state == "batching"


async def test_sweep_due_cursor_reaches_every_batching_conversation_across_ticks():
    """Regression: sweep_due used to always re-read the same top-`batch` rows with no cursor — a
    tenant with more due conversations than the page size had its tail starved forever. The cursor
    now advances across calls so a full sweep pass eventually reaches every row. Fixed 2026-09-12."""
    from app.core.models import CONVERSATIONS

    store = MemoryDataStore()
    engine = _engine(store, StubLlm())
    subjects = [f"sub{i}" for i in range(5)]
    for i, subject in enumerate(subjects):
        await store.put(CONVERSATIONS, f"{TENANT}|{subject}", {
            "tenant": TENANT, "subject_ref": subject, "state": "batching",
            "batch_deadline": 1, "updated": i, "branch_id": "", "last_activity_at": 0,
            "session_started_at": 0, "session_closed_at": 0, "triage_resolved": True,
            "pending_proposal_id": "",
        })

    # `batch=1` on a set of 5 — with no cursor every call would return only `sub0` forever.
    seen: set[str] = set()
    for _ in range(len(subjects)):
        due = await engine.sweep_due(TENANT, now=1000, batch=1)
        seen.update(due)

    assert seen == set(subjects), f"sweep_due starved some conversations: only saw {seen}"
