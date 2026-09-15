"""core/growth.py — the growth-opportunities pipeline, one real step at a time. Each function is
tested in isolation (no peers, no network) so a change to one step can never be masked by another;
`test_build_report_end_to_end` at the bottom is the one test that runs the whole chain together."""
from __future__ import annotations

import asyncio

from app.core.growth import (
    PackageCandidate, apply_financial_guard, apply_points_strategy, build_report,
    find_structural_candidates, format_report, personal_rhythm, recent_service_ids,
    statistical_cross_sell,
)
from app.ports.rhythm_provider import RhythmEntry

NOW = 1_800_000_000
DAY = 86400


def run(c):
    return asyncio.run(c)


def _pkg(id_, *, price, components, service_ids, name=None, active=True, offerable=True):
    return {"id": id_, "name": name or id_, "price_minor": price,
           "component_price_minor_sum": components, "service_ids": service_ids,
           "active": active, "next_offerable_dates": ["2026-10-01"] if offerable else []}


# ── step 1 — structural ─────────────────────────────────────────────────────────────────────────
def test_a_package_selected_services_already_fully_cover_is_a_contains_selected_candidate():
    """"contains_selected" is reserved for a package with NOTHING missing — every one of its own
    components is already selected or recently done. A package with an extra piece beyond what
    was selected is "missing_one" instead (tested below) — a more useful, specific label, even
    when the "extra" is only a single service."""
    packages = [_pkg("pkg1", price=100, components=150, service_ids=["wash", "wax"])]
    out = find_structural_candidates(
        selected_ids=["wash", "wax"], recent_ids=set(), packages=packages)
    assert len(out) == 1
    assert out[0].kind == "contains_selected"


def test_a_package_missing_exactly_one_recent_service_is_a_missing_one_candidate():
    packages = [_pkg("pkg1", price=100, components=150, service_ids=["wash", "wax", "polish"])]
    out = find_structural_candidates(
        selected_ids=["wash"], recent_ids={"wax"}, packages=packages)
    assert len(out) == 1
    assert out[0].kind == "missing_one"
    assert out[0].missing_service_id == "polish"


def test_a_package_missing_two_pieces_is_not_a_candidate_at_all():
    packages = [_pkg("pkg1", price=100, components=150, service_ids=["wash", "wax", "polish"])]
    out = find_structural_candidates(selected_ids=["wash"], recent_ids=set(), packages=packages)
    assert out == []


def test_an_inactive_or_unbookable_package_is_never_a_candidate():
    packages = [
        _pkg("pkg_off", price=100, components=150, service_ids=["wash"], active=False),
        _pkg("pkg_no_dates", price=100, components=150, service_ids=["wash"], offerable=False),
    ]
    out = find_structural_candidates(selected_ids=["wash"], recent_ids=set(), packages=packages)
    assert out == []


def test_recent_service_ids_only_counts_within_the_window():
    rhythm = [
        RhythmEntry(service_id="wash", interval_days=30, last_visit_at=NOW - 10 * DAY,
                   observations=5, is_learned=True),
        RhythmEntry(service_id="wax", interval_days=30, last_visit_at=NOW - 200 * DAY,
                   observations=5, is_learned=True),
        # NOT learned yet — still counts, this only asks "did a real visit happen recently".
        RhythmEntry(service_id="polish", interval_days=0, last_visit_at=NOW - 5 * DAY,
                   observations=1, is_learned=False),
    ]
    ids = recent_service_ids(rhythm, now=NOW)
    assert ids == {"wash", "polish"}


# ── step 2 — financial guard ────────────────────────────────────────────────────────────────────
def test_a_package_that_costs_the_same_or_more_is_dropped():
    same = PackageCandidate(package_id="p1", name="p1", price_minor=150,
                            component_price_minor_sum=150, service_ids=["a"], kind="contains_selected")
    more = PackageCandidate(package_id="p2", name="p2", price_minor=200,
                            component_price_minor_sum=150, service_ids=["a"], kind="contains_selected")
    assert apply_financial_guard([same, more]) == []


def test_a_genuinely_cheaper_package_survives_with_its_real_savings():
    cheaper = PackageCandidate(package_id="p1", name="p1", price_minor=100,
                               component_price_minor_sum=150, service_ids=["a"], kind="contains_selected")
    out = apply_financial_guard([cheaper])
    assert len(out) == 1
    assert out[0].savings_minor == 50


# ── step 3 — points strategy ─────────────────────────────────────────────────────────────────────
class _FakePointsSummary:
    def __init__(self, *, points_for_services, points_by_package, balance, to_next_reward):
        self._preview = {"points_for_services": points_for_services,
                         "points_by_package": points_by_package}
        self._gap = {"points": balance, "to_next_reward": to_next_reward}

    async def earn_preview(self, *, tenant, service_ids, package_ids):
        return self._preview

    async def points_and_gap(self, *, tenant, subject_ref):
        return self._gap


def test_a_package_earning_more_points_narrows_the_gap_to_the_next_reward():
    candidate = PackageCandidate(package_id="p1", name="p1", price_minor=100,
                                 component_price_minor_sum=150, service_ids=["a"],
                                 kind="contains_selected", savings_minor=50)
    points = _FakePointsSummary(points_for_services=20, points_by_package={"p1": 60},
                               balance=100, to_next_reward=80)
    out = run(apply_points_strategy([candidate], points_summary=points,
                                    tenant="t1", subject_ref="s1"))
    assert out[0].extra_points == 40
    assert out[0].to_next_reward_before == 80
    assert out[0].to_next_reward_after == 40   # 80 - 40 extra points


def test_a_package_earning_fewer_points_never_reports_a_negative_gap_reduction():
    candidate = PackageCandidate(package_id="p1", name="p1", price_minor=100,
                                 component_price_minor_sum=150, service_ids=["a"],
                                 kind="contains_selected", savings_minor=50)
    points = _FakePointsSummary(points_for_services=60, points_by_package={"p1": 20},
                               balance=0, to_next_reward=80)
    out = run(apply_points_strategy([candidate], points_summary=points,
                                    tenant="t1", subject_ref="s1"))
    assert out[0].extra_points == -40
    assert out[0].to_next_reward_after == 80   # never widened past the real starting gap, never negative progress


def test_no_points_peer_wired_leaves_candidates_untouched_not_dropped():
    candidate = PackageCandidate(package_id="p1", name="p1", price_minor=100,
                                 component_price_minor_sum=150, service_ids=["a"],
                                 kind="contains_selected", savings_minor=50)
    out = run(apply_points_strategy([candidate], points_summary=None, tenant="t1", subject_ref="s1"))
    assert out == [candidate]


def test_a_peer_failure_leaves_candidates_untouched_not_dropped():
    class _Boom:
        async def earn_preview(self, **kw):
            raise ConnectionError("down")

        async def points_and_gap(self, **kw):
            raise ConnectionError("down")

    candidate = PackageCandidate(package_id="p1", name="p1", price_minor=100,
                                 component_price_minor_sum=150, service_ids=["a"],
                                 kind="contains_selected", savings_minor=50)
    out = run(apply_points_strategy([candidate], points_summary=_Boom(),
                                    tenant="t1", subject_ref="s1"))
    assert out == [candidate]


# ── step 4 — statistical cross-sell ─────────────────────────────────────────────────────────────
class _FakeRelated:
    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._mapping = mapping

    async def related_to(self, tenant, service_id):
        return self._mapping.get(service_id, [])


def test_cross_sell_names_a_real_related_service_never_a_package():
    related = _FakeRelated({"wash": ["wax", "pkg:should_be_ignored"]})
    lines = run(statistical_cross_sell(
        tenant="t1", service_ids=["wash"], related_services=related,
        names_by_id={"wash": "غسيل", "wax": "شمع"}))
    assert len(lines) == 1
    assert "شمع" in lines[0] and "غسيل" in lines[0]
    assert "pkg:" not in lines[0]


def test_cross_sell_with_no_peer_wired_returns_nothing():
    assert run(statistical_cross_sell(
        tenant="t1", service_ids=["wash"], related_services=None, names_by_id={})) == []


# ── step 5 — personal rhythm ─────────────────────────────────────────────────────────────────────
def test_personal_rhythm_splits_due_and_lapsed_by_the_same_bands_as_the_standalone_tools():
    rhythm = [
        # due soon: ratio ~1.0
        RhythmEntry(service_id="wash", interval_days=30, last_visit_at=NOW - 30 * DAY,
                   observations=5, is_learned=True),
        # lapsed: ratio well past 2.5
        RhythmEntry(service_id="wax", interval_days=10, last_visit_at=NOW - 100 * DAY,
                   observations=5, is_learned=True),
        # not learned — excluded regardless of ratio
        RhythmEntry(service_id="polish", interval_days=10, last_visit_at=NOW - 100 * DAY,
                   observations=1, is_learned=False),
    ]
    bands = personal_rhythm(rhythm, now=NOW, names_by_id={"wash": "غسيل", "wax": "شمع"})
    assert bands["due"] == ["غسيل"]
    assert bands["lapsed"] == ["شمع"]


# ── assembly ─────────────────────────────────────────────────────────────────────────────────────
def test_format_report_omits_empty_sections_entirely():
    report = format_report(candidates=[], cross_sell=[], rhythm={"due": [], "lapsed": []})
    assert report == ""


def test_format_report_states_real_numbers_plainly():
    candidate = PackageCandidate(package_id="p1", name="باقة الشمع", price_minor=100,
                                 component_price_minor_sum=150, service_ids=["a"],
                                 kind="contains_selected", savings_minor=50, extra_points=40,
                                 to_next_reward_before=80, to_next_reward_after=40)
    report = format_report(candidates=[candidate], cross_sell=[], rhythm={"due": [], "lapsed": []})
    assert "0.5 ر.س" in report or "0.5" in report   # 50 halalas -> 0.5 SAR, no invented rounding
    assert "40" in report and "مكافأته" in report


# ── end to end ──────────────────────────────────────────────────────────────────────────────────
class _FakePackageCatalog:
    def __init__(self, packages):
        self._packages = packages

    async def list_active(self, tenant):
        return self._packages


class _FakeServiceCatalog:
    def __init__(self, services):
        self._services = services

    async def list_active(self, tenant):
        return self._services


class _FakeRhythmProvider:
    def __init__(self, entries):
        self._entries = entries

    async def for_subject(self, *, tenant, subject_ref):
        return self._entries


def test_build_report_end_to_end_never_suggests_a_losing_package():
    packages = _FakePackageCatalog([
        _pkg("pkg_good", price=100, components=150, service_ids=["wash", "wax"],
            name="باقة الغسيل والشمع"),
        _pkg("pkg_bad", price=200, components=150, service_ids=["wash", "polish"],
            name="باقة خاسرة"),
    ])
    services = _FakeServiceCatalog([
        {"id": "wash", "name": "غسيل"}, {"id": "wax", "name": "شمع"},
    ])
    points = _FakePointsSummary(points_for_services=20, points_by_package={"pkg_good": 60},
                               balance=100, to_next_reward=80)
    report = run(build_report(
        tenant="t1", subject_ref="s1", selected_service_ids=["wash"],
        package_catalog=packages, service_catalog=services, rhythm_provider=None,
        related_services=None, points_summary=points, now=NOW))
    assert "باقة الغسيل والشمع" in report
    assert "باقة خاسرة" not in report and "200" not in report


def test_build_report_with_every_peer_absent_returns_the_honest_empty_string():
    report = run(build_report(
        tenant="t1", subject_ref="s1", selected_service_ids=["wash"],
        package_catalog=None, service_catalog=None, rhythm_provider=None,
        related_services=None, points_summary=None, now=NOW))
    assert report == ""
