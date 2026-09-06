"""The customer-message word limit — refused BEFORE the message ever joins the batch, so it never
reaches the model even bundled with other, shorter ones (see conversation.py::handle_inbound_text's
own gate comment)."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary
from app.core.shop_identity import DEFAULT_MSG_WORD_LIMIT, GENERIC_SHOP_LABEL, ShopContext

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


class _FakeShopIdentity:
    def __init__(self, limit: int) -> None:
        self._limit = limit

    async def resolve(self, tenant: str) -> ShopContext:
        return ShopContext(name=GENERIC_SHOP_LABEL, msg_word_limit=self._limit)


async def _past_triage(engine, tenant=TENANT, subject=SUBJECT):
    await engine.handle_inbound_text(tenant=tenant, subject_ref=subject, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=tenant, subject_ref=subject,
                                         reply_id="triage:inquiry", now=1010)


async def test_a_message_at_the_default_limit_is_accepted():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm)
    await _past_triage(engine)
    text = " ".join(["كلمة"] * DEFAULT_MSG_WORD_LIMIT)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text=text, now=1020)
    assert plan.kind == "none"                    # forwarded into batching, no synchronous refusal
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.raw_window and conv.raw_window[-1]["text"] == text


async def test_a_message_one_word_over_the_default_limit_is_refused_without_calling_the_llm():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm)
    await _past_triage(engine)
    text = " ".join(["كلمة"] * (DEFAULT_MSG_WORD_LIMIT + 1))
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text=text, now=1020)
    assert plan.kind == "text"
    assert "اختصر" in plan.text
    assert llm.calls == []
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.raw_window == []                  # never recorded into the batching machinery


async def test_no_state_is_touched_on_a_refusal():
    """Same discipline as the licence gate: a customer who overshoots must be free to just try
    again shorter, not stuck having silently "used" part of this session."""
    store = MemoryDataStore()
    engine = _engine(store)
    await _past_triage(engine)
    conv_before = await engine._get(TENANT, SUBJECT)
    text = " ".join(["كلمة"] * (DEFAULT_MSG_WORD_LIMIT + 1))
    await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text=text, now=1020)
    conv_after = await engine._get(TENANT, SUBJECT)
    assert conv_before.state == conv_after.state
    assert conv_after.last_activity_at == conv_before.last_activity_at


async def test_a_shops_own_tightened_limit_is_respected():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, shop_identity=_FakeShopIdentity(20))
    await _past_triage(engine)
    text = " ".join(["كلمة"] * 21)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text=text, now=1020)
    assert plan.kind == "text"
    assert llm.calls == []


async def test_a_shops_own_loosened_limit_is_respected():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, shop_identity=_FakeShopIdentity(300))
    await _past_triage(engine)
    text = " ".join(["كلمة"] * (DEFAULT_MSG_WORD_LIMIT + 1))    # over the default, under this shop's
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text=text, now=1020)
    assert plan.kind == "none"


async def test_msg_word_limit_enabled_false_lets_every_message_through():
    """The gate-side kill switch: even a shop with a real, tight configured limit gets no
    refusal at all while this is off — matches shop_notes_enabled's own byte-identical posture."""
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, shop_identity=_FakeShopIdentity(20),
                     msg_word_limit_enabled=False)
    await _past_triage(engine)
    text = " ".join(["كلمة"] * 500)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text=text, now=1020)
    assert plan.kind == "none"


async def test_triage_and_branch_list_messages_are_never_gated_by_word_count():
    """Free text sent BEFORE a triage pick is already refused for an unrelated reason (never
    reaches this gate at all) — an extremely long message at that stage must still just re-send
    the triage list, not a word-limit refusal."""
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    long_text = " ".join(["كلمة"] * 500)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text=long_text, now=1010)
    assert plan.kind == "list"
    assert llm.calls == []
