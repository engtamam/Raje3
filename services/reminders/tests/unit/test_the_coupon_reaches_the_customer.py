"""A code minted for one person, and a wording with a place to put it.

WHAT WAS TRUE UNTIL THIS FILE. `tick.py` mints a coupon for every campaign send that carries an
offer — `COUPONS.code_for(idempotency_key)`, stable for the same send for ever — and hands it to
`campaign_slots`, which fills the blank whose source is `code`. Not one of the four offer goals'
wordings HAD such a blank. `mkt_coupon` did, and no goal could select it.

So the code was computed, passed down two function calls, matched against a slot nobody declared,
and dropped. Nothing failed. Nothing was logged. #245 — a code unique to one customer, spent once,
that measures whether the campaign worked — reached nobody, and would have gone on reaching nobody
because a message with a missing blank is not a message with an error: it is a message that is one
sentence shorter.

WHAT THIS PINS, AND IT IS THE CHAIN RATHER THAN EITHER END:

  · the offer wordings a shop can actually send declare a `code` blank;
  · `campaign_slots` puts the minted code IN that blank;
  · and the code that comes out is the one `coupons.code_for` made for that send, not a new one.
"""
from __future__ import annotations

import json
import pathlib

from app.core import coupons as COUPONS
from app.core.rendering import campaign_slots

SEED = pathlib.Path(__file__).resolve().parents[4] / "deploy" / "seed" / "templates.json"

#: The goals that put something on the table. Each mints a coupon on every send, so each needs a
#: wording that can carry one — read from `campaigns/core/models.py::GOAL_TEMPLATE`, which is the
#: only place that decides.
OFFER_TEMPLATES = ("mkt_offer", "mkt_winback", "mkt_personal_occasion")


def _seed() -> dict:
    return {t["name"]: t for t in json.loads(SEED.read_text(encoding="utf-8"))["types"]}


def test_every_offer_wording_has_somewhere_to_put_the_code():
    library = _seed()
    for name in OFFER_TEMPLATES:
        assert name in library, f"{name} vanished from the seed"
        assert "code" in library[name]["fills"], (
            f"{name} states a discount and has no blank for the coupon — the code is minted for "
            f"every one of its sends and thrown away")


def test_the_code_in_the_message_is_the_code_that_was_minted():
    """THE WHOLE CHAIN, END TO END: a send's idempotency key becomes a code becomes a slot."""
    library = _seed()
    template = library["mkt_offer"]
    minted = COUPONS.code_for("camp_1|sub_a|run_3")
    assert minted, "no code for a real send key"

    # `campaign_slots` answers PER NUMBERED SLOT, so it needs the slot numbers as the library
    # hands them over — the seed states the blanks by their kind (`fills`) and the numbers are
    # implied by their order, which is what the library expands before the renderer sees a row.
    row = dict(template, variables=list(range(1, len(template["fills"]) + 1)))
    values = campaign_slots(
        row,
        establishment="مغسلة النخيل",
        owner_text="",
        service_text="غسيل خارجي",
        offer_value="20%",
        coupon_code=minted,
        expires_at=1_800_000_000)

    assert minted in values.values(), (
        f"the minted code never reached a slot: {values}")
    # AND IT IS THE ONE THE CUSTOMER WILL READ, in the blank the wording declares for it.
    position = str(template["fills"].index("code") + 1)
    assert values[position] == minted


def test_a_send_with_no_offer_carries_no_code_rather_than_an_empty_one():
    """Meta REFUSES an empty variable, so «no coupon» must not arrive as a blank string in a
    template that declares one. The engine mints only when the offer has an end date, and this is
    the reading that proves the two agree rather than merely coexist."""
    assert COUPONS.code_for("") == ""
