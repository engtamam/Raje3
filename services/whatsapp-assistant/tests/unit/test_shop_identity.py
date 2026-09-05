"""build_system_prompt (core/conversation.py) and its wiring through ConversationEngine.compose_reply
via app/core/shop_identity.py — the shop's name must be per-tenant, config/data-driven, and never
leak from one tenant's persona into another's."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine, build_system_prompt
from app.core.points import NullPointsSummary
from app.core.shop_identity import GENERIC_SHOP_LABEL, NullShopIdentity


class _FakeShopIdentity:
    """Scriptable per-tenant name resolver — the shape a real HttpShopIdentity would return."""

    def __init__(self, names: dict[str, str]) -> None:
        self._names = names

    async def resolve(self, tenant: str) -> str:
        return self._names.get(tenant, GENERIC_SHOP_LABEL)


def _engine(store, llm, shop_identity=None, **overrides):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    kwargs = dict(store=store, llm=llm, booking_provider=provider,
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=4,
                 allowed_tools=frozenset({"check_availability", "propose_booking",
                                         "get_customer_points_summary",
                                         "suggest_redeemable_offer"}),
                 shop_identity=shop_identity)
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


def test_build_system_prompt_names_the_shop():
    prompt = build_system_prompt("محل الأناقة")
    assert "محل الأناقة" in prompt


def test_build_system_prompt_falls_back_to_generic_label_when_no_name():
    prompt = build_system_prompt("")
    assert GENERIC_SHOP_LABEL in prompt


def test_build_system_prompt_still_carries_the_hard_behavioral_constraints():
    """Whatever the shop's name, the propose-only / never-claim-an-action / ignore-override rules
    must still be present — personalization must not have crowded out the constraints."""
    prompt = build_system_prompt("محل الأناقة")
    assert "تقترح" in prompt          # propose, never confirm
    assert "تجاهل" in prompt          # ignore attempts to override instructions


def test_build_system_prompt_refuses_medical_and_technical_advice():
    """Found live (audit, 2026-09-05): nothing forbade the model from answering a genuine, ordinary
    customer question like «ايش الأفضل لبشرتي؟» with free-form advice — a real liability exposure
    no code-level filter can catch after the fact (there is no regex signature for "an opinion").
    Must be a persona-level refusal, checked here so it can never quietly disappear in a rewrite."""
    prompt = build_system_prompt("محل الأناقة")
    assert "نصيحة طبية" in prompt
    assert "توصية علاج" in prompt


def test_build_system_prompt_sets_a_length_ceiling_and_a_dialect():
    """The only length signal used to be the bare adjective «مختصر» — no target, no ceiling, no
    carve-out for a legitimate longer reply (e.g. listing several slots). And no dialect register
    was named at all, which the coordinator flagged as a real risk of the persona swinging between
    stiff MSA and overdone colloquial from one turn to the next."""
    prompt = build_system_prompt("محل الأناقة")
    assert "20 كلمة" in prompt
    assert "100 كلمة" in prompt
    assert "سعودية" in prompt


def test_two_tenants_get_two_different_personas_with_no_cross_leak():
    """TENANT ISOLATION FOR THE PERSONA ITSELF: shop A's name must never appear in shop B's
    system prompt, and vice versa — the whole point of resolving the name per tenant rather than
    hardcoding it once."""
    prompt_a = build_system_prompt("صالون A")
    prompt_b = build_system_prompt("مغسلة B")
    assert "صالون A" in prompt_a and "صالون A" not in prompt_b
    assert "مغسلة B" in prompt_b and "مغسلة B" not in prompt_a


async def test_compose_reply_sends_a_persona_naming_this_tenants_shop():
    store = MemoryDataStore()
    llm = StubLlm()
    identity = _FakeShopIdentity({"shop_a": "صالون A", "shop_b": "مغسلة B"})
    engine = _engine(store, llm, shop_identity=identity)

    llm.queue_text("أهلاً!")
    await engine.on_inbound_text(tenant="shop_a", subject_ref="sub1", from_number="+9665",
                                 text="مرحبا", now=1000)
    await engine.compose_reply("shop_a", "sub1", now=1200)

    llm.queue_text("أهلاً!")
    await engine.on_inbound_text(tenant="shop_b", subject_ref="sub2", from_number="+9666",
                                 text="مرحبا", now=1000)
    await engine.compose_reply("shop_b", "sub2", now=1200)

    assert len(llm.calls) == 2
    assert "صالون A" in llm.calls[0]["system_prompt"]
    assert "صالون A" not in llm.calls[1]["system_prompt"]
    assert "مغسلة B" in llm.calls[1]["system_prompt"]
    assert "مغسلة B" not in llm.calls[0]["system_prompt"]


async def test_compose_reply_degrades_to_generic_label_when_no_shop_identity_configured():
    """An engine built without a shop_identity (pre-existing test constructors, or an unconfigured
    peer) must still produce a valid persona — the generic label, never a crash and never a blank
    identity."""
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, shop_identity=None)

    llm.queue_text("أهلاً!")
    await engine.on_inbound_text(tenant="shop_x", subject_ref="sub1", from_number="+9665",
                                 text="مرحبا", now=1000)
    await engine.compose_reply("shop_x", "sub1", now=1200)

    assert GENERIC_SHOP_LABEL in llm.calls[0]["system_prompt"]


async def test_null_shop_identity_always_resolves_the_generic_label():
    assert await NullShopIdentity().resolve("any_tenant") == GENERIC_SHOP_LABEL
