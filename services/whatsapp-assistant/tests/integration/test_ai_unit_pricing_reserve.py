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

    async def reserve(self, *, tenant: str, amount_halalas: int, source: str):
        self.reserved_amounts.append(amount_halalas)
        return f"hld_{source}"

    async def confirm(self, hold_id: str) -> None:
        return None

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


def _engine(store, llm, wallet, *, model_name: str, model_costs_json: str = _REGISTRY):
    return ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180,
        session_timeout_seconds=2400, raw_window_messages=12,
        allowed_tools=frozenset({"check_availability", "propose_booking",
                                "get_customer_points_summary", "suggest_redeemable_offer"}),
        wallet_balance=wallet, wallet_estimated_tokens=1000,
        wallet_rate_halalas_per_1k=100,   # the flat legacy fallback rate
        wallet_margin_halalas=0,
        ai_unit_pricing_settings=_Settings(model_costs_json), default_model_name=model_name)


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
    store = MemoryDataStore()
    wallet = _FakeWallet()
    engine = _engine(store, StubLlm(), wallet, model_name="some-brand-new-model")
    await _through_triage_and_reserve(engine, "sub1")

    assert len(wallet.reserved_amounts) == 1
    # "expensive-model"'s own rate (max of its input/output halves) — 15 halalas/1k, not the flat
    # 100 fallback and never 0.
    assert wallet.reserved_amounts[0] == 15


async def test_an_unpriced_model_with_a_completely_empty_registry_falls_back_to_the_flat_rate():
    """The one case the flat legacy rate IS still used: no model has ever been priced at all, so
    there is no "most expensive known model" to substitute."""
    store = MemoryDataStore()
    wallet = _FakeWallet()
    engine = _engine(store, StubLlm(), wallet, model_name="some-brand-new-model",
                     model_costs_json="{}")
    await _through_triage_and_reserve(engine, "sub1")

    assert len(wallet.reserved_amounts) == 1
    assert wallet.reserved_amounts[0] == 100   # the flat 100 halalas/1k fallback, no margin here


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
