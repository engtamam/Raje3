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


# ── أ-7 · the discount is data at creation and prose everywhere after ──────────────────────────
def test_the_amount_travels_on_the_row_to_both_readers():
    """`offer_value` was filled into a message slot and went no further: not onto the send log,
    not to `choose_offer`, not to the till, not to the customer's page. So the message says «خصم
    20%» and the operator's screen shows only a sentence — which, when the owner wrote his own
    line, may not restate the amount at all. The employee asks the customer, and the customer's
    word becomes the source.
    """
    from app.core.models import SendLog, as_row

    row = as_row(SendLog(tenant="t1", subject_ref="sub_a", cls="marketing", at=0,
                         offer_text="خصم 20% على الغسيل", offer_expires_at=1,
                         offer_value="20%"))

    assert row["offer_value"] == "20%", "the row is the entitlement, and this is part of it"


# ── ب-4 · «طبّق العرض» wired to a field the route never sent ───────────────────────────────────
def test_the_offer_says_which_services_it_covers(monkeypatch):
    """The field screen reads `offer.service_ids` twice: to decide whether the visit in front of
    the operator is one this offer applies to, and to badge those services in the grid. The route
    answered `{text, expires_at, sent_at}` — so the set was empty on every visit, the apply
    control was never rendered once, and no service ever carried its badge. An offer the operator
    cannot apply is an offer the customer argues about at the counter.
    """
    import asyncio
    import types

    from app.api.v1 import owner as O

    row = {"offer_text": "خصم 20%", "offer_expires_at": 2_000_000_000, "at": 1,
           "offer_value": "20%",
           "offer_services": ["svc_wash", "svc_oil"]}

    class _Store:
        def __init__(self, _):
            pass

        async def active_offer(self, tenant, subject_ref, *, used_refs, now):
            return row

    # PUT BACK AFTERWARDS. These were plain assignments, so the fake store stayed on the module
    # for every test that ran later in the same process — and the next route test to read the send
    # log got an object that answers one method and knows nothing else. It passed alone and failed
    # in the suite, which is the hardest kind of failure to read: a test that lies about a file it
    # never mentions.
    monkeypatch.setattr(O, "SendLogStore", _Store)
    monkeypatch.setattr(O, "spent_refs", lambda **kw: set())
    monkeypatch.setattr(O, "_ops_url", lambda r: "http://ops.invalid")
    monkeypatch.setattr(O, "_ops_token", lambda r: "t" * 40)

    request = types.SimpleNamespace(
        app=types.SimpleNamespace(state=types.SimpleNamespace(
            container=types.SimpleNamespace(datastore=None))))
    principal = types.SimpleNamespace(tenant="t1")

    out = asyncio.run(O.active_offer(request, subject_ref="sub_" + "a" * 24,
                                     principal=principal))

    assert out["offer"]["service_ids"] == ["svc_wash", "svc_oil"], (
        "the screen decides whether this visit is covered, and badges the grid, from this list")
    # AND THE REST OF THE ANSWER IS UNCHANGED: the sentence, the end, the amount. No `code`:
    # the coupon feature is gone, and a key reappearing here is what a half-revert looks like.
    assert out["offer"]["text"] == "خصم 20%" and "code" not in out["offer"]
    assert out["offer"]["value"] == "20%"
