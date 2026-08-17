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
from app.core.links import LinkError, customer_page, stop_link

BASE = "https://raje3.sa"
REF = "abc123XY_-"


def test_the_link_is_absolute_and_a_phone_can_open_it():
    assert customer_page(BASE, REF) == "https://raje3.sa/p/abc123XY_-"


def test_the_stop_link_is_the_page_plus_one_segment():
    """One file, two functions: a page URL that changes takes the withdrawal link with it."""
    assert stop_link(BASE, REF) == customer_page(BASE, REF) + "/stop"


def test_a_trailing_slash_on_the_base_does_not_double():
    assert customer_page("https://raje3.sa/", REF) == "https://raje3.sa/p/abc123XY_-"


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
