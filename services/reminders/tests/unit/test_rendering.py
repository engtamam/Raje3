"""Template choice and variable filling — including the injection channel this closes."""
from __future__ import annotations

import pytest

from app.core.rendering import (FALLBACK_NAME, RenderError, choose, merged_service_text,
                                render, sanitise_owner_text)

LIB = [
    {"name": "svc_service_reminder_brief", "type": "svc_service_reminder", "tone": "brief",
     "class": "service", "variables": [1, 2, 3], "fills": ["system", "system", "catalogue"],
     "active": True},
    {"name": "svc_service_reminder_warm", "type": "svc_service_reminder", "tone": "warm",
     "class": "service", "variables": [1, 2, 3], "fills": ["system", "system", "catalogue"],
     "active": True},
    {"name": "mkt_offer_brief", "type": "mkt_offer", "tone": "brief", "class": "marketing",
     "variables": [1, 2, 3, 4], "fills": ["system", "system", "owner", "system"], "active": True},
]


def t(name):
    return next(x for x in LIB if x["name"] == name)


# ── the injection channel ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", [
    "خصم على https://evil.example",
    "زورونا على www.example.com",
    "تفاصيل على example.com",
    "اتصل 0501234567",
    "عرض\nجديد",
    "عرض\u200bخفي",
])
def test_an_owner_cannot_smuggle_anything_into_an_approved_template(bad):
    """A free variable inside a template Meta approved goes out under the ESTABLISHMENT'S name and
    counts against OUR quality rating."""
# arabic-indic-digits: intentional — fed in as a value the renderer must refuse.
    with pytest.raises(RenderError):
        sanitise_owner_text(bad)


def test_a_bad_value_is_refused_not_silently_cleaned():
    """An escaped link is still a link a customer reads and retypes, and mangling the text
    produces a message the owner did not write and cannot explain."""
    with pytest.raises(RenderError) as exc:
        sanitise_owner_text("عرض على example.com")
    assert "رابط" in str(exc.value)


def test_ordinary_arabic_text_passes():
    assert sanitise_owner_text("  خصم 20% على غيار الزيت  ") == "خصم 20% على غيار الزيت"


def test_an_overlong_field_is_refused():
    with pytest.raises(RenderError):
        sanitise_owner_text("أ" * 200)


def test_a_catalogue_value_is_sanitised_too():
    """'Picked from a catalogue' describes the UI, not the provenance — the owner types the list."""
    with pytest.raises(RenderError):
        render(template=t("svc_service_reminder_brief"),
               system={"1": "أحمد", "2": "ورشة النخبة"},
               catalogue={"3": "زيت — تفاصيل على example.com"}, owner={})


# ── choosing ───────────────────────────────────────────────────────────────────────────────────
def test_the_tenants_tone_is_honoured():
    assert choose(template_type="svc_service_reminder", tone="warm",
                  library=LIB)["name"].endswith("_warm")


def test_a_retired_tone_falls_back_instead_of_stopping_the_tenant():
    """A configuration mismatch becoming a silent outage is the shape this codebase keeps
    finding."""
    got = choose(template_type="svc_service_reminder", tone="ceremonial", library=LIB)
    assert got["type"] == "svc_service_reminder"


def test_an_inactive_template_is_not_chosen():
    lib = [dict(LIB[0], active=False)]
    with pytest.raises(RenderError):
        choose(template_type="svc_service_reminder", tone="brief", library=lib)


# ── filling ────────────────────────────────────────────────────────────────────────────────────
def test_every_slot_is_filled_from_its_declared_source():
    r = render(template=t("mkt_offer_brief"),
               system={"1": "أحمد", "2": "ورشة النخبة", "4": "31 ديسمبر"},
               catalogue={}, owner={"3": "خصم 20%"})
    assert r.variables == ["أحمد", "ورشة النخبة", "خصم 20%", "31 ديسمبر"]
    assert r.cls == "marketing"


def test_a_customer_with_no_name_still_gets_a_valid_message():
    """The name is optional in our model and a blank variable is a Meta rejection at send time —
    which arrives three days later blaming the wording."""
    r = render(template=t("svc_service_reminder_brief"),
               system={"1": "", "2": "ورشة النخبة"}, catalogue={"3": "غيار الزيت"}, owner={})
    assert r.variables[0] == FALLBACK_NAME


def test_a_missing_system_value_that_is_not_the_name_refuses():
    with pytest.raises(RenderError):
        render(template=t("svc_service_reminder_brief"), system={"1": "أحمد"},
               catalogue={"3": "غيار الزيت"}, owner={})


def test_a_numbering_gap_is_caught_here_too():
    """This side must not depend on the other side having been right."""
    with pytest.raises(RenderError):
        render(template={"name": "x", "type": "x", "class": "service", "variables": [1, 3],
                         "fills": ["system", "system"]},
               system={"1": "أحمد", "3": "س"}, catalogue={}, owner={})


# ── the merged phrase ──────────────────────────────────────────────────────────────────────────
def test_three_services_read_as_one_arabic_phrase():
    assert merged_service_text(["غيار الزيت", "الفلاتر", "الإطارات"]) == \
        "غيار الزيت، الفلاتر والإطارات"


def test_one_service_is_just_itself():
    assert merged_service_text(["غيار الزيت"]) == "غيار الزيت"


def test_seven_services_are_summarised_not_listed():
    """A reminder listing seven services is a receipt, and nobody reads a receipt sent as a
    reminder."""
    out = merged_service_text([f"خدمة {i}" for i in range(1, 8)])
    assert out.endswith("و4 غيرها")


# ── approval, restored now that something can supply it ────────────────────────────────────────
LIB_A = [
    {"name": "svc_x_brief", "type": "svc_x", "tone": "brief", "active": True},
    {"name": "svc_x_warm", "type": "svc_x", "tone": "warm", "active": True},
    {"name": "svc_x_formal", "type": "svc_x", "tone": "formal", "active": True},
]


def test_none_means_not_known_and_skips_the_filter():
    """DELIBERATELY NOT AN EMPTY SET. Empty means nothing may be sent, so a caller that forgot the
    argument would silence the entire product rather than behave as it did before."""
    t = choose(template_type="svc_x", tone="brief", library=LIB_A, approved=None)
    assert t["name"] == "svc_x_brief"


def test_an_approved_template_is_preferred_in_the_chosen_tone():
    t = choose(template_type="svc_x", tone="warm", library=LIB_A,
                 approved={"svc_x_brief", "svc_x_warm"})
    assert t["name"] == "svc_x_warm"


def test_the_tone_is_given_up_before_the_send_is():
    """A shop whose chosen tone is still in review and whose other two are approved sends in a
    different voice. A message in the wrong register reaches the customer; one held for the right
    register does not."""
    t = choose(template_type="svc_x", tone="warm", library=LIB_A, approved={"svc_x_formal"})
    assert t["name"] == "svc_x_formal"


def test_nothing_approved_is_a_different_sentence_from_nothing_existing():
    """One means Meta is still reviewing and the answer is patience; the other means the library
    was never seeded and the answer is us. One message for both sends an owner to support for a
    thing that resolves itself in an hour."""
    with pytest.raises(RenderError) as pending:
        choose(template_type="svc_x", tone="brief", library=LIB_A, approved=set())
    with pytest.raises(RenderError) as missing:
        choose(template_type="svc_nothing", tone="brief", library=LIB_A, approved={"svc_x_brief"})
    assert "مراجعة واتساب" in str(pending.value)
    assert "مراجعة واتساب" not in str(missing.value)


def test_a_paused_or_disabled_template_is_not_sendable():
    """v0.13.5 split the statuses. The filter asks for `approved` rather than excluding `pending`,
    so paused and disabled — and any status added later — stay out by default."""
    with pytest.raises(RenderError):
        # Only the paused one exists in the library; it is absent from the approved set.
        choose(template_type="svc_x", tone="brief",
                 library=[LIB_A[0]], approved={"svc_other"})


# ── the typed blanks: an offer is not free text ────────────────────────────────────────────────
COUPON = {"name": "mkt_coupon_brief", "type": "mkt_coupon", "tone": "brief", "class": "marketing",
          "variables": [1, 2, 3, 4, 5],
          "fills": ["system", "system", "amount", "code", "date"], "active": True}


def _coupon(**over):
    system = {"1": "محمد", "2": "مغسلة النخيل", "3": "20%", "4": "RJ-4F2K", "5": "21 أغسطس"}
    system.update(over)
    return render(template=COUPON, system=system, catalogue={}, owner={})


def test_a_typed_offer_goes_out_whole():
    assert _coupon().variables == ["محمد", "مغسلة النخيل", "20%", "RJ-4F2K", "21 أغسطس"]
    assert _coupon(**{"3": "50 ريال"}).variables[2] == "50 ريال"


@pytest.mark.parametrize("bad", ["خصم كبير", "٢٠٪", "20 %", "120%", "0%", "50 ريال فقط", ""])
def test_a_discount_that_is_not_a_number_never_leaves(bad):
    """«خصم كبير» promises nothing anybody can be held to, and Arabic-Indic digits are unreadable
    on half the phones our customers hold. Refused here rather than at the till."""
    with pytest.raises(RenderError):
        _coupon(**{"3": bad})


def test_an_offer_with_no_end_is_refused():
    """An offer with no last day is an offer for ever, and the shop honours it long after it meant
    to stop. Refusing the send is the cheaper failure."""
    with pytest.raises(RenderError):
        _coupon(**{"5": ""})


@pytest.mark.parametrize("bad", ["rj-4f2k", "RJ 4F2K", "", "RJ-4F2K-99-11"])
def test_a_coupon_code_the_till_cannot_read_never_leaves(bad):
    with pytest.raises(RenderError):
        _coupon(**{"4": bad})
