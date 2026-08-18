"""Whatever the engine refuses, «رسائلي» can show — including the two refusals that showed nothing.

THE SEND LOG IS THE ONLY PLACE A MESSAGE'S EXISTENCE IS RECORDED. Its own docstring says so:
«What went out, or what did not and why.» Nine refusals wrote a row. Two did not, and they are the
two an owner is most likely to ask about:

  · the customer was erased or was never there — the schedule quietly ended and nothing anywhere
    said a message had been owed to anybody;

  · he switched the trigger off — everything already scheduled under it was dropped in silence,
    at exactly the moment he wants to know whether anything went out under it.

Both closed the schedule correctly. Neither left a trace, so «لم يخرج شيء» and «لا سجلّ عندنا»
were the same screen.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.stores import ScheduleStore, SendLogStore

from test_tick import FakeSender, at, go, run, sched


@pytest.fixture
def st():
    return MemoryDataStore()


class SwitchedOff:
    """His choice, as the tick reads it: this trigger is off."""

    @staticmethod
    def enabled(_reason: str) -> bool:
        return False


class NoRecipient:
    """operations answers «this customer is gone» — the shape `Unsendable` is raised for."""

    def __init__(self) -> None:
        self.calls: list = []

    async def send(self, **_kw):
        raise AssertionError("nothing may be sent when there is nobody to send to")


def test_a_trigger_switched_off_leaves_a_row_naming_the_switch(st):
    sched(st, kind="reminder", template_type="svc_service_reminder")
    sender = FakeSender()
    res = go(st, sender, choices=SwitchedOff())

    assert sender.calls == []
    rows = run(SendLogStore(st).since("t1", "sub_a", since=0))
    assert len(rows) == 1, "the record that a message was owed and deliberately not sent"
    assert rows[0]["outcome"] == "suppressed"
    # THE SENTENCE IS THE ANSWER. «موقوفة» on its own would leave him wondering whether we failed;
    # this names his own switch, which is the one cause he can act on.
    assert rows[0]["reason"] == "أوقفتَ هذا النوع من الرسائل"
    assert res.suppressed == 1


def test_the_row_it_writes_carries_the_schedule_and_the_branch(st):
    # WITHOUT THESE THE ROW CANNOT BE READ BACK TO ANYTHING. «كم رسالة وقفت في فرع جدة» is a
    # question about a field, and a row written without one can never be given it later.
    sched(st, branch_id="jeddah")
    go(st, FakeSender(), choices=SwitchedOff())
    row = run(SendLogStore(st).since("t1", "sub_a", since=0))[0]
    assert row["branch_id"] == "jeddah"
    assert row["schedule_id"]


def test_it_still_closes_the_schedule_rather_than_queueing_it_for_ever(st):
    # THE ROW IS AN ADDITION, NOT A REPLACEMENT. A refusal that logs and stays pending would show
    # him a queue that never drains and one new log row every hour.
    sched(st)
    go(st, FakeSender(), choices=SwitchedOff())
    row = run(ScheduleStore(st).get("t1|sub_a|oil|reminder"))
    assert row["state"] == "suppressed"


def test_a_switched_on_trigger_writes_no_suppression(st):
    # THE GUARD MUST NOT FIRE ON THE HAPPY PATH — a log full of suppressions for messages that
    # went out would make the ledger worse than empty.
    sched(st)
    sender = FakeSender()
    go(st, sender)
    assert len(sender.calls) == 1
    assert [r["outcome"] for r in run(SendLogStore(st).since("t1", "sub_a", since=0))] == ["sent"]
