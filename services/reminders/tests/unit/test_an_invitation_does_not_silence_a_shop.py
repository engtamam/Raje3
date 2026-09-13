"""A visit confirmation goes out with no customer page in the world; a promotion still may not.

WHAT WAS ACTUALLY WRONG, AFTER COUNTING RATHER THAN ASSUMING. Everyone — including this file's
author — described the outage as «the mandatory stop link points at a portal that is off». The
library says otherwise: all thirty `stop_link` wordings are MARKETING, and the thirty-six that
failed to render carry `invite` — the marketing opt-in invitation riding in the last line of
service, personal and warning texts.

So the shop's entire ordinary traffic was being killed to protect the perfection of an invitation.

THE TWO LINES ARE NOT THE SAME KIND OF THING:

  · the stop link is the customer's one-tap exit from marketing. It is required, and a promotional
    message without it must not go — refusing to render is correct and stays;
  · the invitation is an offer to opt in. A visit confirmation is lawful without it, and a shop
    whose customers hear nothing because we could not address an invitation has been failed by us.

The decision: «ما يحتاج رابط او ايقاف للخدمية … نبغاه رابط التسويقية هو الوحيد».
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import invite as I
from app.core import links as L
from app.core.stores import SendLogStore

from test_tick import FakeSender, at, go, run, sched


@pytest.fixture
def st():
    return MemoryDataStore()


#: A service wording whose last blank is the invitation — the shape of all fifteen.
INVITING_LIB = [{"name": "svc_service_reminder_brief", "type": "svc_service_reminder",
                 "tone": "brief", "class": "service", "variables": [1, 2, 3, 4],
                 "fills": ["system", "system", "catalogue", "invite"], "active": True}]

#: A promotional wording carrying the exit — the shape of all thirty.
STOPPING_LIB = [{"name": "mkt_offer_brief", "type": "mkt_offer", "tone": "brief",
                 "class": "marketing", "variables": [1, 2, 3, 4],
                 "fills": ["system", "system", "catalogue", "stop_link"], "active": True}]


def test_the_invitation_becomes_words_when_there_is_no_address():
    line = I.line(consent="never_asked", public_base_url="", reference="t1.sub_a")
    # NOT EMPTY — Meta refuses a blank variable — and carrying no link it cannot promise.
    assert line == I.NOT_GRANTED_NO_LINK
    assert "http" not in line


def test_it_still_carries_the_link_the_moment_there_is_one():
    # THE DEGRADATION IS NOT A REMOVAL. The day the page opens, the invitation is an invitation
    # again with no template touched and no deployment step.
    line = I.line(consent="never_asked", public_base_url="https://my.example.sa",
                  reference="t1.sub_a")
    assert "https://my.example.sa" in line


def test_the_stop_link_still_refuses_because_that_one_is_the_law():
    # A PROMOTIONAL MESSAGE WITHOUT AN EXIT MUST NOT GO. If this ever starts returning prose, the
    # product is sending marketing nobody can turn off.
    with pytest.raises(L.LinkError):
        L.stop_link("", "t1.sub_a")


def test_a_service_message_goes_out_with_no_public_page_at_all(st):
    sched(st)
    sender = FakeSender()
    res = go(st, sender, library=INVITING_LIB, public_base_url="")

    assert len(sender.calls) == 1, "the confirmation the shop's customer is waiting for"
    assert res.sent == 1
    rows = run(SendLogStore(st).since("t1", "sub_a", since=0))
    assert [r["outcome"] for r in rows] == ["sent"]


def test_the_same_pass_would_not_send_a_promotion(st):
    # THE OTHER HALF OF THE RULE, ON THE SAME BENCH. Softening the invitation must not soften the
    # exit: this is the assertion that keeps the two apart.
    sched(st, cls="marketing", template_type="mkt_offer")
    sender = FakeSender()
    go(st, sender, library=STOPPING_LIB, public_base_url="")
    assert sender.calls == []


def test_no_consent_line_claims_a_benefit_the_shop_may_not_have():
    """THIS WAS CAUGHT TWICE, AND THE SECOND TIME IS THE ONE WORTH KEEPING.

    The first fix corrected only the line used when there is no address. The LINKED one — the one
    that actually goes out once a shop has a public page — still said «ولك عندنا مزايا خاصة», and
    the granted line said «ومزاياك الخاصة مفعّلة». Both assert that this shop is running something
    for this customer. We do not know that. A shop may have no offer at all, and then a message in
    the shop's name has told his customer something untrue — at the moment right after a visit,
    when the customer trusts it most.

    WHAT IS TRUE WHATEVER THE SHOP IS DOING is the channel, never the contents: would you like our
    offers to reach you on WhatsApp, and yes they will reach you there. So every line here is
    about WHERE a message arrives, and none of them about what it will contain.
    """
    for line in (I.NOT_GRANTED, I.GRANTED, I.WITHDRAWN, I.NOT_GRANTED_NO_LINK):
        assert "مزايا" not in line and "مزاياك" not in line, line
        # AND NO PRICE OR DISCOUNT EITHER, for the separate reason that a utility text which sells
        # is re-categorised by Meta as marketing — and then it needs consent to be sent at all.
        assert "خصم" not in line and "%" not in line, line
