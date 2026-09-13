"""core/tools.py's suggest_services_carousel — floor enforced BEFORE rendering, never at send
time; only items with a real photo are ever offered."""
from __future__ import annotations

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.points import NullPointsSummary
from app.ports.catalog_provider import CatalogCard

TENANT = "t1"
ALLOWED = frozenset({"suggest_services_carousel"})


class FakeCatalogProvider:
    def __init__(self, cards):
        self._cards = cards

    async def list_cards(self, *, tenant, limit=10):
        return self._cards[:limit]


def _provider_call(**kwargs):
    store = MemoryDataStore()
    cfg = BookingConfig(business_hours={}, default_duration_minutes=30, concurrency=1,
                       max_lead_days=7, slot_granularity_minutes=30, service_durations={})
    return T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
        tool="suggest_services_carousel", args={}, allowed_tools=ALLOWED, store=store,
        booking_provider=ConfigDrivenAvailabilityProvider(store=store, cfg=cfg),
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, **kwargs)


async def test_two_or_more_cards_with_photos_render_a_carousel():
    cards = [
        CatalogCard(id="srv_1", kind="service", name="قص شعر", price_minor=5000,
                   image_url="http://x/1.jpg"),
        CatalogCard(id="pkg_1", kind="package", name="باقة", price_minor=12000,
                   image_url="http://x/2.jpg"),
    ]
    result = await _provider_call(catalog_provider=FakeCatalogProvider(cards))
    assert isinstance(result, T.RenderedCarousel)
    assert result.cards == cards


async def test_items_with_no_photo_are_never_included():
    cards = [
        CatalogCard(id="srv_1", kind="service", name="a", price_minor=100, image_url="http://x/1.jpg"),
        CatalogCard(id="srv_2", kind="service", name="b", price_minor=100, image_url=""),
        CatalogCard(id="srv_3", kind="service", name="c", price_minor=100, image_url="http://x/3.jpg"),
    ]
    result = await _provider_call(catalog_provider=FakeCatalogProvider(cards))
    assert isinstance(result, T.RenderedCarousel)
    assert [c.id for c in result.cards] == ["srv_1", "srv_3"]


async def test_exactly_one_photo_renders_a_single_card_not_an_apology():
    """The bug this fixed: `< 2` used to fold "exactly one" into "none at all" and apologised
    for missing photos it actually had."""
    cards = [CatalogCard(id="srv_1", kind="service", name="a", price_minor=100,
                         image_url="http://x/1.jpg")]
    result = await _provider_call(catalog_provider=FakeCatalogProvider(cards))
    assert isinstance(result, T.RenderedSingleCard)
    assert result.card == cards[0]


async def test_zero_photos_still_degrades_to_plain_text():
    cards = [CatalogCard(id="srv_1", kind="service", name="a", price_minor=100, image_url="")]
    result = await _provider_call(catalog_provider=FakeCatalogProvider(cards))
    assert isinstance(result, str)
    assert "صور" in result


async def test_no_catalog_provider_configured_degrades_to_plain_text():
    result = await _provider_call(catalog_provider=None)
    assert isinstance(result, str)


async def test_cards_are_capped_at_max_carousel_cards():
    cards = [CatalogCard(id=f"srv_{i}", kind="service", name=str(i), price_minor=100,
                         image_url=f"http://x/{i}.jpg") for i in range(10)]
    result = await _provider_call(catalog_provider=FakeCatalogProvider(cards), max_carousel_cards=3)
    assert isinstance(result, T.RenderedCarousel)
    assert len(result.cards) == 3


async def test_a_tool_not_in_the_allowlist_is_refused_even_with_a_provider_configured():
    """Defence in depth — the LLM adapter already filters this, but a call reaching here outside
    the allowlist must never be trusted, same as every other tool."""
    import pytest

    with pytest.raises(T.ToolValidationError):
        store = MemoryDataStore()
        cfg = BookingConfig(business_hours={}, default_duration_minutes=30, concurrency=1,
                           max_lead_days=7, slot_granularity_minutes=30, service_durations={})
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
            tool="suggest_services_carousel", args={}, allowed_tools=frozenset(), store=store,
            booking_provider=ConfigDrivenAvailabilityProvider(store=store, cfg=cfg),
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            catalog_provider=FakeCatalogProvider([
                CatalogCard(id="a", kind="service", name="a", price_minor=1, image_url="http://x/1"),
                CatalogCard(id="b", kind="service", name="b", price_minor=1, image_url="http://x/2"),
            ]))
