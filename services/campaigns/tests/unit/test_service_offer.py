"""«عرض على خدمة» — the goal and the cycle lock that makes it safe (spec §10.9.1).

The lock is not politeness. An offer on a service, reaching somebody who took it yesterday, is the
message that loses the permission — he reads a shop that does not know he was there. And it costs
the owner money: a discount on a visit that was coming anyway is a sale sold cheaper.
"""
from __future__ import annotations

import pytest

from app.core import audience as A
from app.core.models import GOAL_TEMPLATE, GOALS, Campaign
from app.core.preview import Preview

DAY = 86400
NOW = 1_700_000_000


def customer(ref, *, service="oil", last_days=None, cycle=90):
    row = {"subject_ref": ref, "last_visit": NOW - 5 * DAY, "visit_count": 4,
           "interval_days": cycle}
    if last_days is not None:
        row["services"] = {service: {"last_visit": NOW - last_days * DAY,
                                     "interval_days": cycle}}
    return row


async def rows(*people):
    async def _read(_tenant):
        return list(people)
    return _read


@pytest.mark.anyio
async def test_the_man_who_took_it_yesterday_is_held_out():
    """90-day cycle, one day ago — 1%. The offer would tell him we do not know he was here."""
    people = [customer("fresh", last_days=1, cycle=90)]
    out = await A.resolve(goal="service_offer", tenant="t1", now=NOW,
                          customers=await rows(*people), service_id="oil")

    assert out.count == 0
    assert out.too_recent == 1


@pytest.mark.anyio
async def test_the_man_at_seventy_percent_is_exactly_who_it_is_for():
    """63 of 90 days. The need has begun to press, and the offer pulls a coming visit into this
    week — which is the only real effect a campaign has."""
    people = [customer("due", last_days=63, cycle=90)]
    out = await A.resolve(goal="service_offer", tenant="t1", now=NOW,
                          customers=await rows(*people), service_id="oil")

    assert out.count == 1
    assert out.too_recent == 0


@pytest.mark.anyio
async def test_just_under_the_threshold_is_still_held():
    """62 of 90. The line is a line — and being able to see it move is what makes it a rule
    rather than a feeling."""
    people = [customer("early", last_days=62, cycle=90)]
    out = await A.resolve(goal="service_offer", tenant="t1", now=NOW,
                          customers=await rows(*people), service_id="oil")

    assert out.count == 0 and out.too_recent == 1


@pytest.mark.anyio
async def test_someone_who_never_took_it_is_included():
    """Silence is not recency. Excluding him would exclude every new customer from every service
    campaign — the opposite of the intent, and invisible until somebody counted."""
    people = [customer("new", last_days=None)]
    out = await A.resolve(goal="service_offer", tenant="t1", now=NOW,
                          customers=await rows(*people), service_id="oil")

    assert out.count == 1


@pytest.mark.anyio
async def test_his_own_rhythm_decides_not_one_date_for_the_shop():
    """Two men, the same 40 days since the service. One changes his oil every 50 days and is due;
    the other every 120 and is nowhere near. One date for the shop would have sent to both."""
    people = [customer("quick", last_days=40, cycle=50),
              customer("slow", last_days=40, cycle=120)]
    out = await A.resolve(goal="service_offer", tenant="t1", now=NOW,
                          customers=await rows(*people), service_id="oil")

    assert [c.subject_ref for c in out.candidates] == ["quick"]
    assert out.too_recent == 1


@pytest.mark.anyio
async def test_the_goal_without_a_service_reaches_nobody():
    """Refused rather than widened to the shop. An announcement wearing a targeted name would let
    the owner read the reach number as proof the targeting worked."""
    people = [customer("anyone", last_days=80)]
    out = await A.resolve(goal="service_offer", tenant="t1", now=NOW,
                          customers=await rows(*people))

    assert out.count == 0


@pytest.mark.anyio
async def test_the_lock_applies_to_no_other_goal():
    """«أعلن جديدك» has no service to measure against, and «رجّع اللي غابوا» is locked from the
    other end by its own definition."""
    people = [customer("fresh", last_days=1, cycle=90)]
    out = await A.resolve(goal="announce", tenant="t1", now=NOW,
                          customers=await rows(*people))

    assert out.count == 1 and out.too_recent == 0


def test_the_goal_is_declared_everywhere_it_must_be():
    assert "service_offer" in GOALS
    assert "service_offer" in GOAL_TEMPLATE
    c = Campaign(tenant="t1", goal="service_offer", service_id="oil")
    # Marketing, like every other offer — the class is never the owner's choice.
    assert c.cls == "marketing"
    # MANUAL. A standing offer would discount the same service for ever, to a rota of people
    # crossing 70%, with nobody ever deciding to stop.
    assert c.trigger == "manual"


def test_the_preview_says_who_was_held_out_and_why():
    p = Preview(reaches=47, too_recent=112)
    assert p.held_out_line == "استُثني 112 لأنهم أخذوا الخدمة قريباً"


def test_it_says_nothing_when_nobody_was_held_out():
    """A permanent «استُثني 0» teaches an owner to stop reading the line — and the line is what
    makes the lock read as intelligence rather than as a number that shrank."""
    assert Preview(reaches=47).held_out_line == ""
