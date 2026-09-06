"""The weekly digest message (core/digest.py) — focused on the rating line (rating-app-feature.md
phase 6): zero ratings drops the line entirely, the average is a real decimal, the unhandled count
is accurate and itself drops when zero, and the line is among those a too-long report trims first.
"""
from __future__ import annotations

from app.core.digest import OWNER_TEXT_MAX, build

TENANT_SHOP = "مغسلة النخيل"


def _snapshot(**values) -> dict:
    return {"visits": 10, "values": {"visits_week": {"visits": 5, "previous": None}, **values}}


def test_no_ratings_this_week_prints_no_line():
    msg = build(snapshot=_snapshot(), ratings_count=0)
    assert "تقييمات" not in msg["text"]


def test_a_shop_without_the_rating_app_sees_no_line_either():
    """Same code path as "no ratings this week" — the peer answers 0 for a shop that never
    bought the app, and the line drops exactly the same way, with no special case needed."""
    msg = build(snapshot=_snapshot())
    assert "تقييمات" not in msg["text"]


def test_the_average_is_a_real_decimal_not_rounded_to_an_integer():
    msg = build(snapshot=_snapshot(), ratings_count=3, ratings_average=4.7)
    assert "4.7/5 (3)" in msg["text"]


def test_the_unhandled_count_matches_exactly_and_is_a_separate_line():
    msg = build(snapshot=_snapshot(), ratings_count=5, ratings_average=4.0, ratings_unhandled=2)
    assert "تقييمات الأسبوع: 4.0/5 (5)" in msg["text"]
    assert "بانتظار المعالجة: 2" in msg["text"]


def test_zero_unhandled_drops_that_one_line_but_keeps_the_average():
    msg = build(snapshot=_snapshot(), ratings_count=5, ratings_average=4.0, ratings_unhandled=0)
    assert "تقييمات الأسبوع" in msg["text"]
    assert "بانتظار المعالجة" not in msg["text"]


def test_the_rating_line_is_among_those_dropped_first_when_the_report_runs_long():
    """The rating line sits after points (line 7) and before the audience/associations lines
    (8-9) — a report long enough to need trimming drops it before a MORE important earlier line,
    never the other way, since trimming happens from the end."""
    long_shop = "أ" * 200   # forces the header itself to eat into the budget
    msg_with = build(snapshot=_snapshot(new_vs_returning={"new": 3, "returning": 2}),
                     ratings_count=5, ratings_average=4.9, ratings_unhandled=1, shop=long_shop)
    assert len(msg_with["text"]) <= OWNER_TEXT_MAX
    # The earlier, more important lines (new/returning customers) must have survived the trim.
    assert "عملاء جدد" in msg_with["text"]


def test_ratings_summary_fields_never_break_a_report_that_has_none_of_them():
    """Backward compatibility: every existing caller that never passes the three new kwargs must
    get byte-identical behaviour to before this feature shipped."""
    msg = build(snapshot=_snapshot(new_vs_returning={"new": 4, "returning": 1}))
    assert "تقييمات" not in msg["text"]
    assert "عملاء جدد: 4" in msg["text"]


# ── flow_action_data — the report Flow's own data (rating-app-feature.md phase 6b) ──────────────
def test_flow_action_data_carries_every_key_the_published_screen_declares():
    """Every `show_*`/`*_text` pair report-flow.json's own `data` schema declares must be present
    — a Flow's flow_action_data supplies every placeholder the screen declares, not only the
    ones with something to show (the `visible` binding is what hides the rest)."""
    msg = build(snapshot=_snapshot())
    expected_keys = {
        "header_text",
        "show_visits", "visits_text", "show_new", "new_text",
        "show_returning", "returning_text", "show_at_risk", "at_risk_text",
        "show_top_service", "top_service_text", "show_messages", "messages_text",
        "show_ceiling", "ceiling_text", "show_points", "points_text",
        "show_ratings", "ratings_text", "show_unhandled", "unhandled_text",
        "show_consented", "consented_text", "show_associations", "associations_text",
    }
    assert expected_keys <= set(msg["flow_action_data"].keys())


def test_flow_action_data_hides_a_zero_section_the_same_way_the_text_does():
    msg = build(snapshot=_snapshot())
    fd = msg["flow_action_data"]
    assert fd["show_ratings"] is False
    assert fd["ratings_text"] == ""
    assert fd["show_new"] is False


def test_flow_action_data_shows_exactly_what_the_text_line_shows():
    msg = build(snapshot=_snapshot(new_vs_returning={"new": 4, "returning": 1}),
               ratings_count=3, ratings_average=4.7, ratings_unhandled=1)
    fd = msg["flow_action_data"]
    assert fd["show_new"] is True and fd["new_text"] == "4"
    assert fd["show_ratings"] is True and fd["ratings_text"] == "4.7/5 (3)"
    assert fd["show_unhandled"] is True and fd["unhandled_text"] == "1"


def test_flow_action_data_still_shows_a_section_the_plain_text_had_to_trim():
    """The Flow screen and the plain-text teaser are allowed to disagree on length — trimming
    only pops entries off the text `lines` list, never off `flow`, so a shop with a genuinely
    full week still sees everything on the Flow screen even if the text version had to cut its
    last line or two."""
    long_shop = "أ" * 200
    msg = build(snapshot=_snapshot(new_vs_returning={"new": 3, "returning": 2}),
               ratings_count=5, ratings_average=4.9, ratings_unhandled=2, shop=long_shop)
    assert msg["flow_action_data"]["show_ratings"] is True
    assert msg["flow_action_data"]["show_unhandled"] is True


def test_flow_action_data_header_matches_the_text_headers_own_shop_name():
    msg = build(snapshot=_snapshot(), shop="مغسلة النخيل")
    assert msg["flow_action_data"]["header_text"] == "أسبوعك في مغسلة النخيل"
