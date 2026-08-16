"""أ-4 · what his page says an offer covers — and the state it had no words for.

The scope had two renderings and needed three. «على: {names}» when we could name the services, and
«على كل الخدمات» for everything else — where «everything else» silently included «this offer IS
limited and the names did not reach us». So a discount on one service was printed to the customer
as covering the whole shop, and he found that out at the counter, in front of somebody who had to
refuse him.
"""
from __future__ import annotations

import time

import pytest


def _page(offers):
    from app.core.compose import Page, Section
    from app.core.render import render_page
    from app.core.theme import build_theme

    page = Page(reference="ref_1", tenant="t_1", shop_name="مغسلة")
    page.offers = Section(available=True, data=offers)
    return render_page(page, build_theme(None))


def _offer(**over):
    row = {"text": "خصم 20%", "expires_at": int(time.time()) + 86_400, "sent_at": 0,
           "services": [], "scoped": False, "code": ""}
    row.update(over)
    return row


def test_named_services_are_printed_as_words():
    html = _page([_offer(services=["غسيل خارجي"], scoped=True)])
    assert "على: غسيل خارجي" in html


def test_an_offer_on_everything_still_says_so():
    """The generous case must not lose its sentence: a blank scope on the widest offer would make
    it read as the least specified one."""
    assert "على كل الخدمات" in _page([_offer()])


def test_a_limited_offer_we_cannot_name_is_not_promised_as_the_whole_shop():
    html = _page([_offer(services=[], scoped=True)])
    assert "على كل الخدمات" not in html, "this offer is limited — saying otherwise is a promise"
    assert "على خدمات محدّدة" in html


def test_the_code_is_rendered_when_it_arrives():
    """It reaches the page now (the feed emits it), and the page has always been ready to show
    it — large, `dir=ltr`, to be read across a counter."""
    html = _page([_offer(code="RJ-7K2M")])
    assert "RJ-7K2M" in html


def test_the_discount_is_stated_and_not_only_implied():
    """أ-7 · the sentence may be the owner's own line, which need not name the amount at all."""
    html = _page([_offer(text="لك مفاجأة عندنا", value="20%")])
    assert "الخصم: 20%" in html


def test_an_offer_with_no_typed_amount_says_nothing_about_one():
    """Inventing «الخصم: » with nothing after it would be worse than the silence it replaces."""
    assert "الخصم:" not in _page([_offer()])
