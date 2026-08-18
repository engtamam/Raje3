"""A message that keeps throwing stops, says so, and is counted while it tries.

WHAT IT USED TO DO. `_fail` returned the row to `pending` with `due_at = now + 3600` and no memory
of how many times it had done so. For the failure it was written for — a peer briefly away — that
is right. For the others it was a loop with no exit: a number Meta refuses, a template rejected for
this shop alone, a malformed row. The same inputs raise the same exception on every tick, for as
long as the establishment exists.

Nothing was recorded, because the send log only hears about attempts that got as far as being
attempted; nothing was closed, so the row was in no report; and the owner had a customer who was
never messaged and no row to ask about.

THE THREE FACTS THIS FILE HOLDS: it still retries (an outage must not cost a message), it counts
(so the count survives the process that dies mid-deploy), and it eventually ends the way every
other refusal ends — a line in the send log carrying the last error, and a closed schedule.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.stores import ScheduleStore, SendLogStore
from app.core.tick import MAX_ATTEMPTS

from test_tick import at, go, run, sched


@pytest.fixture
def st():
    return MemoryDataStore()


class AlwaysRefuses:
    """The peer that will never accept THIS message — the case the old retry could not end."""

    def __init__(self) -> None:
        self.calls: list = []

    async def send(self, **kw):
        self.calls.append(kw)
        raise RuntimeError("رفض دائم من الطرف الآخر")


KEY = "t1|sub_a|oil|reminder"


def _tick(st, sender, hour):
    return go(st, sender, now=at(hour))


def test_it_still_retries_because_an_outage_must_not_cost_a_message(st):
    sched(st)
    sender = AlwaysRefuses()
    res = _tick(st, sender, 10)

    assert res.failed == 1
    row = run(ScheduleStore(st).get(KEY))
    assert row["state"] == "pending", "one failure is not a verdict"
    assert row["attempts"] == 1


def test_the_count_lives_on_the_row_so_a_restart_does_not_reset_it(st):
    # THE TICK IS A PROCESS THAT DIES — that is what a deploy is, and deploys are when failures
    # cluster. A counter held anywhere but the row would start again at zero each time.
    sched(st)
    sender = AlwaysRefuses()
    _tick(st, sender, 10)
    _tick(st, sender, 12)
    assert run(ScheduleStore(st).get(KEY))["attempts"] == 2


def test_it_gives_up_at_the_bound_and_writes_the_last_error(st):
    sched(st)
    sender = AlwaysRefuses()
    for i in range(MAX_ATTEMPTS):
        _tick(st, sender, 10)
        # Each pass leaves the row due an hour later; the fixture's clock does not need to move
        # for the next call, because `due_at` is compared against the `now` we hand it.
        row = run(ScheduleStore(st).get(KEY))
        if row["state"] != "pending":
            break
        row["due_at"] = at(10)
        run(ScheduleStore(st).upsert("t1", KEY, row))

    row = run(ScheduleStore(st).get(KEY))
    assert row["state"] == "suppressed", "the loop has an exit now"
    assert row["attempts"] == MAX_ATTEMPTS

    rows = run(SendLogStore(st).since("t1", "sub_a", since=0))
    assert len(rows) == 1, "the one line saying this message was owed and will not be sent"
    assert rows[0]["outcome"] == "suppressed"
    # THE LAST ERROR TRAVELS. «توقّفنا» alone would leave support guessing at what to fix.
    assert "رفض دائم من الطرف الآخر" in rows[0]["reason"]


def test_after_giving_up_it_asks_the_peer_nothing_further(st):
    sched(st)
    sender = AlwaysRefuses()
    for _ in range(MAX_ATTEMPTS + 5):
        _tick(st, sender, 10)
        row = run(ScheduleStore(st).get(KEY))
        if row["state"] == "pending":
            row["due_at"] = at(10)
            run(ScheduleStore(st).upsert("t1", KEY, row))

    # NOT ONE CALL PER HOUR FOR EVER. The count is the whole point: past the bound the peer is not
    # asked again about a message it has refused twenty times.
    assert len(sender.calls) == MAX_ATTEMPTS
