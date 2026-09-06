"""The rating app's own facts on a visit — rating, feedback text, and the handled-by-owner mark.

Foundation phase: these fields are written by a later phase's WhatsApp Flow webhook and by the
console's «التقييمات» tab; nothing here sends anything or checks app ownership. This only proves
the shape holds, round-trips through the real store, and does not disturb an ordinary visit.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Visit
from app.core.stores import VisitStore

T = "tnt_rating"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store():
    return VisitStore(MemoryDataStore())


def _visit(**over) -> Visit:
    base = dict(id="vis_1", tenant=T, customer_id="cus_1", service_ids=["svc_1"],
                created=1_000, occurred_at=1_000)
    base.update(over)
    return Visit(**base)


# ── defaults on a brand-new visit ─────────────────────────────────────────────────────────────
def test_an_ordinary_visit_carries_no_rating_by_default():
    v = _visit()
    assert v.rating == 0
    assert v.feedback_text == ""
    assert v.rated_at == 0
    assert v.rating_handled_at == 0
    assert v.rating_handled_note == ""


def test_public_reports_the_same_zero_defaults():
    p = _visit().public()
    assert p["rating"] == 0
    assert p["feedback_text"] == ""
    assert p["rated_at"] == 0
    assert p["rating_handled_at"] == 0
    assert p["rating_handled_note"] == ""


def test_public_still_carries_every_pre_existing_field_unchanged():
    p = _visit(package_id="pkg_1", offer_ref="off_1").public()
    assert p["package_id"] == "pkg_1"
    assert p["offer_ref"] == "off_1"
    assert p["customer_id"] == "cus_1"


# ── a rated visit ──────────────────────────────────────────────────────────────────────────────
def test_a_five_star_rating_with_a_comment_is_held_exactly():
    v = _visit(rating=5, feedback_text="خدمة ممتازة", rated_at=2_000)
    assert v.rating == 5
    assert v.feedback_text == "خدمة ممتازة"
    assert v.rated_at == 2_000


def test_a_rating_with_no_comment_is_held_as_an_empty_string_not_none():
    v = _visit(rating=3, rated_at=2_000)
    assert v.feedback_text == ""
    p = v.public()
    assert p["feedback_text"] == ""


def test_every_star_value_one_through_five_round_trips(store):
    for i, stars in enumerate((1, 2, 3, 4, 5)):
        v = _visit(id=f"vis_star_{i}", rating=stars, rated_at=1_000 + i)
        run(store.save(v))
        got = run(store.get(T, v.id))
        assert got.rating == stars


def test_a_long_comment_is_not_truncated_by_the_model_itself(store):
    long_text = "تعليق طويل جداً " * 200
    v = _visit(rating=2, feedback_text=long_text)
    run(store.save(v))
    got = run(store.get(T, v.id))
    assert got.feedback_text == long_text


def test_arabic_emoji_and_mixed_script_comments_round_trip_intact(store):
    text = "ممتاز 👍🔥 excellent service! 5/5"
    v = _visit(rating=5, feedback_text=text)
    run(store.save(v))
    got = run(store.get(T, v.id))
    assert got.feedback_text == text


# ── handling — set only by a human, from the console ─────────────────────────────────────────
def test_marking_a_rating_handled_stores_the_time_and_the_note(store):
    v = _visit(rating=1, feedback_text="الخدمة تأخرت كثيراً")
    run(store.save(v))
    v.rating_handled_at = 3_000
    v.rating_handled_note = "تواصلنا معه واعتذرنا"
    run(store.save(v))
    got = run(store.get(T, v.id))
    assert got.rating_handled_at == 3_000
    assert got.rating_handled_note == "تواصلنا معه واعتذرنا"


def test_an_unhandled_rating_reports_zero_handled_at_never_a_sentinel(store):
    v = _visit(rating=2)
    run(store.save(v))
    assert run(store.get(T, v.id)).rating_handled_at == 0


def test_handling_one_visit_does_not_touch_a_sibling_visit(store):
    a = _visit(id="vis_a", rating=1)
    b = _visit(id="vis_b", rating=1)
    run(store.save(a)); run(store.save(b))
    a.rating_handled_at = 5_000
    run(store.save(a))
    assert run(store.get(T, "vis_a")).rating_handled_at == 5_000
    assert run(store.get(T, "vis_b")).rating_handled_at == 0


# ── a rating of zero is "not yet", never a real one ───────────────────────────────────────────
def test_zero_is_not_a_valid_star_value_by_convention_never_written_as_one():
    # The model itself does not enforce 1-5 (that belongs to whatever writes it, later phases) —
    # this pins the CONVENTION so a future writer knows what "not yet" must look like.
    assert _visit().rating == 0


# ── backward compatibility — an old row minted before these fields existed ───────────────────
def test_an_old_row_with_none_of_the_new_keys_still_loads(store):
    old_row = {"id": "vis_old", "tenant": T, "customer_id": "cus_old",
               "service_ids": ["svc_1"], "created": 500, "occurred_at": 500}
    run(store._s.put("visits", f"{T}|{old_row['id']}", old_row))
    got = run(store.get(T, "vis_old"))
    assert got.rating == 0
    assert got.feedback_text == ""
    assert got.rating_handled_at == 0


def test_an_old_row_migrated_this_way_can_still_be_rated_and_saved(store):
    old_row = {"id": "vis_old2", "tenant": T, "customer_id": "cus_old",
               "service_ids": ["svc_1"], "created": 500, "occurred_at": 500}
    run(store._s.put("visits", f"{T}|{old_row['id']}", old_row))
    v = run(store.get(T, "vis_old2"))
    v.rating = 4
    v.rated_at = 900
    run(store.save(v))
    got = run(store.get(T, "vis_old2"))
    assert got.rating == 4
    assert got.rated_at == 900


# ── the fields save through the store exactly like every other field ─────────────────────────
def test_saving_a_visit_writes_every_rating_field_to_the_row(store):
    v = _visit(rating=5, feedback_text="رائع", rated_at=1_100,
              rating_handled_at=1_200, rating_handled_note="شكرناه")
    run(store.save(v))
    got = run(store.get(T, v.id))
    assert (got.rating, got.feedback_text, got.rated_at,
            got.rating_handled_at, got.rating_handled_note) == (
        5, "رائع", 1_100, 1_200, "شكرناه")


def test_two_visits_by_the_same_customer_carry_independent_ratings(store):
    a = _visit(id="vis_x", rating=5)
    b = _visit(id="vis_y", rating=1)
    run(store.save(a)); run(store.save(b))
    assert run(store.get(T, "vis_x")).rating == 5
    assert run(store.get(T, "vis_y")).rating == 1


def test_a_free_visit_can_still_be_rated_like_any_other():
    v = _visit(free=True, rating=4)
    assert v.free is True
    assert v.rating == 4


def test_a_package_visit_can_still_be_rated_like_any_other():
    v = _visit(package_id="pkg_9", rating=3)
    assert v.package_id == "pkg_9"
    assert v.rating == 3


# ── VisitStore.ratings — the console's «التقييمات» tab query (rating-app-feature.md phase 5) ────
def test_ratings_returns_only_visits_that_were_actually_rated(store):
    run(store.save(_visit(id="vis_rated", rating=4, rated_at=1_000)))
    run(store.save(_visit(id="vis_unrated", rating=0)))
    rows, _ = run(store.ratings(T))
    ids = [v.id for v in rows]
    assert "vis_rated" in ids
    assert "vis_unrated" not in ids


def test_ratings_filters_by_an_exact_star_value(store):
    run(store.save(_visit(id="vis_5", rating=5, rated_at=1_000)))
    run(store.save(_visit(id="vis_2", rating=2, rated_at=1_001)))
    rows, _ = run(store.ratings(T, stars=5))
    assert [v.id for v in rows] == ["vis_5"]


def test_ratings_with_no_stars_filter_returns_every_rank(store):
    for i, stars in enumerate((1, 2, 3, 4, 5)):
        run(store.save(_visit(id=f"vis_{stars}", rating=stars, rated_at=1_000 + i)))
    rows, _ = run(store.ratings(T))
    assert len(rows) == 5


def test_ratings_handled_false_is_an_exact_native_filter(store):
    run(store.save(_visit(id="vis_open", rating=3, rated_at=1_000)))
    run(store.save(_visit(id="vis_done", rating=3, rated_at=1_001,
                          rating_handled_at=2_000, rating_handled_note="تم")))
    rows, _ = run(store.ratings(T, handled=False))
    assert [v.id for v in rows] == ["vis_open"]


def test_ratings_handled_true_returns_only_handled_ones(store):
    run(store.save(_visit(id="vis_open", rating=3, rated_at=1_000)))
    run(store.save(_visit(id="vis_done", rating=3, rated_at=1_001,
                          rating_handled_at=2_000, rating_handled_note="تم")))
    rows, _ = run(store.ratings(T, handled=True))
    assert [v.id for v in rows] == ["vis_done"]


def test_ratings_filters_by_branch(store):
    run(store.save(_visit(id="vis_a", rating=4, rated_at=1_000, branch_id="brn_a")))
    run(store.save(_visit(id="vis_b", rating=4, rated_at=1_001, branch_id="brn_b")))
    rows, _ = run(store.ratings(T, branch_id="brn_a"))
    assert [v.id for v in rows] == ["vis_a"]


def test_ratings_sorts_newest_first(store):
    run(store.save(_visit(id="vis_old", rating=3, rated_at=1_000)))
    run(store.save(_visit(id="vis_new", rating=3, rated_at=2_000)))
    rows, _ = run(store.ratings(T))
    assert [v.id for v in rows] == ["vis_new", "vis_old"]


def test_ratings_is_tenant_scoped(store):
    run(store.save(_visit(id="vis_mine", tenant=T, rating=4, rated_at=1_000)))
    run(store.save(_visit(id="vis_theirs", tenant="tnt_other", rating=4, rated_at=1_000)))
    rows, _ = run(store.ratings(T))
    assert [v.id for v in rows] == ["vis_mine"]
