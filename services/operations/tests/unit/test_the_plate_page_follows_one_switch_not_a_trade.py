"""The plate page follows one switch the owner can flip, not a trade he chose once.

WHAT IT WAS. Sign-up asked «نوع النشاط» and the answer decided four separate things, one of which
was whether «تسجيل زيارة» shows a plate page. So the tyre shop that added detailing, and the car
wash that stopped doing cars, both lived for ever with a screen that was wrong about them — the
trade was chosen once and there was no screen anywhere that could change it.

WHAT IT IS. `tracks_vehicle` on his own establishment, and he can flip it this afternoon.

THE FIELDS ARE NAMES, NOT A BOOLEAN, because `Visit.tsx` asks «is `plate` among my fields». A
boolean would put the list of what a vehicle shop needs inside the console, where changing it means
a release.
"""
from __future__ import annotations

import asyncio

from app.core import vehicles as V


def run(coro):
    return asyncio.run(coro)


class _Store:
    def __init__(self, rows=None):
        self.rows = dict(rows or {})

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row


class _Unreadable(_Store):
    async def get(self, collection, key):
        raise RuntimeError("the datastore is down")


def test_a_shop_that_never_said_does_not_get_a_plate_page():
    """Absent means no, and most shops are absent — the default is not written at signup."""
    store = _Store()

    assert run(V.VehicleStore(store).tracks_vehicle("t1")) is False
    assert run(V.fields_for(store, "t1")) == []


def test_a_shop_that_says_yes_is_asked_for_the_plate_and_the_meter():
    store = _Store()
    run(V.VehicleStore(store).set("t1", True))

    assert run(V.VehicleStore(store).tracks_vehicle("t1")) is True
    assert [f["name"] for f in run(V.fields_for(store, "t1"))] == [V.PLATE, V.METER]


def test_turning_it_off_is_an_answer_and_is_stored_as_one():
    """A shop that stopped doing cars must not be left reading the absent row as «never asked»."""
    store = _Store()
    run(V.VehicleStore(store).set("t1", True))
    run(V.VehicleStore(store).set("t1", False))

    assert run(V.VehicleStore(store).tracks_vehicle("t1")) is False
    assert run(V.fields_for(store, "t1")) == []
    assert store.rows[(V.VEHICLES, "t1")]["tracks_vehicle"] is False, (
        "the row must SAY no, not vanish — the two are different facts"
    )


def test_one_shops_answer_is_not_another_shops():
    store = _Store()
    run(V.VehicleStore(store).set("t1", True))

    assert run(V.VehicleStore(store).tracks_vehicle("t2")) is False


def test_an_unreadable_row_shows_no_plate_page_rather_than_guessing_one():
    """The two mistakes are not equal: a plate page in a salon is a screen nobody can get past,
    and a missing one costs a tyre shop an optional field on a visit that still records."""
    assert run(V.VehicleStore(_Unreadable()).tracks_vehicle("t1")) is False
    assert run(V.fields_for(_Unreadable(), "t1")) == []


def test_a_missing_tenant_is_never_a_vehicle_shop():
    assert run(V.VehicleStore(_Store()).tracks_vehicle("")) is False
