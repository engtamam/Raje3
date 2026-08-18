"""A campaign that refuses every customer must not leave the owner an empty screen.

THE CAMPAIGN PATH SAYS NO IN A DIFFERENT SHAPE, and that is how three refusals kept writing
nothing after the scheduled path was fixed. `send_one` has no schedule to close — its own
docstring: «it is decided, sent, and recorded, and nothing waits for it» — so it refuses by
RETURNING `{"sent": False, …}`. Three of its six returns wrote no row:

  · the render failed — which today is every service wording on the fleet, the public base being
    unset;
  · the recipient was erased;
  · WhatsApp's daily ceiling closed mid-run.

An owner who pressed send on a hundred and forty customers and got none of them delivered opened
«رسائلي» and found nothing at all: not a suppression, not a reason, no evidence the campaign had
ever run. The ceiling one is worse than silent — the screen promises «تُكمل من حيث توقّفت», and
without rows nobody can say where it stopped.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.message_sender import CeilingReached, Unsendable
from app.core import engagement as E
from app.core import gate as G
from app.core.stores import SendLogStore
from app.core.tick import Tick

from test_tick import LIB, NAMES, at, run

ECFG = E.EngagementConfig()

#: The wording exists and its class is enabled, so the gate passes it — and then the fourth blank
#: is filled from `link`, which is composed from the public base. This is the live failure.
LINKED_LIB = [{"name": "svc_service_reminder_brief", "type": "svc_service_reminder",
               "tone": "brief", "class": "service", "variables": [1, 2, 3, 4],
               "fills": ["system", "system", "catalogue", "link"], "active": True}]


class Refuses:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls: list = []

    async def send(self, **kw):
        self.calls.append(kw)
        raise self.exc


@pytest.fixture
def st():
    return MemoryDataStore()


# A SERVICE MESSAGE ON THE CAMPAIGN PATH, which is what this path mostly carries: the points
# receipt, the expiry warning, the weekly digest. A marketing row would be refused earlier for
# want of explicit consent — a correct refusal, and a different one from the three under test.
ROW = {"id": "cmp_1", "subject_ref": "sub_a", "cls": "service", "offer_services": ["oil"],
       "template_type": "svc_service_reminder", "kind": "campaign", "branch_id": "jeddah"}


def one(st, sender, *, library=None, base="https://my.example.sa"):
    tick = Tick(store=st, sender=sender, limits=G.Limits(), eng_cfg=ECFG, public_base_url=base)
    return run(tick.send_one("t1", dict(ROW), now=at(10), library=library or LIB,
                             service_names=NAMES, establishment="ورشة النخبة"))


def rows(st):
    return run(SendLogStore(st).since("t1", "sub_a", since=0))


def test_a_render_that_fails_leaves_a_row(st):
    sender = Refuses(RuntimeError("must not be reached"))
    res = one(st, sender, library=LINKED_LIB, base="")
    assert res["sent"] is False
    assert sender.calls == [], "nothing may be sent when nothing could be built"
    assert len(rows(st)) == 1
    assert rows(st)[0]["outcome"] == "suppressed"
    assert "عنوان الموقع العام" in rows(st)[0]["reason"]


def test_an_erased_recipient_leaves_a_row(st):
    res = one(st, Refuses(Unsendable("العميل غير موجود")))
    assert res["sent"] is False
    assert len(rows(st)) == 1
    assert "لا يوجد مستقبِل" in rows(st)[0]["reason"]


def test_the_daily_ceiling_leaves_a_row_so_where_it_stopped_is_answerable(st):
    res = one(st, Refuses(CeilingReached("rate_limit")))
    assert res["sent"] is False
    got = rows(st)
    assert len(got) == 1
    # THE SCREEN PROMISES «تُكمل من حيث توقّفت». This row is the only thing that makes that
    # sentence checkable rather than a hope.
    assert "سقف واتساب اليومي" in got[0]["reason"]
    assert got[0]["branch_id"] == "jeddah"


def test_a_delivered_campaign_message_is_logged_as_sent_not_suppressed(st):
    class Accepts:
        def __init__(self) -> None:
            self.calls: list = []

        async def send(self, **kw):
            self.calls.append(kw)
            return "wamid.1"

    sender = Accepts()
    res = one(st, sender)
    assert res["sent"] is True
    assert len(sender.calls) == 1
    assert [r["outcome"] for r in rows(st)] == ["sent"]
