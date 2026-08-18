"""Stopping a reminder for a CAR stops that reminder, and not a copy of it.

FOUND ON THE CLUSTER, IN TWO ROWS THAT SHOULD HAVE BEEN ONE:

    a76d…|sub_3de4…|ast_b0a6…|srv_149b…|reminder   state=pending     <- the tick reads this
    a76d…|sub_3de4…|srv_149b…|reminder             state=cancelled   <- the press landed here

The owner pressed «أوقفها». The screen said done. The audit recorded it. `reason` reads «ألغاه
المالك». And the reminder was still pending, and would still have gone out.

WHY IT ONLY HAPPENED TO CARS, WHICH IS TO SAY: TO THIS PRODUCT'S CORE MARKET. `Schedule.key` grew
a car segment when the cycle moved from the customer to the vehicle — «ممكن عندي سيارتين برقمي».
Three writers rebuilt that key by hand and none of them grew it, so each wrote to a key that
exists only in their own imagination. For a shop with no cars the two spellings are identical and
everything worked; for بنشر and مغسلة nothing did.

AND NOTHING CAUGHT IT, which is the part worth keeping. Nine hundred and fifty-seven tests passed
before this fix and after it: every one that cancels a schedule cancels one with no car. The
defect lived in the gap between a field that was added and the tests that were not.

Three behaviours, and the middle one is the whole reason this file exists:

  · a cancel by kind (what a new visit does — spec 5.6) reaches the car's own row;
  · the owner's «أوقفها» reaches it too, by id;
  · and the two cars of one customer stay two, because that is what the segment is for.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Schedule, as_row, key_of
from app.core.stores import ScheduleStore

from test_tick import at, run


@pytest.fixture
def st():
    return MemoryDataStore()


def _car_reminder(**over):
    d = dict(tenant="t1", subject_ref="sub_a", service_id="oil", kind="reminder",
             due_at=at(9), cls="service", template_type="svc_service_reminder",
             asset_id="ast_car1")
    d.update(over)
    return Schedule(**d)


def test_the_key_a_row_is_written_under_is_the_key_it_is_read_back_by(st):
    # THE SMALLEST STATEMENT OF THE DEFECT. `key_of` on a stored row must equal `Schedule.key` on
    # the object it came from — if these two ever disagree again, every writer disagrees with
    # every reader and nothing says so.
    sch = _car_reminder()
    row = as_row(sch)
    assert key_of(row) == sch.key
    assert "ast_car1" in sch.key, "the car is part of the name, or the second car overwrites the first"


def test_a_new_visit_cancels_last_months_reminder_for_that_car(st):
    """SPEC 5.6, AND IT NEVER WORKED FOR A CAR. Asking «how was your oil change?» while the
    customer is standing at the counter for the next one is the bug the cancel exists to stop."""
    store = ScheduleStore(st)
    sch = _car_reminder()
    run(store.upsert("t1", sch.key, as_row(sch)))

    stopped = run(store.cancel_kind("t1", "sub_a", "oil", "reminder",
                                    reason="زيارة جديدة", now=at(10)))
    assert stopped == 1

    # READ BACK AT THE KEY THE SCHEDULER USED — the only key anything else will ever look at.
    after = run(store.get(sch.key))
    assert after is not None, "the row vanished from its own key"
    assert after["state"] == "cancelled", "the row the tick reads is still pending"

    # AND NO SECOND ROW. The old code wrote the cancelled copy beside the original; a store that
    # now holds two rows for one intention will eventually send one of them.
    rows, _ = run(store._find("t1", {"subject_ref": "sub_a"}, limit=50))
    assert len(rows) == 1, f"the cancel duplicated the row instead of updating it: {len(rows)}"


def test_the_owner_stopping_it_stops_the_row_the_tick_reads(st):
    """«أوقفها» — the press whose screen said done while the message stayed pending."""
    store = ScheduleStore(st)
    sch = _car_reminder()
    run(store.upsert("t1", sch.key, as_row(sch)))

    # What the API does: find by id, then write back under the recomputed key.
    found, _ = run(store._find("t1", {"id": sch.id}, limit=1))
    row = found[0]
    row["state"] = "cancelled"
    row["reason"] = "ألغاه المالك"
    run(store.upsert("t1", key_of(row), row))

    pending = run(store.pending_for_subject("t1", "sub_a"))
    assert pending == [], "the owner stopped it and it is still waiting to go out"


def test_two_cars_of_one_customer_keep_two_schedules(st):
    # WHY THE SEGMENT EXISTS AT ALL. Without it the second car's oil change UPDATED the first
    # car's reminder, and one whole car fell silently out of the product.
    store = ScheduleStore(st)
    first = _car_reminder(asset_id="ast_car1")
    second = _car_reminder(asset_id="ast_car2")
    run(store.upsert("t1", first.key, as_row(first)))
    run(store.upsert("t1", second.key, as_row(second)))

    rows, _ = run(store._find("t1", {"subject_ref": "sub_a"}, limit=50))
    assert len(rows) == 2

    # AND CANCELLING BY KIND TAKES BOTH, because a visit that services the customer's cars is not
    # a visit that services one of them — the caller narrows by service, not by car.
    stopped = run(store.cancel_kind("t1", "sub_a", "oil", "reminder",
                                    reason="زيارة جديدة", now=at(10)))
    assert stopped == 2
    assert run(store.pending_for_subject("t1", "sub_a")) == []
