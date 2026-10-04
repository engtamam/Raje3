"""Distance + Google Maps link handling (core/geo.py)."""
from __future__ import annotations

from app.core import geo


# ── haversine_km ─────────────────────────────────────────────────────────────────────────────
def test_the_same_point_is_zero_distance():
    assert geo.haversine_km(24.7136, 46.6753, 24.7136, 46.6753) == 0.0


def test_riyadh_to_jeddah_is_roughly_the_known_distance():
    # Riyadh (24.7136, 46.6753) to Jeddah (21.4858, 39.1925) — real-world straight-line distance
    # is ~850km. A wide tolerance band, since this checks the formula is right, not a GPS fixture.
    d = geo.haversine_km(24.7136, 46.6753, 21.4858, 39.1925)
    assert 800 <= d <= 900


def test_distance_is_symmetric():
    d1 = geo.haversine_km(24.7136, 46.6753, 21.4858, 39.1925)
    d2 = geo.haversine_km(21.4858, 39.1925, 24.7136, 46.6753)
    assert abs(d1 - d2) < 1e-9


def test_antipodal_points_do_not_crash_or_misbehave():
    # The one case asin()-based formulas get numerically shaky on — atan2 stays well-behaved.
    d = geo.haversine_km(0, 0, 0, 180)
    assert abs(d - math_pi_times_radius()) < 1.0


def math_pi_times_radius() -> float:
    import math
    return math.pi * geo.EARTH_RADIUS_KM


# ── within_radius_km ─────────────────────────────────────────────────────────────────────────
def test_within_radius_true_for_a_nearby_point():
    assert geo.within_radius_km(24.7136, 46.6753, 24.72, 46.68, radius_km=10) is True


def test_within_radius_false_for_a_far_point():
    assert geo.within_radius_km(24.7136, 46.6753, 21.4858, 39.1925, radius_km=10) is False


# ── clamp_radius_km ─────────────────────────────────────────────────────────────────────────
def test_clamp_keeps_an_in_range_value():
    assert geo.clamp_radius_km(25) == 25


def test_clamp_allows_zero_pickup_only():
    assert geo.clamp_radius_km(0) == 0


def test_clamp_folds_a_negative_value_up_to_the_floor():
    assert geo.clamp_radius_km(-5) == geo.MIN_RADIUS_KM


def test_clamp_folds_an_excessive_value_down_to_the_ceiling():
    assert geo.clamp_radius_km(500) == geo.MAX_RADIUS_KM


def test_clamp_falls_back_to_the_default_on_garbage_input():
    assert geo.clamp_radius_km("not a number") == geo.DEFAULT_RADIUS_KM
    assert geo.clamp_radius_km(None) == geo.DEFAULT_RADIUS_KM


# ── parse_google_maps_link — every shape Google's own share sheet produces ─────────────────────
def test_parses_the_at_sign_pan_zoom_shape():
    url = "https://www.google.com/maps/@24.7136,46.6753,17z"
    assert geo.parse_google_maps_link(url) == (24.7136, 46.6753)


def test_parses_the_q_query_shape():
    url = "https://www.google.com/maps?q=24.7136,46.6753"
    assert geo.parse_google_maps_link(url) == (24.7136, 46.6753)


def test_parses_the_ll_query_shape():
    url = "https://maps.google.com/maps?ll=24.7136,46.6753"
    assert geo.parse_google_maps_link(url) == (24.7136, 46.6753)


def test_parses_the_place_data_blob_shape():
    # No `@lat,lng` present here on purpose — a real place link that DOES carry one resolves to
    # that viewport-center pair first (same precedence `googleMapsLink.ts` documents), so this
    # checks the `!3d!4d` pattern in isolation.
    url = "https://www.google.com/maps/place/Some+Place/data=!3d24.7136!4d46.6753"
    assert geo.parse_google_maps_link(url) == (24.7136, 46.6753)


def test_a_link_with_no_coordinates_returns_none():
    assert geo.parse_google_maps_link("https://www.google.com/maps/search/coffee") is None


def test_empty_or_garbage_input_returns_none():
    assert geo.parse_google_maps_link("") is None
    assert geo.parse_google_maps_link("not a url at all") is None


def test_out_of_range_coordinates_in_the_text_are_rejected():
    # Something that matches the SHAPE of @lat,lng but is not a real coordinate must not pass.
    assert geo.parse_google_maps_link("https://example.com/@999.0,46.6753,17z") is None


# ── short links ──────────────────────────────────────────────────────────────────────────────
def test_recognises_a_short_link_host():
    assert geo.is_short_google_maps_link("https://maps.app.goo.gl/abc123") is True
    assert geo.is_short_google_maps_link("https://goo.gl/maps/abc123") is True


def test_a_full_link_is_not_flagged_as_short():
    assert geo.is_short_google_maps_link("https://www.google.com/maps/@24.7,46.6,17z") is False


def test_resolve_short_link_refuses_a_non_google_host():
    # SSRF guard: only goo.gl/maps.app.goo.gl are ever followed, never an arbitrary caller-named
    # host — this must return "" rather than attempt the request at all.
    assert geo.resolve_short_link("https://evil.example.com/redirect-me") == ""


def test_resolve_short_link_refuses_a_plaintext_scheme():
    assert geo.resolve_short_link("http://maps.app.goo.gl/abc123") == ""


def test_resolve_google_maps_link_prefers_the_direct_parse_over_resolving():
    # A full link is never sent through the network path at all, even if (hypothetically) it were
    # also a recognised short-link host — the direct parse always wins first.
    url = "https://www.google.com/maps?q=24.7136,46.6753"
    assert geo.resolve_google_maps_link(url) == (24.7136, 46.6753)


def test_resolve_google_maps_link_returns_none_for_an_unresolvable_short_link(monkeypatch):
    monkeypatch.setattr(geo, "resolve_short_link", lambda url: "")
    assert geo.resolve_google_maps_link("https://maps.app.goo.gl/doesnotmatter") is None


# ── nearest_branch_for_point (WhatsApp Direct Ordering, Step 4) ─────────────────────────────────

from dataclasses import dataclass


@dataclass
class _B:
    id: str
    lat: float = 0.0
    lng: float = 0.0
    delivery_radius_km: int = 10
    active: bool = True


# Riyadh-ish coordinates, a few km apart.
_RIYADH = (24.7136, 46.6753)
_NEAR_RIYADH = (24.72, 46.68)  # ~1-2km from _RIYADH
_JEDDAH = (21.4858, 39.1925)   # ~850km from _RIYADH


def test_the_only_covering_branch_is_picked():
    branches = [_B("b1", *_RIYADH, delivery_radius_km=5)]
    picked = geo.nearest_branch_for_point(branches, lat=_NEAR_RIYADH[0], lng=_NEAR_RIYADH[1])
    assert picked is not None
    assert picked.id == "b1"


def test_nobody_covering_returns_none():
    branches = [_B("b1", *_JEDDAH, delivery_radius_km=5)]
    assert geo.nearest_branch_for_point(branches, lat=_RIYADH[0], lng=_RIYADH[1]) is None


def test_the_nearer_of_two_covering_branches_wins():
    far = _B("far", *_RIYADH, delivery_radius_km=100)
    near = _B("near", *_NEAR_RIYADH, delivery_radius_km=100)
    picked = geo.nearest_branch_for_point(
        [far, near], lat=_NEAR_RIYADH[0], lng=_NEAR_RIYADH[1])
    assert picked.id == "near"


def test_an_inactive_branch_is_never_picked_even_if_it_is_the_only_one_covering():
    branches = [_B("b1", *_RIYADH, delivery_radius_km=100, active=False)]
    assert geo.nearest_branch_for_point(branches, lat=_RIYADH[0], lng=_RIYADH[1]) is None


def test_an_unset_location_zero_zero_is_never_picked():
    # Branch.lat/lng's own sentinel for "never pinned" -- must not be read as a real point.
    branches = [_B("b1", lat=0.0, lng=0.0, delivery_radius_km=100)]
    assert geo.nearest_branch_for_point(branches, lat=0.1, lng=0.1) is None


def test_a_zero_radius_branch_pickup_only_is_never_picked():
    branches = [_B("b1", *_RIYADH, delivery_radius_km=0)]
    assert geo.nearest_branch_for_point(branches, lat=_RIYADH[0], lng=_RIYADH[1]) is None


def test_an_exact_tie_is_broken_by_id_deterministically():
    b1 = _B("z_branch", *_RIYADH, delivery_radius_km=100)
    b2 = _B("a_branch", *_RIYADH, delivery_radius_km=100)  # identical point -> identical distance
    picked = geo.nearest_branch_for_point([b1, b2], lat=_RIYADH[0], lng=_RIYADH[1])
    assert picked.id == "a_branch"  # lexicographically first, same call always agrees


def test_an_empty_branch_list_returns_none():
    assert geo.nearest_branch_for_point([], lat=_RIYADH[0], lng=_RIYADH[1]) is None
