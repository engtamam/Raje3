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
