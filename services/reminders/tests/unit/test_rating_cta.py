"""The rating app's own call-to-action line — a whole sentence, never a template-level condition,
never a blank (WhatsApp refuses an empty variable)."""
from __future__ import annotations

from app.core import rating_cta as RC
from app.core import rendering as R

TEMPLATE = {"name": "svc_visit_confirmation_rating_warm", "type": "svc_visit_confirmation_rating",
           "tone": "warm", "active": True, "class": "service",
           "variables": [1, 2, 3, 4], "fills": ["system", "system", "rating_cta", "invite"]}


def _render(rating_points: int):
    return R.render(template=TEMPLATE, system={"1": "أحمد", "2": "مغسلة النخيل"},
                    catalogue={}, owner={}, marketing_consent="never_asked",
                    public_base_url="https://my.raje3.sa", reference="ref1",
                    rating_points=rating_points)


# ── the bare function ────────────────────────────────────────────────────────────────────────
def test_a_configured_points_value_names_it():
    assert RC.line(5) == "شاركنا رأيك بزيارتك واكسب 5 نقطة"


def test_zero_points_is_the_neutral_sentence_not_a_sentence_naming_zero():
    assert RC.line(0) == RC.NO_POINTS
    assert "0" not in RC.line(0)


def test_a_large_points_value_still_reads_as_one_sentence():
    assert RC.line(500) == "شاركنا رأيك بزيارتك واكسب 500 نقطة"


def test_the_neutral_sentence_is_never_empty():
    assert RC.line(0).strip() != ""


# ── through render() ──────────────────────────────────────────────────────────────────────────
def test_render_fills_slot_three_with_the_points_sentence():
    out = _render(5)
    assert out.variables[2] == "شاركنا رأيك بزيارتك واكسب 5 نقطة"


def test_render_fills_slot_three_with_the_neutral_sentence_when_points_are_zero():
    out = _render(0)
    assert out.variables[2] == RC.NO_POINTS


def test_render_never_produces_a_blank_slot_three_either_way():
    for points in (0, 1, 100):
        out = _render(points)
        assert out.variables[2].strip() != ""


def test_rating_points_defaults_to_zero_when_the_caller_does_not_pass_it():
    # an ordinary render() call (every other template) must not have to know this parameter exists
    out = R.render(template=TEMPLATE, system={"1": "أحمد", "2": "مغسلة النخيل"},
                   catalogue={}, owner={}, marketing_consent="never_asked",
                   public_base_url="https://my.raje3.sa", reference="ref1")
    assert out.variables[2] == RC.NO_POINTS


def test_render_still_fills_the_invite_slot_alongside_rating_cta():
    out = _render(5)
    assert "https://my.raje3.sa" in out.variables[3] or out.variables[3]
