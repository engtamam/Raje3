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


# ── the routes: what a stranger with a forwarded link can learn, and what the page must not cache
from app.api.page import NO_STORE


def test_the_page_is_never_stored_by_a_proxy_or_a_shared_phone():
    """`private` alone permits a browser to keep it, and a phone shared between a father and his
    son shows the second one the first one's visits after a back button."""
    cc = NO_STORE["Cache-Control"]
    assert "no-store" in cc and "no-cache" in cc and "private" in cc


def test_the_unsubscribe_stops_marketing_only():
    """Someone unsubscribing from offers still wants to know their car is ready — taking that away
    is not what they pressed."""
    import inspect
    from app.api import page as mod
    src = inspect.getsource(mod.stop)
    assert 'stopped=["marketing"]' in src and "merge=True" in src


def test_the_unsubscribe_merges_rather_than_replacing():
    """A stop that turns four other things back on is the opposite of what the customer pressed."""
    import inspect
    from app.adapters.peers import HttpReminders
    src = inspect.getsource(HttpReminders.set_prefs)
    assert "existing" in src and "set(existing) | set(stopped)" in src


def test_a_failed_save_shows_no_confirmation():
    """A customer told their choice was saved who keeps receiving messages does not try again —
    they block the number."""
    import inspect
    from app.adapters.peers import HttpReminders
    assert "return False" in inspect.getsource(HttpReminders.set_prefs)
    from app.api import page as mod
    assert "saved=saved" in inspect.getsource(mod.save_prefs)


def test_an_invalid_reference_makes_no_peer_calls():
    """Otherwise the route is a way to make three services do work on behalf of anyone with a
    URL."""
    import inspect
    src = inspect.getsource(__import__("app.api.page", fromlist=["x"]).page)
    before = src.split("if not r.valid:", 1)[1].split("return", 1)[0]
    assert "composer" not in before


# ── his offers: the reason most people open this link ──────────────────────────────────────────
import time  # noqa: E402

SOON = int(time.time()) + 3 * 86400


def with_offers(*offers):
    return page(offers=Section(available=True, data=list(offers)))


def an_offer(**over):
    o = {"text": "20% على غيار الزيت", "expires_at": SOON, "sent_at": SOON - 86400,
         "services": []}
    o.update(over)
    return o


def test_the_offer_is_the_first_thing_on_the_page():
    """He arrived from a message that offered him something. A page that puts a notification
    setting where the offer should be makes him scroll to find what he was promised — and some of
    them do not."""
    html = render_page(with_offers(an_offer()), THEME)

    assert html.index("عروضك الحصرية") < html.index("الرسائل التي تصلك")
    assert html.index("عروضك الحصرية") < html.index("زياراتك")


def test_the_offer_is_shown_in_its_own_words():
    html = render_page(with_offers(an_offer()), THEME)
    assert "20% على غيار الزيت" in html


def test_what_it_covers_is_said_either_way():
    """"The whole shop" is a real answer and a generous one — leaving it blank would make the most
    generous offer look like the least specified."""
    everything = render_page(with_offers(an_offer()), THEME)
    assert "على كل الخدمات" in everything

    some = render_page(with_offers(an_offer(services=["غيار الزيت", "غسيل"])), THEME)
    assert "غيار الزيت" in some and "غسيل" in some


def test_the_countdown_gets_the_MOMENT_not_a_duration():
    """A duration computed here is wrong the second the page is read and frozen wrong while it
    stays open. And an expiry the customer could extend by changing his phone's clock would be
    worse — the arithmetic is local, the truth is not."""
    html = render_page(with_offers(an_offer()), THEME)

    assert f"data-until='{SOON}'" in html
    # Four cells: days, hours, minutes, SECONDS.
    assert html.count("<div><b>--</b>") == 4
    assert "ثانية" in html and "دقيقة" in html and "ساعة" in html and "يوم" in html


def test_a_phone_whose_script_did_not_run_still_sees_the_end_date():
    """The countdown is an enhancement. Without it the offer must still say when it ends, or a
    failed script leaves a discount with no deadline on it at all."""
    html = render_page(with_offers(an_offer()), THEME)
    assert "cd-fallback" in html
    assert "ينتهي:" in html


def test_a_customer_with_no_offers_is_not_told_he_has_none():
    """No empty card and no "you have no offers". Telling somebody he has been given nothing is a
    worse page than not raising it at all."""
    html = render_page(page(), THEME)
    assert "عروضك الحصرية" not in html


def test_the_offers_section_never_mentions_us():
    """§8.6.1 applies to the newest section as much as to the oldest: the customer is having a
    relationship with a workshop, not with a platform."""
    html = render_page(with_offers(an_offer()), THEME)
    assert "راجع" not in html and "Raje3" not in html.lower()


def test_the_branch_appears_beside_the_service_only_when_the_row_has_one():
    """A chain's customer must be able to tell WHICH of four places he was at.

    And a one-branch shop must not carry a label on all ten rows saying the same thing — a line
    that never varies is one the eye stops reading, taking the date and the service with it.
    """
    with_branch = render_page(page(visits=Section(available=True, data=[
        {"services": "غيار الزيت", "branch": "فرع العليا", "date": "12 يونيو"}])), THEME)
    assert "فرع العليا" in with_branch
    assert "غيار الزيت" in with_branch

    plain = render_page(page(visits=Section(available=True, data=[
        {"services": "غيار الزيت", "date": "12 يونيو"}])), THEME)
    assert "·" not in plain.split("زياراتك")[1].split("</section>")[0]


def test_a_branch_name_cannot_carry_markup_onto_the_page():
    """The name is typed by an owner into his own console and rendered on a PUBLIC page.

    Everything else on this page is escaped; a field added later is exactly the one that gets
    forgotten, and this page is opened from a link in the shop's name.
    """
    html = render_page(page(visits=Section(available=True, data=[
        {"services": "غيار", "branch": "<script>alert(1)</script>", "date": "12 يونيو"}])), THEME)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ── the three the customer pays for (م · قواطع) ────────────────────────────────────────────────


def test_a_failed_offers_read_says_so_rather_than_showing_a_page_without_offers():
    """«AN UNAVAILABLE OFFERS SECTION SAYS SO» — compose.py promised it in writing and render.py
    had no such branch.

    He opened this link FROM a message that offered him something. A page with no offer on it does
    not read to him as «a service is briefly down»; it reads as «that message was not real», and he
    does not come back to check.
    """
    from app.core.compose import Page, Section

    p = Page(reference="r", tenant="t")
    p.offers = Section(available=False, failed=True)

    html = render_page(p, THEME)

    assert "عروضك الحصرية" in html, "the section must appear, saying why it is empty"
    assert "تعذّر" in html
    # AND IT BLAMES US, not him. «لا توجد عروض» would be a claim about his shop.
    assert "عندنا" in html


def test_a_shop_that_simply_sent_him_nothing_is_still_silent():
    """THE OTHER DIRECTION, and it is why the third state had to exist rather than a wider `if`.
    Most customers have no offer waiting, and «تعذّر عرض عروضك» on every one of those pages would
    turn a correct page into an apology — and teach everybody to ignore the sentence on the day it
    is true."""
    from app.core.compose import Page

    html = render_page(Page(reference="r", tenant="t"), THEME)

    assert "عروضك الحصرية" not in html
