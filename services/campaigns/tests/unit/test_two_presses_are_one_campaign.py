"""Pressing «أطلق» twice must not cost the shop twice.

WHY IT HAPPENS AT ALL. The create route fires inside the request, so a campaign to a large
audience takes several seconds during which the screen shows nothing. The owner presses again —
which is not carelessness, it is the only feedback the button gives. Before this, that produced a
SECOND campaign with a fresh id, and every protection against reaching one person twice is keyed
on the campaign id: the two could not see each other, three hundred customers received the same
offer twice, and the shop paid for both.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.press import PRESSES, WINDOW_SECONDS, claim, key_for, settle

TENANT = "shop"
NOW = 1_780_000_000


def run(c):
    return asyncio.run(c)


def _key(**over) -> str:
    args = dict(goal="win_back", owner_text="خصم 20% هذا الأسبوع", service_id="", branch_id="",
                offer_value="20%", expires_at=NOW + 604_800, fire_at=0)
    args.update(over)
    return key_for(TENANT, **args)


def test_the_same_intention_is_the_same_key():
    assert _key() == _key()


def test_a_different_intention_is_a_different_campaign():
    """Changing anything the owner chose makes it a new campaign, which is what he meant."""
    base = _key()
    assert _key(owner_text="خصم 30% هذا الأسبوع") != base
    assert _key(goal="announce") != base
    assert _key(branch_id="br_2") != base
    assert _key(expires_at=NOW + 1) != base


def test_the_key_does_not_depend_on_the_attempt():
    """Nothing in it comes from us — no uuid, no clock. The attempt is what is uncertain."""
    assert _key() == _key()          # called at two different instants, same answer


def test_the_second_press_does_not_get_a_campaign_of_its_own():
    store = MemoryDataStore()
    key = _key()

    first = run(claim(store, TENANT, key, now=NOW))
    assert first.first

    # …the first press is still sending.
    second = run(claim(store, TENANT, key, now=NOW + 2))
    assert not second.first and second.in_flight

    run(settle(store, TENANT, key, "cmp_abc", now=NOW + 5))
    third = run(claim(store, TENANT, key, now=NOW + 6))
    assert not third.first and third.campaign_id == "cmp_abc"


def test_running_the_same_campaign_again_later_is_a_new_campaign():
    """Shops really do re-run an offer. Past the window it is a new one, not a silent no-op."""
    store = MemoryDataStore()
    key = _key()
    run(claim(store, TENANT, key, now=NOW))
    run(settle(store, TENANT, key, "cmp_abc", now=NOW))

    again = run(claim(store, TENANT, key, now=NOW + WINDOW_SECONDS + 1))
    assert again.first


def test_the_claim_is_written_before_the_campaign_exists():
    """Which is the whole reason the second press can see it while the first is still sending."""
    store = MemoryDataStore()
    key = _key()
    run(claim(store, TENANT, key, now=NOW))
    row = run(store.get(PRESSES, key))
    assert row is not None and row["campaign_id"] == ""
