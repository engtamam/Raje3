"""أ-6 · the offer that was sent to four hundred people and existed for none of them.

`offer_text` on the send log IS the entitlement — the till, `choose_offer` and the customer's page
all skip a row whose text is blank. It was taken from one place: the owner's free line. Then the
offer templates were built with no free line at all (`fills: [system, system, amount, catalogue,
date]`), so the screen never asked for one and every campaign of that shape recorded a blank.

Nothing failed. The messages went out, correct and specific. The customer walked in with one on his
phone, and the till said «لا يوجد عرضٌ ساري».
"""
from __future__ import annotations

from app.core.offer_text import compose


def test_the_owners_own_line_always_wins():
    """It is what the customer actually read. A different sentence at the counter is how one offer
    becomes an argument about two."""
    assert compose(owner_text="لك غسلة مجانية", value="20%",
                   service_names=["غسيل"], has_expiry=True) == "لك غسلة مجانية"


def test_a_campaign_with_no_free_line_still_records_an_entitlement():
    """THE DEFECT, exactly: structured offer, no owner text, blank on the log."""
    got = compose(value="20%", service_names=["غسيل خارجي"], has_expiry=True)
    assert got == "خصم 20% على غسيل خارجي"


def test_a_discount_with_no_scope_says_only_the_discount():
    assert compose(value="50 ريال", has_expiry=True) == "خصم 50 ريال"


def test_a_scope_with_no_amount_is_still_an_offer():
    assert compose(service_names=["تلميع"], has_expiry=True) == "عرض خاص على تلميع"


def test_an_expiry_alone_is_proof_that_something_was_granted():
    """The last resort, and still better than blank: the shop granted something with an end date,
    and the operator must see that a valid offer exists even when we cannot restate it."""
    assert compose(has_expiry=True) == "عرض خاص"


def test_no_expiry_is_no_offer():
    """An entitlement with no end is a price change nobody decided on, and every reader of this
    field already refuses one. Composing a sentence here would create offers out of ordinary
    marketing messages — the opposite mistake, and the more expensive one."""
    assert compose(owner_text="لك غسلة مجانية", value="20%", has_expiry=False) == ""
    assert compose(value="20%", service_names=["غسيل"], has_expiry=False) == ""
