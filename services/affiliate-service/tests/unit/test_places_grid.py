"""The Grid algorithm, ported from places_scraper_v2.py — pure math, so these are direct value
checks against what the script itself would compute.
"""
from __future__ import annotations

from app.core.places_grid import generate_grid, matches_indicators, split_offsets


def test_generate_grid_covers_the_box_with_at_least_one_point():
    points = generate_grid(24.7136, 46.6753, w_km=10, h_km=10, step_km=7.5)
    assert len(points) >= 1
    for lat, lng in points:
        assert 24.0 < lat < 25.5
        assert 46.0 < lng < 47.5


def test_generate_grid_more_points_for_a_larger_box():
    small = generate_grid(24.7136, 46.6753, w_km=10, h_km=10, step_km=7.5)
    large = generate_grid(24.7136, 46.6753, w_km=100, h_km=80, step_km=7.5)
    assert len(large) > len(small)


def test_generate_grid_is_deterministic():
    a = generate_grid(21.5433, 39.1728, w_km=80, h_km=30, step_km=7.5)
    b = generate_grid(21.5433, 39.1728, w_km=80, h_km=30, step_km=7.5)
    assert a == b


def test_split_offsets_returns_four_quadrants():
    offsets = split_offsets(5.0)
    assert len(offsets) == 4
    signs = {(o[0] > 0, o[1] > 0) for o in offsets}
    assert signs == {(True, True), (True, False), (False, True), (False, False)}


def test_matches_indicators_with_no_indicators_matches_everything():
    assert matches_indicators("Any Business Name", []) is True


def test_matches_indicators_is_case_insensitive_substring():
    assert matches_indicators("Ladies Beauty Salon", ["ladies"]) is True
    assert matches_indicators("صالون نسائي للسيدات", ["نسائي"]) is True


def test_matches_indicators_refuses_a_non_match():
    assert matches_indicators("Car Wash Center", ["ladies", "نسائي"]) is False
