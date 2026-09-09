"""ConversationEngine's reserve math, wired to a real (fake) per-model cost registry — a cheap
model and an expensive model must reserve visibly different amounts for the exact same turn, and a
model missing from the registry must never block the AI. It also must never be free: with any
OTHER model already priced, it is billed at the most expensive of those; only a completely empty
registry falls back to the flat legacy rate.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.ports.llm import LlmReply
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary

TENANT = "shop1"


def _provider(store):
    cfg = BookingConfig(business_hours={}, default_duration_minutes=30, concurrency=1,
                        max_lead_days=7, slot_granularity_minutes=15, service_durations={})
    return ConfigDrivenAvailabilityProvider(store=store, cfg=cfg)


class _FakeWallet:
    """Just enough to observe the reserved amount — always accepts, records what it was asked
    to hold. The money-safety race itself is covered by test_wallet_hold_gates_the_ai.py; this
    file is only about WHICH NUMBER gets reserved."""
    driver = "fake"

    def __init__(self):
        self.reserved_amounts: list[int] = []
        self.confirmed_final_nets: list[int | None] = []

    async def reserve(self, *, tenant: str, amount_halalas: int, source: str):
        self.reserved_amounts.append(amount_halalas)
        return f"hld_{source}"

    async def confirm(self, hold_id: str, *, final_net: int | None = None) -> None:
        self.confirmed_final_nets.append(final_net)

    async def release(self, hold_id: str) -> None:
        return None


class _Settings:
    """A minimal stand-in for app.config.Settings — only the AI-unit fields
    AiUnitPricingConfig.from_settings actually reads."""
    def __init__(self, model_costs_json: str):
        self.PRICING_AI_UNIT_UNITS_PER_HALALA = 1000
        self.PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER = 5.0
        self.PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER = 2.0
        self.PRICING_AI_UNIT_USD_TO_SAR = 3.75
        self.PRICING_AI_UNIT_MODEL_COSTS_JSON = model_costs_json


_REGISTRY = (
    '{"cheap-model": {"input_usd_per_million": 0.10, "output_usd_per_million": 0.40}, '
    '"expensive-model": {"input_usd_per_million": 5.00, "output_usd_per_million": 20.00}}')


def _engine(store, llm, wallet, *, model_name: str, model_costs_json: str = _REGISTRY,
           runtime_config=None):
    return ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180,
        session_timeout_seconds=2400, raw_window_messages=12,
        allowed_tools=frozenset({"check_availability", "propose_booking",
                                "get_customer_points_summary", "suggest_redeemable_offer"}),
        wallet_balance=wallet, wallet_estimated_tokens=1000,
        wallet_rate_halalas_per_1k=100,   # the flat legacy fallback rate
        wallet_margin_halalas=0,
        ai_unit_pricing_settings=_Settings(model_costs_json), default_model_name=model_name,
        runtime_config=runtime_config)


async def _through_triage_and_reserve(engine, subject: str) -> None:
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=subject, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=subject, reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=subject, from_number="+9665",
                                 text="أبي أحجز غسيل", now=1002)
    await engine.compose_reply(TENANT, subject, now=1200)


async def test_a_cheap_and_an_expensive_model_reserve_visibly_different_amounts_for_the_same_turn():
    store_cheap, store_exp = MemoryDataStore(), MemoryDataStore()
    wallet_cheap, wallet_exp = _FakeWallet(), _FakeWallet()

    await _through_triage_and_reserve(
        _engine(store_cheap, StubLlm(), wallet_cheap, model_name="cheap-model"), "sub1")
    await _through_triage_and_reserve(
        _engine(store_exp, StubLlm(), wallet_exp, model_name="expensive-model"), "sub1")

    assert len(wallet_cheap.reserved_amounts) == 1
    assert len(wallet_exp.reserved_amounts) == 1
    cheap_amount = wallet_cheap.reserved_amounts[0]
    expensive_amount = wallet_exp.reserved_amounts[0]
    assert expensive_amount > cheap_amount
    # A real, large gap (the registry's own $ gap is 50x on input, 50x on output) — not noise.
    assert expensive_amount > cheap_amount * 10


async def test_an_unpriced_model_is_billed_at_the_priciest_known_models_rate_never_free():
    """THE REAL BUG THIS REPLACES: this registry's own flat legacy fallback is 100 — but an
    unpriced model must not fall back to THAT when the registry itself is non-empty; it must be
    billed at the most expensive model already registered ("expensive-model" here), so it can
    only ever be over-charged relative to its true unknown cost, never under-charged or free."""
    store_unpriced, store_expensive = MemoryDataStore(), MemoryDataStore()
    wallet_unpriced, wallet_expensive = _FakeWallet(), _FakeWallet()
    engine_unpriced = _engine(store_unpriced, StubLlm(), wallet_unpriced,
                              model_name="some-brand-new-model")
    engine_expensive = _engine(store_expensive, StubLlm(), wallet_expensive,
                               model_name="expensive-model")
    await _through_triage_and_reserve(engine_unpriced, "sub1")
    await _through_triage_and_reserve(engine_expensive, "sub1")

    assert len(wallet_unpriced.reserved_amounts) == 1
    # SAME conversation flow (identical prompt size either way), priced at "expensive-model"'s own
    # rate for both — the unpriced model's substitute, exactly, never the flat fallback and never 0.
    assert wallet_unpriced.reserved_amounts == wallet_expensive.reserved_amounts


async def test_an_unpriced_model_with_a_completely_empty_registry_falls_back_to_the_flat_rate():
    """The one case the flat legacy rate IS still used: no model has ever been priced at all, so
    there is no "most expensive known model" to substitute — EVERY model name reserves identically
    against an empty registry, priced at the one flat rate left (100 halalas/1k) for both."""
    store_a, store_b = MemoryDataStore(), MemoryDataStore()
    wallet_a, wallet_b = _FakeWallet(), _FakeWallet()
    engine_a = _engine(store_a, StubLlm(), wallet_a, model_name="some-brand-new-model",
                      model_costs_json="{}")
    engine_b = _engine(store_b, StubLlm(), wallet_b, model_name="a-totally-different-unpriced-name",
                      model_costs_json="{}")
    await _through_triage_and_reserve(engine_a, "sub1")
    await _through_triage_and_reserve(engine_b, "sub1")

    assert len(wallet_a.reserved_amounts) == 1
    assert wallet_a.reserved_amounts == wallet_b.reserved_amounts


class _FakeCatalog:
    def __init__(self, services: list[dict]):
        self._services = services

    async def list_active(self, tenant):
        return self._services


def _big_catalog(n: int) -> list[dict]:
    return [{"id": f"svc{i}", "name": f"خدمة رقم {i} — وصف طويل نسبياً لهذه الخدمة", "price_minor": 5000}
           for i in range(n)]


async def test_a_shops_own_bigger_catalogue_reserves_visibly_more_for_the_same_model():
    """THE REAL FEATURE — replaces a flat, one-size-fits-all token guess with a REAL measurement
    of what is actually about to be sent. Two shops, same model, same conversation shape: the one
    with a much bigger service catalogue (core/context_builder.py's own build_context_block,
    genuinely uncapped) must reserve visibly more, because its real prompt really is bigger — the
    old flat WALLET_ESTIMATED_MAX_TOKENS_PER_TURN guess could never have told these apart."""
    store_small, store_big = MemoryDataStore(), MemoryDataStore()
    wallet_small, wallet_big = _FakeWallet(), _FakeWallet()
    engine_small = _engine(store_small, StubLlm(), wallet_small, model_name="cheap-model")
    engine_small._catalog = _FakeCatalog(_big_catalog(1))
    engine_big = _engine(store_big, StubLlm(), wallet_big, model_name="cheap-model")
    engine_big._catalog = _FakeCatalog(_big_catalog(200))

    await _through_triage_and_reserve(engine_small, "sub1")
    await _through_triage_and_reserve(engine_big, "sub1")

    assert len(wallet_small.reserved_amounts) == 1
    assert len(wallet_big.reserved_amounts) == 1
    assert wallet_big.reserved_amounts[0] > wallet_small.reserved_amounts[0]


async def test_using_an_unpriced_models_substitute_rate_is_audited():
    """The visibility half of the fix — a real Auditor (not a no-op fake), so a bug in
    auditable_actions.py's own declaration (this action must be declared there, or `Auditor.record`
    itself refuses it) is caught here rather than silently swallowed by _reserve_llm_hold's own
    best-effort try/except."""
    from app.core.audit import Auditor
    from app.core.auditable import critical_actions, declared_actions, validate
    from app.adapters.audit_sink.null import NullAuditSink
    from app.auditable_actions import AUDITABLE_ACTIONS

    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    sink = NullAuditSink()
    auditor = Auditor(sink=sink, service="whatsapp-assistant",
                      critical_actions=critical_actions(actions),
                      declared_actions=declared_actions(actions), fail_closed=True)

    store = MemoryDataStore()
    wallet = _FakeWallet()
    engine = _engine(store, StubLlm(), wallet, model_name="some-brand-new-model")
    engine.set_auditor(auditor)
    await _through_triage_and_reserve(engine, "sub1")

    unpriced_events = [e for e in sink.events if e.action == "whatsapp_assistant.unpriced_model_used"]
    assert len(unpriced_events) == 1
    assert unpriced_events[0].metadata.get("model") == "some-brand-new-model"

    # A PRICED model must never fire this event — the audit trail would be noise otherwise.
    store2 = MemoryDataStore()
    wallet2 = _FakeWallet()
    engine2 = _engine(store2, StubLlm(), wallet2, model_name="cheap-model")
    engine2.set_auditor(auditor)
    await _through_triage_and_reserve(engine2, "sub2")
    assert not [e for e in sink.events
               if e.action == "whatsapp_assistant.unpriced_model_used"
               and e.resource == "model:cheap-model"]


class _FlakyRuntimeConfig:
    """Simulates an operator flipping ASSISTANT_MODEL_NAME mid-turn: the FIRST .get() call for
    that key (compose_reply's own `_resolve_live_model_name`, called once before the reserve)
    answers `first`; every call after that answers `second` — exactly what a second, independent
    re-resolve deeper in the same turn would have seen under the old TOCTOU."""
    def __init__(self, first: str, second: str):
        self._first, self._second = first, second
        self._calls = 0

    async def get(self, *, tenant: str, key: str, default):
        if key != "ASSISTANT_MODEL_NAME":
            return default
        self._calls += 1
        return self._first if self._calls == 1 else self._second


async def test_a_model_switch_mid_turn_cannot_split_the_reserve_from_the_actual_call():
    """THE RACE THIS FIX CLOSES: before threading one resolved model_name through both the reserve
    and the actual LLM call, each side re-read ASSISTANT_MODEL_NAME independently — a switch
    landing in the real async I/O gap between them (shop context, prompt building) meant the
    reserve was priced at one model's rate while the actual call ran a different one. Both sides
    must now agree, always, on whichever value was live at the ONE moment compose_reply resolved
    it — never a mix."""
    store, store_control = MemoryDataStore(), MemoryDataStore()
    wallet, wallet_control = _FakeWallet(), _FakeWallet()
    llm, llm_control = StubLlm(), StubLlm()
    runtime_config = _FlakyRuntimeConfig(first="cheap-model", second="expensive-model")
    engine = _engine(store, llm, wallet, model_name="cheap-model", runtime_config=runtime_config)
    # CONTROL: no flaky runtime_config at all — "cheap-model" resolved consistently throughout,
    # exactly what a non-racing turn looks like. Its reserved amount is the ground truth to compare
    # against, rather than a hand-computed magic number tied to this test's own prompt size.
    engine_control = _engine(store_control, llm_control, wallet_control, model_name="cheap-model")
    await _through_triage_and_reserve(engine, "sub1")
    await _through_triage_and_reserve(engine_control, "sub1")

    assert len(wallet.reserved_amounts) == 1
    assert len(llm.calls) == 1
    # Priced at "cheap-model"'s own rate, matching the control exactly — NOT "expensive-model",
    # which a second, independent resolve deeper in the turn would have priced it at instead.
    assert wallet.reserved_amounts == wallet_control.reserved_amounts
    # AND the actual call ran the SAME model the reserve was priced for.
    assert llm.calls[0]["model_name"] == "cheap-model"


async def test_confirm_charges_the_real_smaller_cost_not_the_reserved_ceiling():
    """THE REAL FEATURE: wallet-service v0.19.2's confirm(final_net=...). The reserve above prices
    a conservative ceiling BEFORE the LLM call (worse-of-input/output, blended over a generous
    token estimate); StubLlm's default reply carries real, small token counts (5 in, 5 out) —
    the real cost must come out well under what was reserved, priced at EACH side's own real rate
    (not the reserve's single blended one)."""
    store = MemoryDataStore()
    wallet = _FakeWallet()
    llm = StubLlm()
    engine = _engine(store, llm, wallet, model_name="expensive-model")
    await _through_triage_and_reserve(engine, "sub1")

    # real: ceil(5/1000 * 9.375 input-rate) + ceil(5/1000 * 15.0 output-rate) = 1 + 1 = 2 — this
    # depends only on StubLlm's own default reply token counts, never on the reserve's own
    # (now real-prompt-size-based) estimate.
    assert wallet.confirmed_final_nets == [2]
    assert wallet.confirmed_final_nets[0] < wallet.reserved_amounts[0]   # never the full ceiling


async def test_confirm_is_clamped_to_the_reserved_amount_never_exceeds_it():
    """The one direction that must never happen: wallet-service refuses final_net above the
    reserved net outright. A real cost that somehow exceeds the reserve's own generous estimate
    (a reply far longer than WALLET_ESTIMATED_MAX_TOKENS_PER_TURN assumed) must be CLAMPED down to
    the reserved amount rather than ever attempt a final_net past it."""
    store = MemoryDataStore()
    wallet = _FakeWallet()
    llm = StubLlm()
    # Reserved for "cheap-model" (a small rate) but the real reply is priced as if it ran
    # "expensive-model" — simulating real usage costing far more than what was ever reserved.
    llm.queue(LlmReply(text="رد طويل جداً", input_tokens=5000, output_tokens=5000))
    engine = _engine(store, llm, wallet, model_name="cheap-model")
    await _through_triage_and_reserve(engine, "sub1")

    reserved = wallet.reserved_amounts[0]
    assert wallet.confirmed_final_nets == [reserved]   # clamped down, never a value above it


async def test_with_no_ai_unit_pricing_settings_wired_behaviour_is_byte_identical_to_before():
    """Every pre-existing test constructor (ai_unit_pricing_settings=None, the default) must keep
    reserving exactly the flat rate it always did — no regression for a caller that never opts in."""
    store = MemoryDataStore()
    wallet = _FakeWallet()
    engine = ConversationEngine(
        store=store, llm=StubLlm(), booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180,
        session_timeout_seconds=2400, raw_window_messages=12,
        allowed_tools=frozenset({"check_availability", "propose_booking",
                                "get_customer_points_summary", "suggest_redeemable_offer"}),
        wallet_balance=wallet, wallet_estimated_tokens=1000, wallet_rate_halalas_per_1k=100,
        wallet_margin_halalas=50)
    await _through_triage_and_reserve(engine, "sub1")
    assert wallet.reserved_amounts == [150]   # 1000 @ 100/1k = 100, + 50 margin — unchanged
