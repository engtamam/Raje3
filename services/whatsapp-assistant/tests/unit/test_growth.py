"""core/growth.py — the growth-opportunities pipeline, one real step at a time. Each function is
tested in isolation (no peers, no network) so a change to one step can never be masked by another;
`test_build_report_end_to_end` at the bottom is the one test that runs the whole chain together."""
from __future__ import annotations

import asyncio

from app.core.growth import (
    RECENT_SERVICE_WINDOW_DAYS, PackageCandidate, apply_financial_guard, apply_points_strategy,
    build_report, find_structural_candidates, format_report, personal_rhythm, recent_service_ids,
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


# ── deeper scenarios — richer, more realistic combined data ─────────────────────────────────────
# Everything below exercises several moving parts TOGETHER (several candidates of both kinds
# surviving at once, a batched points call shared across them, cross-sell and rhythm firing in the
# same turn) rather than one function in isolation — closer to what a real, busy shop turn looks
# like than the single-fact tests above.

def test_financial_guard_boundary_exactly_equal_price_is_dropped_not_kept():
    """Savings must be STRICTLY positive — a package priced exactly at the sum of its components
    saves the customer nothing and must be dropped, not kept as a "break-even, still worth it"."""
    exact = PackageCandidate(package_id="p1", name="p1", price_minor=150,
                             component_price_minor_sum=150, service_ids=["a"], kind="contains_selected")
    one_halala_cheaper = PackageCandidate(package_id="p2", name="p2", price_minor=149,
                                          component_price_minor_sum=150, service_ids=["a"],
                                          kind="contains_selected")
    out = apply_financial_guard([exact, one_halala_cheaper])
    assert [c.package_id for c in out] == ["p2"]
    assert out[0].savings_minor == 1


def test_points_strategy_boundary_zero_extra_points_reports_no_progress_not_a_crash():
    """A package earning EXACTLY the same points as booking separately is a real, valid outcome —
    extra_points must land at exactly 0, and the gap must not move at all."""
    candidate = PackageCandidate(package_id="p1", name="p1", price_minor=100,
                                 component_price_minor_sum=150, service_ids=["a"],
                                 kind="contains_selected", savings_minor=50)
    points = _FakePointsSummary(points_for_services=40, points_by_package={"p1": 40},
                               balance=0, to_next_reward=80)
    out = run(apply_points_strategy([candidate], points_summary=points, tenant="t1", subject_ref="s1"))
    assert out[0].extra_points == 0
    assert out[0].to_next_reward_after == 80


def test_points_strategy_boundary_extra_points_exactly_close_the_gap_to_zero():
    """extra_points landing EXACTLY on the remaining gap must report a clean zero, never a
    fractional or negative "closed too much" artifact."""
    candidate = PackageCandidate(package_id="p1", name="p1", price_minor=100,
                                 component_price_minor_sum=150, service_ids=["a"],
                                 kind="contains_selected", savings_minor=50)
    points = _FakePointsSummary(points_for_services=0, points_by_package={"p1": 80},
                               balance=0, to_next_reward=80)
    out = run(apply_points_strategy([candidate], points_summary=points, tenant="t1", subject_ref="s1"))
    assert out[0].extra_points == 80
    assert out[0].to_next_reward_after == 0


def test_points_strategy_batch_is_shared_upper_bound_across_several_candidates():
    """apply_points_strategy's own docstring documents ONE shared "book separately" baseline across
    every surviving candidate in the batch (an honest upper bound when candidates don't fully
    overlap, never a per-candidate re-split loyalty was never asked for). With two candidates whose
    component services barely overlap, both must receive the SAME points_for_services baseline —
    proving the batching behaviour actually holds, not just for a single candidate."""
    wash_wax = PackageCandidate(package_id="p_wash_wax", name="غسيل وشمع", price_minor=100,
                                component_price_minor_sum=150, service_ids=["wash", "wax"],
                                kind="contains_selected", savings_minor=50)
    polish_tint = PackageCandidate(package_id="p_polish_tint", name="تلميع وتظليل", price_minor=200,
                                   component_price_minor_sum=260, service_ids=["polish", "tint"],
                                   kind="contains_selected", savings_minor=60)
    points = _FakePointsSummary(
        points_for_services=90,   # one shared baseline covering all four distinct services combined
        points_by_package={"p_wash_wax": 120, "p_polish_tint": 150},
        balance=0, to_next_reward=200)
    out = run(apply_points_strategy([wash_wax, polish_tint], points_summary=points,
                                    tenant="t1", subject_ref="s1"))
    assert out[0].points_for_services == 90
    assert out[1].points_for_services == 90   # same shared baseline, not re-derived per candidate
    assert out[0].extra_points == 30
    assert out[1].extra_points == 60


def test_build_report_end_to_end_with_several_candidates_cross_sell_and_rhythm_all_at_once():
    """A busy, realistic turn: TWO surviving packages of BOTH kinds (one contains_selected, one
    missing_one), a losing third package that must never appear, a real cross-sell hit, and a
    customer with BOTH a due-soon and a lapsed service — all landing in the SAME report, each in
    its own section, none stepping on another's numbers."""
    packages = _FakePackageCatalog([
        _pkg("pkg_contains", price=100, components=150, service_ids=["wash", "wax"],
            name="باقة الغسيل والشمع"),
        _pkg("pkg_missing_one", price=250, components=340, service_ids=["wash", "polish", "tint"],
            name="باقة العناية الكاملة"),
        _pkg("pkg_losing", price=999, components=150, service_ids=["wash", "wax"],
            name="باقة خاسرة"),
    ])
    services = _FakeServiceCatalog([
        {"id": "wash", "name": "غسيل"}, {"id": "wax", "name": "شمع"},
        {"id": "polish", "name": "تلميع"}, {"id": "tint", "name": "تظليل"},
        {"id": "interior", "name": "تنظيف داخلي"},
    ])
    # "polish" was done recently (covers pkg_missing_one's one gap); "interior" is due soon;
    # "tint" itself was done long ago and is now clearly lapsed.
    rhythm = _FakeRhythmProvider([
        RhythmEntry(service_id="polish", interval_days=30, last_visit_at=NOW - 10 * DAY,
                   observations=4, is_learned=True),
        RhythmEntry(service_id="interior", interval_days=20, last_visit_at=NOW - 20 * DAY,
                   observations=6, is_learned=True),
        RhythmEntry(service_id="tint", interval_days=15, last_visit_at=NOW - 200 * DAY,
                   observations=8, is_learned=True),
    ])
    related = _FakeRelated({"wash": ["interior"]})
    points = _FakePointsSummary(
        points_for_services=30,
        points_by_package={"pkg_contains": 70, "pkg_missing_one": 90, "pkg_losing": 999},
        balance=0, to_next_reward=100)

    report = run(build_report(
        tenant="t1", subject_ref="s1", selected_service_ids=["wash"],
        package_catalog=packages, service_catalog=services, rhythm_provider=rhythm,
        related_services=related, points_summary=points, now=NOW))

    # both real winners present, with their own distinct numbers
    assert "باقة الغسيل والشمع" in report
    assert "باقة العناية الكاملة" in report
    assert "(تحتاج فقط إضافة خدمة واحدة" in report   # only the missing_one candidate gets this note

    # the losing package must never appear, anywhere, under any name or price
    assert "باقة خاسرة" not in report and "999" not in report

    # cross-sell and both rhythm bands each show up in their own section
    assert "تنظيف داخلي" in report and "ارتباط إحصائي حقيقي" in report
    assert "خدمات مستحقة قريباً" in report and "تنظيف داخلي" in report
    assert "خدمات توقف عنها" in report and "تظليل" in report

    # sections appear in the documented, fixed order: packages, cross-sell, due, lapsed
    i_pkg = report.index("باقات تستحق الذكر")
    i_cross = report.index("ارتباطات إحصائية حقيقية")
    i_due = report.index("خدمات مستحقة قريباً")
    i_lapsed = report.index("خدمات توقف عنها")
    assert i_pkg < i_cross < i_due < i_lapsed


def test_build_report_with_a_large_catalogue_only_the_real_fits_survive():
    """A larger, more realistic catalogue (10 packages, most irrelevant to this turn) — makes sure
    the pipeline doesn't accidentally surface something structurally unrelated just because it's
    active, offerable and cheap; only packages whose OWN components genuinely fit survive."""
    unrelated = [
        _pkg(f"pkg_unrelated_{i}", price=50, components=80,
            service_ids=[f"svc_{i}_a", f"svc_{i}_b"], name=f"باقة غير ذات صلة {i}")
        for i in range(8)
    ]
    packages = _FakePackageCatalog(unrelated + [
        _pkg("pkg_real", price=100, components=150, service_ids=["wash", "wax"],
            name="باقة حقيقية"),
    ])
    services = _FakeServiceCatalog([{"id": "wash", "name": "غسيل"}, {"id": "wax", "name": "شمع"}])
    report = run(build_report(
        tenant="t1", subject_ref="s1", selected_service_ids=["wash", "wax"],
        package_catalog=packages, service_catalog=services, rhythm_provider=None,
        related_services=None, points_summary=None, now=NOW))
    assert "باقة حقيقية" in report
    for i in range(8):
        assert f"باقة غير ذات صلة {i}" not in report


def test_recent_service_ids_boundary_exactly_at_the_window_edge_still_counts():
    """A visit exactly `window_days` old is still "recent" — the check is >=, not a strict >, so a
    customer whose last visit lands precisely on the boundary day is not unfairly excluded."""
    rhythm = [RhythmEntry(service_id="wash", interval_days=30,
                          last_visit_at=NOW - RECENT_SERVICE_WINDOW_DAYS * DAY,
                          observations=3, is_learned=True)]
    ids = recent_service_ids(rhythm, now=NOW)
    assert ids == {"wash"}
