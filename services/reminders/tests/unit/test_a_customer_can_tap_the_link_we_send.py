"""The page exists, the message goes out, and the link was never in it.

THE DEFECT. `/p/{ref}` is built, served and documented. `core/consent.py` states the legal rule in
its own words — withdrawal must be one tap at `/p/{ref}/stop` — and every route behind that
sentence works. But no line in any of the six services ever composed `https://<host>/p/{ref}`,
there was no setting naming our public address, and no template fill source could have carried one.

So the page could be reached only by a customer who already knew the address, and the withdrawal
tap that PDPL requires be as easy as granting was, in practice, unreachable. Nothing was red: the
message was accepted, delivered, and reported success.

SABOTAGE CHECK: make `_base` return `raje3.sa` when the setting is empty and
`test_no_address_stops_the_message_rather_than_sending_a_dead_link` fails — which is exactly the
"sensible default" that would have shipped every pilot's customers to somebody else's domain.
"""
from __future__ import annotations

import pytest
from app.core.links import LinkError, customer_page, grant_link, reference_for, stop_link

BASE = "https://raje3.sa"
# THE SHAPE portal ACTUALLY READS: `{tenant}.{subject}`, split on the first dot
# (portal/core/reference.py). This fixture was a bare `abc123XY_-` — a value portal has
# never minted and would parse as invalid — so the two halves of the seam agreed only in
# a test. See `test_a_reference_with_no_separator_is_refused`.
REF = reference_for("tnt_page", "sub_abc123")


def test_the_link_is_absolute_and_a_phone_can_open_it():
    assert customer_page(BASE, REF) == "https://raje3.sa/p/tnt_page.sub_abc123"


def test_the_stop_link_is_the_page_plus_one_segment():
    """One file, two functions: a page URL that changes takes the withdrawal link with it."""
    assert stop_link(BASE, REF) == customer_page(BASE, REF) + "/stop"


def test_a_trailing_slash_on_the_base_does_not_double():
    assert customer_page("https://raje3.sa/", REF) == "https://raje3.sa/p/tnt_page.sub_abc123"


def test_no_address_stops_the_message_rather_than_sending_a_dead_link():
    """THE DEFECT ITSELF. «Not configured» must be loud, never a guess at our own domain."""
    with pytest.raises(LinkError) as caught:
        customer_page("", REF)
    assert "PUBLIC_BASE_URL" in str(caught.value), "the operator is told what to set"


def test_a_base_with_no_scheme_is_refused():
    """`raje3.sa/p/abc` renders as plain text in WhatsApp — visible to nobody but the customer."""
    with pytest.raises(LinkError):
        customer_page("raje3.sa", REF)


@pytest.mark.parametrize("ref", ["", "abc/../admin", "abc?x=1", "abc#frag", "a b", "x" * 129])
def test_a_reference_that_could_redirect_is_refused_not_escaped(ref):
    """A slash or a query character in the reference points the customer somewhere else entirely.

    Refused rather than escaped: a reference needing escape is not one we issued, and quietly
    repairing it would hide whatever produced it.
    """
    with pytest.raises(LinkError):
        customer_page(BASE, ref)


def test_the_stop_link_refuses_on_the_same_terms():
    """The guard must not be on the page link alone — the withdrawal one is the regulated half."""
    with pytest.raises(LinkError):
        stop_link("", REF)
    with pytest.raises(LinkError):
        stop_link(BASE, "abc/../admin")


# ── the seam that had never been crossed ──────────────────────────────────────────────────────
def test_a_reference_with_no_separator_is_refused():
    """WHAT THIS CATCHES, AND IT WOULD HAVE SHIPPED. portal mints `{tenant}.{subject}` and this
    module's pattern excluded the dot, so every address it could compose — the mandatory one-tap
    stop included — would have been refused at render. It was invisible because no template in the
    library declared a link slot: the producer and the consumer had never met.
    """
    with pytest.raises(LinkError):
        customer_page(BASE, "sub_abc123")


def test_the_grant_link_is_the_page_plus_one_segment():
    """The only door marketing consent can come through, composed beside the other two so that a
    change to the page URL cannot leave it behind."""
    assert grant_link(BASE, REF) == customer_page(BASE, REF) + "/allow"


def test_the_reference_is_built_the_way_portal_reads_it():
    assert reference_for("tnt_page", "sub_abc123") == "tnt_page.sub_abc123"


@pytest.mark.parametrize("part", ["", "a/b", "a?x=1", "a.b", "x" * 129])
def test_a_part_that_could_redirect_never_reaches_a_url(part):
    """Refused rather than escaped — including a dot INSIDE a part, which would move the separator
    and hand portal a different tenant than the one we meant."""
    with pytest.raises(LinkError):
        reference_for("tnt_page", part)
    with pytest.raises(LinkError):
        reference_for(part, "sub_abc123")
