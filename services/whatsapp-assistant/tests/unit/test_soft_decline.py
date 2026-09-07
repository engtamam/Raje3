"""Soft-decline (core/soft_decline.py + the awaiting_promo_response/promo_declines/promo_suppressed
fields on ConversationState) — two waved-off promotional suggestions this session, and every
PROMO_TOOLS member goes quiet for the rest of it. NOT frustration/escalation: the conversation
keeps running normally throughout every test here."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine

_ALLOWED = frozenset({"check_availability", "propose_booking", "suggest_redeemable_offer"})
TENANT = "t1"
SUBJECT = "sub1"


class _FakePointsWithOffer:
    driver = "fake"

    async def summary(self, *, tenant: str, subject_ref: str) -> dict:
        return {"text": "", "points": 0}

    async def redeemable_offer(self, *, tenant: str, subject_ref: str):
        return {"reward_id": "r1", "reward_name": "غسيل مجاني"}


class _FakePointsNoOffer:
    driver = "fake"

    async def summary(self, *, tenant: str, subject_ref: str) -> dict:
        return {"text": "", "points": 0}

    async def redeemable_offer(self, *, tenant: str, subject_ref: str):
        return None


def _provider(store):
    return ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))


def _engine(store, llm, points_summary, soft_decline_threshold: int = 2):
    return ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store), points_summary=points_summary,
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=25,
        allowed_tools=_ALLOWED, soft_decline_threshold=soft_decline_threshold)


async def _open(engine, now: int) -> None:
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=now)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=now + 1)


async def _turn(engine, text: str, now: int) -> str:
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text=text, now=now)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=now + 200)
    return plan.text


async def test_one_decline_does_not_suppress_the_next_suggestion():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("suggest_redeemable_offer")   # turn 1: a real suggestion
    llm.queue_text("تمام!")                            # turn 2: the decline itself gets a reply
    llm.queue_tool_call("suggest_redeemable_offer")   # turn 3: still offered — one decline only
    engine = _engine(store, llm, _FakePointsWithOffer())
    await _open(engine, 1000)
    text1 = await _turn(engine, "أبغى أعرف عن العروض", 1010)
    assert "غسيل مجاني" in text1
    await _turn(engine, "لا شكرا", 1220)
    text3 = await _turn(engine, "طيب وايش غير كذا", 1430)
    assert "غسيل مجاني" in text3   # tool still ran — not suppressed yet


async def test_two_declines_suppress_every_promo_tool_for_the_rest_of_the_session():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("suggest_redeemable_offer")   # turn 1: suggestion
    llm.queue_text("تمام!")                            # turn 2: decline #1
    llm.queue_tool_call("suggest_redeemable_offer")   # turn 3: suggestion again
    llm.queue_text("تمام!")                            # turn 4: decline #2 — trips the threshold
    llm.queue_tool_call("suggest_redeemable_offer")   # turn 5: model tries anyway — must be refused
    engine = _engine(store, llm, _FakePointsWithOffer())
    await _open(engine, 1000)
    await _turn(engine, "أبغى أعرف عن العروض", 1010)
    await _turn(engine, "لا شكرا", 1220)
    await _turn(engine, "أبغى أعرف عن العروض", 1430)
    await _turn(engine, "لا شكرا", 1640)
    text5 = await _turn(engine, "وايش غير كذا", 1850)
    # The tool is no longer in `allowed` at all — validate_and_render refuses it outright, the
    # same "tool named outside the allowlist" defence-in-depth every other tool gets.
    assert "غسيل مجاني" not in text5
    assert "تعذّر تنفيذ ذلك الآن" in text5


async def test_a_real_followup_question_is_never_mistaken_for_a_decline():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("suggest_redeemable_offer")
    llm.queue_tool_call("suggest_redeemable_offer")   # still offered — the reply below is a
                                                       # genuine question, not a decline
    engine = _engine(store, llm, _FakePointsWithOffer())
    await _open(engine, 1000)
    await _turn(engine, "أبغى أعرف عن العروض", 1010)
    text2 = await _turn(engine, "لا أدري، هل ينفع أستخدمها بأي خدمة؟", 1220)
    assert "غسيل مجاني" in text2


async def test_a_nothing_to_offer_result_never_arms_the_decline_check():
    """suggest_redeemable_offer's own "nothing available" answer is not a pitch — a "لا" right
    after it must not count toward promo_declines at all."""
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("suggest_redeemable_offer")   # nothing to offer this time
    llm.queue_tool_call("suggest_redeemable_offer")   # a fresh offer now exists — still reachable
    engine = _engine(store, llm, _FakePointsNoOffer())
    await _open(engine, 1000)
    text1 = await _turn(engine, "أبغى أعرف عن العروض", 1010)
    assert "لا توجد مكافأة" in text1
    await _turn(engine, "لا", 1220)   # would-be decline, but nothing was actually offered
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.promo_declines == 0


async def test_declining_a_plain_text_reply_never_counts():
    """awaiting_promo_response is only ever armed by a REAL PROMO_TOOLS result — an ordinary free-
    text answer (no tool call at all) must never be treated as something the customer can
    "decline" toward the threshold."""
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_text("أهلاً وسهلاً، كيف أقدر أساعدك؟")
    engine = _engine(store, llm, _FakePointsWithOffer())
    await _open(engine, 1000)
    await _turn(engine, "مرحبا", 1010)
    await _turn(engine, "لا", 1220)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.promo_declines == 0


async def test_suppression_resets_on_a_brand_new_session():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("suggest_redeemable_offer")
    llm.queue_text("تمام!")
    llm.queue_tool_call("suggest_redeemable_offer")
    llm.queue_text("تمام!")
    engine = _engine(store, llm, _FakePointsWithOffer())
    await _open(engine, 1000)
    await _turn(engine, "أبغى أعرف عن العروض", 1010)
    await _turn(engine, "لا شكرا", 1220)
    await _turn(engine, "أبغى أعرف عن العروض", 1430)
    await _turn(engine, "لا شكرا", 1640)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.promo_suppressed is True

    # A silence long enough to close the session, then a brand-new one — same customer. Mirrors
    # _escalate_to_human's own close shape (conversation.py): state="closed" AND
    # triage_resolved=False together — the fresh-session reset block only fires on both.
    conv.session_closed_at = 1640
    conv.state = "closed"
    conv.triage_resolved = False
    await engine._save(conv)
    llm.queue_tool_call("suggest_redeemable_offer")
    await _open(engine, 100000)
    # A different phrasing than the first session's — raw_window (unlike the counters this test
    # is actually about) is not cleared across sessions, and a THIRD identical message would trip
    # the unrelated frustration duplicate-message signal instead of exercising soft-decline reset.
    text = await _turn(engine, "عندكم أي عروض اليوم؟", 100010)
    assert "غسيل مجاني" in text
    conv2 = await engine._get(TENANT, SUBJECT)
    assert conv2.promo_suppressed is False
    assert conv2.promo_declines == 0
