"""The send log as an ENTITLEMENT RECORD — which is what it is, and not only a list of messages.

An offer lives in this collection because sending it is what created the entitlement. So the rules
about spending one live here too: the four below are each a real way a customer could have
something taken from him, or a shop could honour the same thing twice.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.stores import SendLogStore


@pytest.fixture
def store():
    return MemoryDataStore()


@pytest.mark.asyncio
async def test_an_offer_is_spent_only_when_somebody_says_so(store):
    """SILENCE NEVER SPENDS (§5.6.2). A customer who came in for something else and was silently
    charged an offer he was saving is a customer we took something from."""
    log = SendLogStore(store)
    await log.append("t1", {"id": "s1", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 100, "offer_text": "غسلة مجانية",
                            "offer_expires_at": 9_000_000, "offer_services": []})

    # Reading it changes nothing.
    assert len(await log.live_offers("t1", "sub_a", used_refs=set(), now=1000)) == 1

    row = await log.choose_offer("t1", "sub_a", service_ids=["x"], used_refs=set(), now=1000)
    assert row is not None

    # AND CHOOSING SPENT NOTHING. The send log is append-only (§5.6.2) — operations records the
    # spend on the visit, and hands back what it recorded. Until it does, he still holds it.
    assert len(await log.live_offers("t1", "sub_a", used_refs=set(), now=1000)) == 1
    # Once operations HAS recorded it, it is gone from what he holds — not expired, SPENT.
    assert await log.live_offers("t1", "sub_a", used_refs={row["id"]}, now=1000) == []


@pytest.mark.asyncio
async def test_a_second_tap_on_one_visit_spends_nothing_more(store):
    """A double tap at a counter is one intention, and a screen that punished it is a screen
    people stop trusting."""
    log = SendLogStore(store)
    for i, exp in ((1, 9_000_000), (2, 9_500_000)):
        await log.append("t1", {"id": f"s{i}", "tenant": "t1", "subject_ref": "sub_a",
                                "outcome": "sent", "at": 100 + i, "offer_text": f"عرض {i}",
                                "offer_expires_at": exp, "offer_services": []})

    first = await log.choose_offer("t1", "sub_a", service_ids=[], used_refs=set(), now=1000)
    # «One per visit» is enforced where the visit is — in operations, which returns what it already
    # recorded rather than asking again. Here we prove the other half: once one is spent, the next
    # question gets a DIFFERENT offer, never the same one twice.
    again = await log.choose_offer("t1", "sub_a", service_ids=[],
                                   used_refs={first["id"]}, now=1000)

    assert first["id"] != again["id"]
    # And nothing beyond those two exists to spend.
    assert len(await log.live_offers("t1", "sub_a",
                                     used_refs={first["id"], again["id"]}, now=1000)) == 0


@pytest.mark.asyncio
async def test_the_scope_decides_and_the_soonest_to_expire_goes_first(store):
    """THE TEXT PERSUADES AND THE SCOPE APPLIES. A scoped offer is not spent by a visit that never
    touched its services — and holding two, he spends the one about to run out."""
    log = SendLogStore(store)
    await log.append("t1", {"id": "s1", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 101, "offer_text": "على الغسيل", "offer_expires_at": 9_000_000,
                            "offer_services": ["wash"]})
    await log.append("t1", {"id": "s2", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 102, "offer_text": "على كل شيء", "offer_expires_at": 8_000_000,
                            "offer_services": []})

    # A visit with neither: the scoped one must not be touched, and the open one is applicable.
    row = await log.choose_offer("t1", "sub_a", service_ids=["tyres"], used_refs=set(), now=1000)
    assert row["id"] == "s2"        # the open offer, and it expires soonest of the two

    row = await log.choose_offer("t1", "sub_a", service_ids=["wash"],
                                 used_refs={"s2"}, now=1000)
    assert row["id"] == "s1"        # now the scoped one, because this visit carries its service


@pytest.mark.asyncio
async def test_a_visit_that_touches_nothing_scoped_spends_nothing(store):
    log = SendLogStore(store)
    await log.append("t1", {"id": "s1", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 101, "offer_text": "على الغسيل", "offer_expires_at": 9_000_000,
                            "offer_services": ["wash"]})

    assert await log.choose_offer("t1", "sub_a", service_ids=["tyres"],
                                  used_refs=set(), now=1000) is None
    assert len(await log.live_offers("t1", "sub_a", used_refs=set(), now=1000)) == 1


@pytest.mark.asyncio
async def test_choose_offer_carries_the_campaign_id_through_untouched(store):
    """2026-09-14 (till-integration audit follow-up): `choose_offer` hands back the whole row, so
    a `campaign_id` stamped on it by a campaign send must survive to the till's own
    `POST /till/offer/apply` — the one piece of evidence that lets a shop learn which campaign
    actually converted a customer."""
    log = SendLogStore(store)
    await log.append("t1", {"id": "s1", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 100, "offer_text": "خصم 20%",
                            "offer_expires_at": 9_000_000, "offer_services": [],
                            "campaign_id": "cmp_win_back_1"})
    row = await log.choose_offer("t1", "sub_a", service_ids=[], used_refs=set(), now=1000)
    assert row is not None
    assert row["campaign_id"] == "cmp_win_back_1"


@pytest.mark.asyncio
async def test_choose_offer_with_no_campaign_answers_an_empty_string_not_a_missing_key(store):
    """An ordinary reminder's offer (no campaign behind it) must still answer a real, present
    value — a caller reading `row["campaign_id"]` must never KeyError on the common case."""
    log = SendLogStore(store)
    await log.append("t1", {"id": "s1", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 100, "offer_text": "خصم 20%",
                            "offer_expires_at": 9_000_000, "offer_services": []})
    row = await log.choose_offer("t1", "sub_a", service_ids=[], used_refs=set(), now=1000)
    assert row is not None
    assert row.get("campaign_id", "") == ""
