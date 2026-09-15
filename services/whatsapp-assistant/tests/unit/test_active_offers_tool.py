"""core/tools.py's check_active_offers — real offer facts back to the model, never a fixed
sentence for the customer. See core/active_offers.py's own module docstring for why this needs no
guessing about which campaign the customer means."""
from __future__ import annotations

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.active_offers import ActiveOffer
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.points import NullPointsSummary

TENANT = "t1"
ALLOWED = frozenset({"check_active_offers"})


class FakeActiveOffers:
    def __init__(self, offers: list[ActiveOffer]) -> None:
        self._offers = offers

    async def for_subject(self, *, tenant, subject_ref):
        return self._offers


def _call(**kwargs):
    store = MemoryDataStore()
    cfg = BookingConfig(business_hours={}, default_duration_minutes=30, concurrency=1,
                       max_lead_days=7, slot_granularity_minutes=30, service_durations={})
    return T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
        tool="check_active_offers", args={}, allowed_tools=ALLOWED, store=store,
        booking_provider=ConfigDrivenAvailabilityProvider(store=store, cfg=cfg),
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, **kwargs)


async def test_no_peer_wired_says_so_plainly_not_an_error():
    result = await _call(active_offers=None)
    assert result == "لا توجد عروض حالية لهذا العميل."


async def test_no_live_offers_says_so_plainly():
    result = await _call(active_offers=FakeActiveOffers([]))
    assert result == "لا يوجد عرض حالي ساري لهذا العميل الآن."


async def test_a_real_offer_states_the_real_facts():
    offer = ActiveOffer(text="خصم 20% على الغسيل الخارجي", expires_at=1_800_000_000, sent_at=1,
                        services=["غسيل خارجي"], scoped=True, value="20%")
    result = await _call(active_offers=FakeActiveOffers([offer]))
    assert "خصم 20% على الغسيل الخارجي" in result
    assert "20%" in result
    assert "غسيل خارجي" in result
    assert "عروضه الحالية الحقيقية" in result


async def test_an_unscoped_offer_never_invents_a_service_list():
    offer = ActiveOffer(text="خصم عام لكل الخدمات", expires_at=1_800_000_000, sent_at=1,
                        services=[], scoped=False, value="")
    result = await _call(active_offers=FakeActiveOffers([offer]))
    assert "خصم عام لكل الخدمات" in result
    assert "يشمل" not in result


async def test_a_scoped_offer_with_no_kept_names_says_so_honestly():
    """`scoped=True` with an empty `services` list is a real, distinct state (see
    reminders' own portal_offers docstring: an offer recorded before service names were kept) —
    never silently folded into "whole shop"."""
    offer = ActiveOffer(text="خصم محدود", expires_at=1_800_000_000, sent_at=1,
                        services=[], scoped=True, value="")
    result = await _call(active_offers=FakeActiveOffers([offer]))
    assert "خدمات محددة" in result


async def test_multiple_live_offers_are_all_listed():
    offers = [
        ActiveOffer(text="عرض أول", expires_at=1_800_000_000, sent_at=1, services=[],
                   scoped=False, value=""),
        ActiveOffer(text="عرض ثاني", expires_at=1_800_100_000, sent_at=2, services=[],
                   scoped=False, value=""),
    ]
    result = await _call(active_offers=FakeActiveOffers(offers))
    assert "عرض أول" in result and "عرض ثاني" in result
