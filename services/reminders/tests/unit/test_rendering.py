"""Template choice and variable filling — including the injection channel this closes."""
from __future__ import annotations

import pytest

from app.core.rendering import (FALLBACK_NAME, RenderError, choose,
                                merged_service_text, render, sanitise_owner_text)

LIB = [
    {"name": "svc_service_reminder_brief", "type": "svc_service_reminder", "tone": "brief",
     "class": "service", "variables": [1, 2, 3], "fills": ["system", "system", "catalogue"],
     "active": True},
    {"name": "svc_service_reminder_masculine", "type": "svc_service_reminder", "tone": "masculine",
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
    assert sanitise_owner_text("  خصم 20% على قص شعر  ") == "خصم 20% على قص شعر"


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
    assert choose(template_type="svc_service_reminder", tone="masculine",
                  library=LIB)["name"].endswith("_masculine")


def test_a_retired_tone_falls_back_instead_of_stopping_the_tenant():
    """A configuration mismatch becoming a silent outage is the shape this codebase keeps
    finding."""
    got = choose(template_type="svc_service_reminder", tone="ceremonial", library=LIB)
    assert got["type"] == "svc_service_reminder"


def test_an_inactive_template_is_not_chosen():
    lib = [dict(LIB[0], active=False)]
    with pytest.raises(RenderError):
        choose(template_type="svc_service_reminder", tone="brief", library=lib)


# ── the photo+button shape (2026-09-13) ───────────────────────────────────────────────────────
_PLAIN_M = {"name": "mkt_offer_masculine", "type": "mkt_offer", "tone": "masculine",
           "class": "marketing", "variables": [1, 2], "fills": ["system", "system"],
           "active": True, "shape": "plain"}
_PLAIN_F = {"name": "mkt_offer_feminine", "type": "mkt_offer", "tone": "feminine",
           "class": "marketing", "variables": [1, 2], "fills": ["system", "system"],
           "active": True, "shape": "plain"}
_PB_M = {"name": "mkt_offer_masculine_photo_button", "type": "mkt_offer", "tone": "masculine",
        "class": "marketing", "variables": [1, 2], "fills": ["system", "system"],
        "active": True, "shape": "photo_button"}
_PB_F = {"name": "mkt_offer_feminine_photo_button", "type": "mkt_offer", "tone": "feminine",
        "class": "marketing", "variables": [1, 2], "fills": ["system", "system"],
        "active": True, "shape": "photo_button"}
_SHAPE_LIB = [_PLAIN_M, _PLAIN_F, _PB_M, _PB_F]


def test_the_default_want_shape_picks_the_plain_row():
    got = choose(template_type="mkt_offer", tone="masculine", library=_SHAPE_LIB)
    assert got["name"] == "mkt_offer_masculine"


def test_want_shape_photo_button_picks_the_photo_button_row_when_its_active():
    got = choose(template_type="mkt_offer", tone="masculine", library=_SHAPE_LIB,
                 want_shape="photo_button")
    assert got["name"] == "mkt_offer_masculine_photo_button"


def test_want_shape_photo_button_honours_the_tone_too():
    got = choose(template_type="mkt_offer", tone="feminine", library=_SHAPE_LIB,
                 want_shape="photo_button")
    assert got["name"] == "mkt_offer_feminine_photo_button"


def test_want_shape_photo_button_falls_back_to_plain_when_the_variant_is_inactive():
    """A shop whose photo-button variant is still under Meta review must keep sending the plain
    wording — never refuse the whole message over a shape that has not cleared review."""
    lib = [_PLAIN_M, _PLAIN_F, dict(_PB_M, active=False), dict(_PB_F, active=False)]
    got = choose(template_type="mkt_offer", tone="masculine", library=lib,
                 want_shape="photo_button")
    assert got["name"] == "mkt_offer_masculine"


def test_want_shape_photo_button_falls_back_to_plain_when_not_yet_approved():
    got = choose(template_type="mkt_offer", tone="masculine", library=_SHAPE_LIB,
                 want_shape="photo_button", approved={"mkt_offer_masculine"})
    assert got["name"] == "mkt_offer_masculine"


def test_want_shape_photo_button_falls_back_to_plain_when_no_such_row_exists_at_all():
    got = choose(template_type="mkt_offer", tone="masculine", library=[_PLAIN_M, _PLAIN_F],
                 want_shape="photo_button")
    assert got["name"] == "mkt_offer_masculine"


def test_a_row_with_no_shape_field_at_all_defaults_to_plain():
    """Every row this feature predates (the whole rest of the library) must keep behaving
    exactly as before — absent `shape` reads as "plain", not as some unmatched fourth value."""
    old_style = {k: v for k, v in _PLAIN_M.items() if k != "shape"}
    got = choose(template_type="mkt_offer", tone="masculine", library=[old_style])
    assert got["name"] == "mkt_offer_masculine"


def test_want_shape_plain_is_never_overridden_by_an_active_approved_variant():
    """The caller decides the shape; an active photo_button row sitting in the library must never
    be picked just because it happens to be there."""
    got = choose(template_type="mkt_offer", tone="masculine", library=_SHAPE_LIB,
                 want_shape="plain")
    assert got["name"] == "mkt_offer_masculine"


def test_the_own_template_bypasses_shape_filtering_entirely():
    """A shop's own submitted text has no variant family — `want_shape` must not touch this
    branch at all."""
    own_row = {"variables": [1], "fills": ["system"]}
    got = choose(template_type="mkt_offer", tone="masculine", library=_SHAPE_LIB,
                 want_shape="photo_button", own="his_own_template", own_row=own_row)
    assert got["name"] == "his_own_template" and got["own"] is True


def test_want_shape_photo_button_still_falls_back_across_a_retired_tone():
    """Tone fallback and shape filtering compose: a retired tone still finds SOME photo_button
    row rather than raising, exactly like the plain-shape fallback already does."""
    got = choose(template_type="mkt_offer", tone="ceremonial", library=_SHAPE_LIB,
                 want_shape="photo_button")
    assert got["type"] == "mkt_offer" and got.get("shape") == "photo_button"


def test_a_photo_button_only_library_with_no_plain_row_still_serves_the_variant():
    got = choose(template_type="mkt_offer", tone="masculine", library=[_PB_M, _PB_F],
                 want_shape="photo_button")
    assert got["name"] == "mkt_offer_masculine_photo_button"


def test_neither_shape_present_refuses_rather_than_guessing():
    """Asking for a variant of a type this library never seeded any active row of at all — not
    even a plain one — must raise the same way an entirely unknown type already does."""
    with pytest.raises(RenderError):
        choose(template_type="mkt_offer", tone="masculine",
              library=[dict(_PLAIN_M, active=False), dict(_PLAIN_F, active=False)],
              want_shape="photo_button")


def test_want_shape_photo_button_ignores_the_approval_filter_when_approval_is_unknown():
    """`approved=None` means "not known", and skips the filter entirely — the shape filter must
    still run on top of that, same composition as the tone/ladder logic below it."""
    got = choose(template_type="mkt_offer", tone="masculine", library=_SHAPE_LIB,
                 want_shape="photo_button", approved=None)
    assert got["name"] == "mkt_offer_masculine_photo_button"


def test_an_unrecognised_want_shape_value_falls_back_to_plain():
    """A typo or a future value nothing seeds yet must never raise nor pick something
    unexpected — it behaves exactly like asking for a variant that does not exist."""
    got = choose(template_type="mkt_offer", tone="masculine", library=_SHAPE_LIB,
                 want_shape="banana")
    assert got["name"] == "mkt_offer_masculine"


def test_the_ladder_still_varies_the_rung_within_the_chosen_shape():
    """`tone_index` must operate on the SHAPE-FILTERED set, not the whole library — a second rung
    of a photo_button send must not silently hop back to the plain shape."""
    second_masc_pb = dict(_PB_M, name="mkt_offer_masculine_photo_button_2")
    lib = [_PLAIN_M, _PLAIN_F, _PB_M, second_masc_pb, _PB_F]
    got = choose(template_type="mkt_offer", tone="masculine", library=lib,
                 want_shape="photo_button", tone_index=2)
    assert got["name"] == "mkt_offer_masculine_photo_button_2"


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
               system={"1": "", "2": "ورشة النخبة"}, catalogue={"3": "قص شعر"}, owner={})
    assert r.variables[0] == FALLBACK_NAME


def test_a_customer_name_with_a_link_is_refused_not_sent():
    """REAL BUG, found by audit and fixed: the customer's own name (slot 1) is the one `system`
    value an ADVERSARY, not the shop, can author — any customer can set their own WhatsApp display
    name. It must go through sanitise_owner_text like every other free-text slot, not slip through
    the catch-all `system` branch unsanitised."""
    with pytest.raises(RenderError):
        render(template=t("svc_service_reminder_brief"),
               system={"1": "احجز الآن على x.com", "2": "ورشة النخبة"},
               catalogue={"3": "قص شعر"}, owner={})


def test_a_customer_name_with_a_newline_is_refused_not_sent():
    with pytest.raises(RenderError):
        render(template=t("svc_service_reminder_brief"),
               system={"1": "أحمد\nمدير التسويق", "2": "ورشة النخبة"},
               catalogue={"3": "قص شعر"}, owner={})


def test_a_normal_customer_name_still_passes_through_unchanged():
    """The fix must not break the overwhelmingly common case: an ordinary name."""
    r = render(template=t("svc_service_reminder_brief"),
               system={"1": "محمد العتيبي", "2": "ورشة النخبة"}, catalogue={"3": "قص شعر"}, owner={})
    assert r.variables[0] == "محمد العتيبي"


def test_a_missing_system_value_that_is_not_the_name_refuses():
    with pytest.raises(RenderError):
        render(template=t("svc_service_reminder_brief"), system={"1": "أحمد"},
               catalogue={"3": "قص شعر"}, owner={})


def test_a_numbering_gap_is_caught_here_too():
    """This side must not depend on the other side having been right."""
    with pytest.raises(RenderError):
        render(template={"name": "x", "type": "x", "class": "service", "variables": [1, 3],
                         "fills": ["system", "system"]},
               system={"1": "أحمد", "3": "س"}, catalogue={}, owner={})


# ── the merged phrase ──────────────────────────────────────────────────────────────────────────
def test_three_services_read_as_one_arabic_phrase():
    assert merged_service_text(["قص شعر", "الفلاتر", "الإطارات"]) == \
        "قص شعر، الفلاتر والإطارات"


def test_one_service_is_just_itself():
    assert merged_service_text(["قص شعر"]) == "قص شعر"


def test_seven_services_are_summarised_not_listed():
    """A reminder listing seven services is a receipt, and nobody reads a receipt sent as a
    reminder."""
    out = merged_service_text([f"خدمة {i}" for i in range(1, 8)])
    assert out.endswith("و4 غيرها")


# ── approval, restored now that something can supply it ────────────────────────────────────────
LIB_A = [
    {"name": "svc_x_brief", "type": "svc_x", "tone": "brief", "active": True},
    {"name": "svc_x_masculine", "type": "svc_x", "tone": "masculine", "active": True},
    {"name": "svc_x_formal", "type": "svc_x", "tone": "formal", "active": True},
]


def test_none_means_not_known_and_skips_the_filter():
    """DELIBERATELY NOT AN EMPTY SET. Empty means nothing may be sent, so a caller that forgot the
    argument would silence the entire product rather than behave as it did before."""
    t = choose(template_type="svc_x", tone="brief", library=LIB_A, approved=None)
    assert t["name"] == "svc_x_brief"


def test_an_approved_template_is_preferred_in_the_chosen_tone():
    t = choose(template_type="svc_x", tone="masculine", library=LIB_A,
                 approved={"svc_x_brief", "svc_x_masculine"})
    assert t["name"] == "svc_x_masculine"


def test_the_tone_is_given_up_before_the_send_is():
    """A shop whose chosen tone is still in review and whose other two are approved sends in a
    different voice. A message in the wrong register reaches the customer; one held for the right
    register does not."""
    t = choose(template_type="svc_x", tone="masculine", library=LIB_A, approved={"svc_x_formal"})
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
# NO `code` FILL ANY MORE — the coupon feature is gone, and with it the only library template that
# ever declared one. What remains typed is the discount and the end date, and both are still
# checked here for the same reason they always were: a bad value must stop ONE message rather than
# reach a customer under the shop's name.
TYPED = {"name": "mkt_offer_brief", "type": "mkt_offer", "tone": "brief", "class": "marketing",
         "variables": [1, 2, 3, 4],
         "fills": ["system", "system", "amount", "date"], "active": True}


def _typed(**over):
    system = {"1": "محمد", "2": "مغسلة النخيل", "3": "20%", "4": "21 أغسطس"}
    system.update(over)
    return render(template=TYPED, system=system, catalogue={}, owner={})


def test_a_typed_offer_goes_out_whole():
    assert _typed().variables == ["محمد", "مغسلة النخيل", "20%", "21 أغسطس"]
    assert _typed(**{"3": "50 ريال"}).variables[2] == "50 ريال"


@pytest.mark.parametrize("bad", ["خصم كبير", "٢٠٪", "20 %", "120%", "0%", "50 ريال فقط", ""])
def test_a_discount_that_is_not_a_number_never_leaves(bad):
    """«خصم كبير» promises nothing anybody can be held to, and Arabic-Indic digits are unreadable
    on half the phones our customers hold. Refused here rather than at the till."""
    with pytest.raises(RenderError):
        _typed(**{"3": bad})


def test_an_offer_with_no_end_is_refused():
    """An offer with no last day is an offer for ever, and the shop honours it long after it meant
    to stop. Refusing the send is the cheaper failure."""
    with pytest.raises(RenderError):
        _typed(**{"4": ""})


def test_a_code_blank_is_no_longer_a_source_this_renderer_knows():
    """THE DROPPED FEATURE, ASSERTED. `code` used to be a typed source with its own branch and its
    own regex; the branch is gone, so a template still declaring it falls through to the
    owner-slot path and REFUSES rather than quietly emitting whatever sat in that numbered slot."""
    stale = dict(TYPED, fills=["system", "system", "amount", "code"])
    with pytest.raises(RenderError):
        render(template=stale, system={"1": "محمد", "2": "م", "3": "20%", "4": "RJ-4F2K"},
               catalogue={}, owner={})


# ── the campaign path: one slot, one answer ────────────────────────────────────────────────────
from app.core.rendering import arabic_date, campaign_slots   # noqa: E402

OFFER = {"name": "mkt_offer_brief", "type": "mkt_offer", "class": "marketing",
         "variables": [1, 2, 3, 4, 5],
         "fills": ["system", "system", "amount", "catalogue", "date"], "active": True}
ANNOUNCE = {"name": "mkt_announcement_brief", "type": "mkt_announcement", "class": "marketing",
            "variables": [1, 2, 3], "fills": ["system", "system", "owner"], "active": True}


def test_the_owners_sentence_no_longer_lands_in_two_slots_at_once():
    """It used to fill 3 AND 4 through all three source dicts, so a four-variable template said
    the same thing twice — «باقة تنظيف كامل من مغسلة النخيل: تنظيف كامل»."""
    slots = campaign_slots(OFFER, establishment="مغسلة النخيل", owner_text="عرض الصيف",
                           service_text="غسيل خارجي", offer_value="20%",
                           expires_at=1_755_000_000)
    assert slots["3"] == "20%"
    assert slots["4"] == "غسيل خارجي"
    assert slots["4"] != slots["3"]
    assert slots["5"] == arabic_date(1_755_000_000)


def test_slot_one_is_left_for_the_sender_because_the_name_is_not_ours_to_hold():
    """This service holds a pseudonym. The name is resolved beside the phone number, at the last
    moment, and nowhere else."""
    assert campaign_slots(ANNOUNCE, establishment="م", owner_text="جديدنا")["1"] == ""


def test_an_offer_with_no_value_refuses_rather_than_sending_a_hole():
    slots = campaign_slots(OFFER, establishment="مغسلة النخيل", owner_text="عرض",
                           service_text="غسيل", offer_value="", expires_at=1_755_000_000)
    with pytest.raises(RenderError):
        render(template=OFFER, system=slots, catalogue=slots, owner=slots)


@pytest.mark.parametrize("good", ["20%", "5%", "90%", "50 ريال", "12.50 ريال"])
def test_the_send_accepts_exactly_what_the_screen_accepted(good):
    """THE SAME CASES AS `campaigns/tests/unit/test_preview.py`, DELIBERATELY. These two validators
    are read at different moments — campaigns while the owner types, this one at the send — and
    nothing but a gate keeps them equal. If this list and that one ever disagree, one of the two
    services is refusing an offer the other already told him was fine, and by then the campaign has
    launched. `ci/check_the_offer_a_shop_types_is_judged_the_same_everywhere.py` compares the
    patterns; these two tests compare the behaviour."""
    slots = campaign_slots(OFFER, establishment="مغسلة النخيل", owner_text="عرض",
                           service_text="غسيل", offer_value=good, expires_at=1_755_000_000)
    render(template=OFFER, system=slots, catalogue=slots, owner=slots)


@pytest.mark.parametrize("bad", ["خصم كبير", "٢٠٪", "20 %", "120%", "0%", "50 ريال فقط", "50"])
def test_the_send_refuses_exactly_what_the_screen_refused(bad):
    slots = campaign_slots(OFFER, establishment="مغسلة النخيل", owner_text="عرض",
                           service_text="غسيل", offer_value=bad, expires_at=1_755_000_000)
    with pytest.raises(RenderError):
        render(template=OFFER, system=slots, catalogue=slots, owner=slots)


def test_an_offer_with_no_end_refuses_too():
    slots = campaign_slots(OFFER, establishment="مغسلة النخيل", owner_text="عرض",
                           service_text="غسيل", offer_value="20%", expires_at=0)
    with pytest.raises(RenderError):
        render(template=OFFER, system=slots, catalogue=slots, owner=slots)


# ── the campaign's own composed reward (occasion pilot, 2026-09-13) ────────────────────────────
OCCASION = {"name": "mkt_personal_occasion_masculine", "type": "mkt_personal_occasion",
           "class": "marketing", "variables": [1, 2, 3, 4],
           "fills": ["system", "system", "reward", "stop_link"], "active": True}


def test_reward_discount_composes_the_same_sentence_the_body_used_to_hardcode():
    slots = campaign_slots(OCCASION, establishment="مغسلة النخيل", owner_text="",
                           service_text="غسيل خارجي", offer_value="20%")
    assert slots["3"] == "لك خصم 20% على غسيل خارجي"


def test_reward_discount_with_no_scope_names_nothing():
    """An unscoped discount just says the number — no dangling «على »."""
    slots = campaign_slots(OCCASION, establishment="مغسلة النخيل", owner_text="",
                           service_text="", offer_value="20%")
    assert slots["3"] == "لك خصم 20%"


def test_reward_gift_names_the_service():
    slots = campaign_slots(OCCASION, establishment="مغسلة النخيل", owner_text="",
                           service_text="تنظيف كامل", reward_type="gift")
    assert slots["3"] == "هديتك: تنظيف كامل"


def test_reward_gift_with_no_service_refuses_rather_than_sending_a_hole():
    with pytest.raises(RenderError):
        campaign_slots(OCCASION, establishment="م", owner_text="", service_text="",
                       reward_type="gift")


def test_reward_points_composes_the_credit_sentence():
    slots = campaign_slots(OCCASION, establishment="مغسلة النخيل", owner_text="",
                           reward_type="points", reward_points=50)
    assert slots["3"] == "منحناك 50 نقطة هدية"


def test_reward_points_with_no_count_refuses_rather_than_sending_a_hole():
    with pytest.raises(RenderError):
        campaign_slots(OCCASION, establishment="م", owner_text="",
                       reward_type="points", reward_points=0)


def test_reward_discount_with_no_value_refuses_rather_than_sending_a_hole():
    with pytest.raises(RenderError):
        campaign_slots(OCCASION, establishment="م", owner_text="", offer_value="")


REWARD_ONLY = {"name": "mkt_personal_occasion_masculine", "type": "mkt_personal_occasion",
               "class": "marketing", "variables": [1, 2, 3],
               "fills": ["system", "system", "reward"], "active": True}


def test_reward_is_answered_by_meaning_too_since_render_dispatches_it_there():
    """`render` routes a "reward" fill through `OWNER_SLOTS`/`by_meaning` — the same name already
    used elsewhere for an unrelated sentence — so `campaign_slots` must answer under that key too,
    not only under the slot's own number."""
    slots = campaign_slots(REWARD_ONLY, establishment="مغسلة النخيل", owner_text="",
                           service_text="غسيل خارجي", offer_value="20%")
    assert slots["reward"] == slots["3"]
    out = render(template=REWARD_ONLY, system=slots, catalogue=slots, owner=slots,
                by_meaning=slots)
    assert out.variables[2] == "لك خصم 20% على غسيل خارجي"


def test_a_plain_announcement_still_carries_the_owners_one_sentence():
    slots = campaign_slots(ANNOUNCE, establishment="مغسلة النخيل", owner_text="افتتحنا فرعاً")
    out = render(template=ANNOUNCE, system=slots, catalogue=slots, owner=slots)
    assert out.variables == [FALLBACK_NAME, "مغسلة النخيل", "افتتحنا فرعاً"]


def test_the_end_date_is_riyadh_not_utc():
    """An offer ending at 01:00 UTC ends the previous evening for the person reading it."""
    # 2025-08-14 22:30 UTC is already the 15th in Riyadh.
    assert arabic_date(1_755_210_600) == "15 أغسطس"


# ── the owner's own sentence arrives as he wrote it (ح-1) ──────────────────────────────────────


def test_an_owners_blank_is_filled_by_meaning_not_by_position():
    """THE MESSAGE THAT WENT OUT WAS NOT THE MESSAGE HE APPROVED.

    `custom_templates.check()` validates his blanks against the OWNER vocabulary — `customer`,
    `service`, `reward` … — and stores those names. `render()` knew only its own six sources and
    dropped every other name into an `else` that reads `system[NUMBER]`: the LIBRARY row's meaning
    for that position. So «هلا {{1}}، جاهز {{2}} عندنا» with `[customer, service]` sent «هلا محمد،
    جاهز مغسلة النخيل عندنا» — slot 2 is the shop name in the library's layout.

    And the preview fills by meaning and was right, so he approved one sentence and his customers
    received another, in his name, with nothing in any log saying so.
    """
    from app.core import rendering as R

    out = R.render(
        template={"name": "own_1", "type": "svc_service_reminder", "class": "service",
                  "variables": [1, 2], "fills": ["customer", "service"]},
        # The positional dicts still carry the LIBRARY's layout: 2 is the shop.
        system={"1": "محمد", "2": "مغسلة النخيل"},
        catalogue={}, owner={},
        by_meaning={"customer": "محمد", "shop": "مغسلة النخيل", "service": "تلميع"})

    assert out.variables == ["محمد", "تلميع"], "slot 2 is his SERVICE, not the shop's name"


def test_a_meaning_with_no_value_refuses_rather_than_filling_by_position():
    """Falling back to the number is what produced the wrong sentence; keeping it behind a nicer
    name would keep the defect. A refusal costs one message and is visible in the send log."""
    import pytest as _pytest

    from app.core import rendering as R

    with _pytest.raises(R.RenderError):
        R.render(
            template={"name": "own_2", "type": "svc_service_reminder", "class": "service",
                      "variables": [1, 2], "fills": ["customer", "reward"]},
            system={"1": "محمد", "2": "مغسلة النخيل"},
            catalogue={}, owner={},
            by_meaning={"customer": "محمد"})


def test_the_customer_name_still_falls_back_when_the_shop_never_took_one():
    """A name is optional in our model, and an empty one is a Meta rejection at send time — so
    this one meaning falls back rather than refusing, exactly as the positional path always did."""
    from app.core import rendering as R

    out = R.render(
        template={"name": "own_3", "type": "svc_service_reminder", "class": "service",
                  "variables": [1], "fills": ["customer"]},
        system={}, catalogue={}, owner={}, by_meaning={"customer": ""})

    assert out.variables == [R.FALLBACK_NAME]


# --- د-7 · the rung's voice ---------------------------------------------------------------------

_TONES = [{"name": "svc_service_reminder_brief", "type": "svc_service_reminder", "tone": "brief",
           "class": "service", "active": True},
          {"name": "svc_service_reminder_masculine", "type": "svc_service_reminder", "tone": "masculine",
           "class": "service", "active": True},
          {"name": "svc_service_reminder_formal", "type": "svc_service_reminder", "tone": "formal",
           "class": "service", "active": True}]


def test_the_second_rung_does_not_repeat_the_first_word_for_word():
    """د-7 · `tone_index` was stamped on every rung from the first day and read by NOBODY.

    So the second rung was the first rung: same type, same tone, same sentence, days apart. §5.6.1
    calls the ladder «تنويع لا تصعيد», and a customer who receives one sentence twice is the shape
    that gets reported — and a reported number is a banned number.
    """
    first = choose(template_type="svc_service_reminder", tone="brief", library=_TONES,
                     tone_index=1)
    second = choose(template_type="svc_service_reminder", tone="brief", library=_TONES,
                      tone_index=2)

    assert first["name"] != second["name"]
    assert first["tone"] == "brief", "rung one is the shop's own chosen voice, unchanged"


def test_everything_that_is_not_a_rung_still_gets_the_shops_own_tone():
    """The default must not move. Every confirmation, follow-up and campaign in the product calls
    this function without an index, and a shop that chose «brief» chose it for all of them."""
    for index in (0, 1, None):
        got = choose(template_type="svc_service_reminder", tone="masculine", library=_TONES,
                       **({} if index is None else {"tone_index": index}))
        assert got["tone"] == "masculine"


def test_a_shop_with_one_template_still_sends_the_second_rung():
    """A library with a single active tone must not lose the rung to an index it cannot honour —
    the variation is worth giving up, the message is not."""
    one = [_TONES[0]]

    got = choose(template_type="svc_service_reminder", tone="brief", library=one, tone_index=2)

    assert got["name"] == "svc_service_reminder_brief"


def test_the_line_the_screen_approved_is_the_line_this_will_carry():
    """The twin of `test_the_line_he_approves_is_the_line_that_can_be_sent` in campaigns. If this
    cap were ever the tighter of the two, the owner's sentence would pass the screen he wrote it on
    and die at the send — and he would hear about it from a customer, not from us."""
    assert sanitise_owner_text("ا" * 60) == "ا" * 60
    with pytest.raises(RenderError):
        sanitise_owner_text("ا" * 61)


# ── type_status: the one owner of "what does this shop-facing row say about itself" ─────────────
from app.core.rendering import type_status  # noqa: E402

_STATUS_LIBRARY = [
    {"name": "mkt_winback_masculine", "type": "mkt_winback", "tone": "masculine", "active": True},
    {"name": "mkt_winback_feminine", "type": "mkt_winback", "tone": "feminine", "active": True},
]


def test_a_type_with_no_library_rows_is_not_seeded():
    assert type_status("mkt_ghost", library=_STATUS_LIBRARY, statuses={}) == "not_seeded"


def test_an_unreadable_peer_is_unknown_never_not_registered():
    """`statuses=None` means the peer could not be asked — drawing "never submitted" from an
    outage would tell an owner to act on a fact nobody actually checked."""
    assert type_status("mkt_winback", library=_STATUS_LIBRARY, statuses=None) == "unknown"


def test_a_seeded_type_never_registered_for_this_tenant():
    assert type_status("mkt_winback", library=_STATUS_LIBRARY, statuses={}) == "not_registered"


def test_approved_wins_even_if_the_other_tone_is_still_pending():
    statuses = {"mkt_winback_masculine": "approved", "mkt_winback_feminine": "pending"}
    assert type_status("mkt_winback", library=_STATUS_LIBRARY, statuses=statuses) == "approved"


def test_pending_beats_paused_and_disabled():
    statuses = {"mkt_winback_masculine": "paused", "mkt_winback_feminine": "pending"}
    assert type_status("mkt_winback", library=_STATUS_LIBRARY, statuses=statuses) == "pending"


def test_rejected_only_when_nothing_better_is_true_of_any_tone():
    statuses = {"mkt_winback_masculine": "rejected", "mkt_winback_feminine": "rejected"}
    assert type_status("mkt_winback", library=_STATUS_LIBRARY, statuses=statuses) == "rejected"
