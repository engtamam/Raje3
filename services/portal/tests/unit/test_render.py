"""The page — one document, the shop's face, and no trace of us."""
from __future__ import annotations

import re

from app.core.compose import Page, Section, _normalise_prefs
from app.core.render import render_page
from app.core.theme import build_theme

THEME = build_theme("#0F5F4E")


def page(**over):
    p = Page(reference="tnt-alpha.sub_abc123def456", tenant="tnt-alpha",
             shop_name="ورشة النخبة", brand_colour="#0F5F4E")
    p.prefs = Section(available=True, data=_normalise_prefs({"stopped": {"marketing": True}}))
    p.visits = Section(available=True, data=[{"services": "غيار الزيت", "date": "12 يونيو"}])
    for k, v in over.items():
        setattr(p, k, v)
    return p


def test_it_is_one_document_with_no_external_request():
    """A JavaScript bundle costs the first paint and a webfont costs a round trip before any text
    appears. On the connection this page is opened over, that is the difference between reading it
    and closing it."""
    html = render_page(page(), THEME)
    assert "<script src=" not in html
    assert "<link" not in html
    assert "@import" not in html
    assert "https://" not in html.replace("http-equiv", "")


def test_not_a_trace_of_us_anywhere():
    """Spec 8.6.1. The customer is having a relationship with a workshop, not a platform."""
    html = render_page(page(), THEME)
    for ours in ("راجع", "راجِع", "raje3", "Raje3", "RAJE3"):
        assert ours not in html


def test_the_title_is_the_shops_name_and_carries_no_customer():
    """It shows in a screenshot and in browser history — a name here is the leak this design
    exists to avoid."""
    html = render_page(page(), THEME)
    assert "<title>ورشة النخبة</title>" in html
    # A crude "05" check matched a generated hex colour. What it MEANT is: no customer name, and
    # nothing shaped like a Saudi phone number — so that is what it tests.
    assert "سارة" not in html
    assert not re.search(r"(?:\+?966|0)5\d{8}", html)


def test_it_is_rtl_and_arabic_by_construction():
    html = render_page(page(), THEME)
    assert "<html lang='ar' dir='rtl'>" in html


def test_the_page_is_never_indexed_and_never_leaks_its_referrer():
    """The reference is in the URL: a link out would hand it to whoever is on the other side."""
    html = render_page(page(), THEME)
    assert "noindex" in html and "no-referrer" in html


def test_a_shop_name_with_a_quote_or_a_tag_cannot_break_the_page():
    """A shop name is typed by a person into a form and rendered into HTML."""
    html = render_page(page(shop_name='<script>alert(1)</script>"x'), THEME)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_every_switch_is_a_real_checkbox_that_submits_without_javascript():
    """A div pretending to be a switch is not focusable, not announced by a screen reader, and
    does not submit when the script fails."""
    html = render_page(page(), THEME)
    assert html.count("type='checkbox'") == 5
    assert "<form method='post'" in html
    assert "type='submit'" in html


def test_the_switch_state_reflects_the_customers_choice():
    html = render_page(page(), THEME)
    rows = re.findall(r"value='(\w+)'( checked)?", html)
    state = {c: bool(ch) for c, ch in rows}
    assert state["marketing"] is False and state["service"] is True


def test_unavailable_preferences_render_read_only_and_say_so():
    """Showing togglable switches whose save will fail is worse than admitting it up front."""
    html = render_page(page(prefs=Section(available=False)), THEME)
    assert "type='checkbox'" not in html
    assert "تعذّر تحميل تفضيلاتك" in html


def test_no_visits_and_could_not_load_them_read_differently():
    empty = render_page(page(visits=Section(available=True, data=[])), THEME)
    broken = render_page(page(visits=Section(available=False)), THEME)
    assert "لا زيارات مسجّلة بعد" in empty
    assert "تعذّر تحميل سجلّ زياراتك" in broken


def test_a_page_with_no_shop_name_still_renders():
    """A page saying nothing beats a 500 that says the shop is broken."""
    html = render_page(page(shop_name=""), THEME)
    assert "<title>" in html and "</html>" in html


def test_the_brand_colour_reaches_the_document():
    html = render_page(page(), build_theme("#B91C1C"))
    assert "--accent:#b91c1c" in html.lower()
    assert "theme-color" in html


def test_the_visit_list_is_capped_so_a_reminder_page_is_not_a_receipt():
    many = [{"services": f"خدمة {i}", "date": "1 يناير"} for i in range(50)]
    html = render_page(page(visits=Section(available=True, data=many)), THEME)
    assert html.count("class='v'") == 10


def test_the_whole_document_stays_small():
    """Every kilobyte is a fraction of a second on one bar of signal."""
    html = render_page(page(), THEME)
    assert len(html.encode()) < 12_000, f"{len(html.encode())} bytes"
