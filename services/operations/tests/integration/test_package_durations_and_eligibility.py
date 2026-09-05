"""`/internal/operations/package-durations` and `/package-eligibility` — bookings' two questions
about a package's basket, computed FRESH from the package's live components every call (never a
cached field on `Package` — see Package's own docstring for why).
"""
from __future__ import annotations

import asyncio

INTERNAL = {"X-Internal-Token": "t" * 40}
DURATIONS_PATH = "/internal/operations/package-durations"
ELIGIBILITY_PATH = "/internal/operations/package-eligibility"
TENANT = "tnt_pkg_durations"


def _seed(client, *, duration: int = 0, eligible: list[str] | None = None, sid: str) -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    svc = Service(id=sid, tenant=TENANT, name="خدمة", duration_minutes=duration, active=True,
                 eligible_staff_ids=eligible or [])
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(svc))
    return svc.id


def _seed_package(client, *, package_id: str, service_ids: list[str], active: bool = True) -> str:
    from app.core.models import Package
    from app.core.stores import PackageStore

    pkg = Package(id=package_id, tenant=TENANT, name="باقة", service_ids=service_ids,
                 price_minor=5000, active=active)
    asyncio.run(PackageStore(client.app.state.container.datastore).save(pkg))
    return pkg.id


# ── durations ──────────────────────────────────────────────────────────────────────────────────
def test_the_sum_of_the_packages_live_components(client):
    a = _seed(client, duration=20, sid="pd_a")
    b = _seed(client, duration=25, sid="pd_b")
    pkg = _seed_package(client, package_id="pd_pkg1", service_ids=[a, b])
    r = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["duration_minutes"] == 45


def test_any_unconfigured_component_makes_the_whole_answer_null(client):
    a = _seed(client, duration=20, sid="pd_c")
    b = _seed(client, duration=0, sid="pd_d")           # not configured
    pkg = _seed_package(client, package_id="pd_pkg2", service_ids=[a, b])
    r = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["duration_minutes"] is None


def test_an_unknown_package_is_null_not_an_error(client):
    r = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": "does_not_exist"},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["duration_minutes"] is None


def test_a_retired_package_is_null(client):
    a = _seed(client, duration=10, sid="pd_e")
    b = _seed(client, duration=10, sid="pd_f")
    pkg = _seed_package(client, package_id="pd_pkg3", service_ids=[a, b], active=False)
    r = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.json()["duration_minutes"] is None


def test_a_components_duration_change_after_creation_is_reflected_live(client):
    """THE WHOLE REASON THIS IS NEVER CACHED — see Package's own docstring."""
    from app.core.models import Service
    from app.core.stores import ServiceStore

    a = _seed(client, duration=10, sid="pd_g")
    b = _seed(client, duration=10, sid="pd_h")
    pkg = _seed_package(client, package_id="pd_pkg4", service_ids=[a, b])
    first = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": pkg},
                        headers=INTERNAL)
    assert first.json()["duration_minutes"] == 20

    store = ServiceStore(client.app.state.container.datastore)
    svc = asyncio.run(store.get(TENANT, a))
    svc.duration_minutes = 30
    asyncio.run(store.save(svc))

    second = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": pkg},
                         headers=INTERNAL)
    assert second.json()["duration_minutes"] == 40


def test_no_token_is_refused_on_durations(client):
    r = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": "x"})
    assert r.status_code == 401


# ── eligibility ────────────────────────────────────────────────────────────────────────────────
def test_unrestricted_components_leave_the_package_unrestricted(client):
    a = _seed(client, sid="pe_a")
    b = _seed(client, sid="pe_b")
    pkg = _seed_package(client, package_id="pe_pkg1", service_ids=[a, b])
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"] is None


def test_the_intersection_of_two_restricted_components(client):
    a = _seed(client, sid="pe_c", eligible=["op1", "op2", "op3"])
    b = _seed(client, sid="pe_d", eligible=["op2", "op3", "op4"])
    pkg = _seed_package(client, package_id="pe_pkg2", service_ids=[a, b])
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"] == ["op2", "op3"]


def test_one_unrestricted_component_does_not_narrow_the_other_restricted_one(client):
    a = _seed(client, sid="pe_e", eligible=[])                 # unrestricted
    b = _seed(client, sid="pe_f", eligible=["op9"])
    pkg = _seed_package(client, package_id="pe_pkg3", service_ids=[a, b])
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.json()["eligible_staff_ids"] == ["op9"]


def test_genuinely_disjoint_specialties_degrade_to_unrestricted_not_impossible(client):
    """THE "5 خدمات، 5 موظفات" EDGE CASE. A package spanning two specialties with NO staff member
    in common must still be bookable — the intersection is real and empty, and that degrades to
    "no restriction" (None) rather than "nobody qualifies" ([]), same reasoning as the route's own
    docstring: which staff actually does which part is a manual floor matter, not a hard gate."""
    a = _seed(client, sid="pe_g", eligible=["nail_tech"])
    b = _seed(client, sid="pe_h", eligible=["hair_stylist"])     # disjoint from the above
    pkg = _seed_package(client, package_id="pe_pkg4", service_ids=[a, b])
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["eligible_staff_ids"] is None


def test_an_unknown_package_is_null(client):
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": "does_not_exist"},
                    headers=INTERNAL)
    assert r.json()["eligible_staff_ids"] is None


def test_no_token_is_refused_on_eligibility(client):
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": "x"})
    assert r.status_code == 401


# ── deep robustness pass (100-test confidence sweep) ─────────────────────────────────────────────

def test_three_components_two_share_an_operator_the_third_is_disjoint(client):
    """Real-world shape: two hair services doable by the same two stylists, plus a totally
    unrelated specialty — the whole package must degrade to unrestricted (the disjoint one
    breaks any real intersection), never to "impossible"."""
    a = _seed(client, sid="pe_i", eligible=["op1", "op2"])
    b = _seed(client, sid="pe_j", eligible=["op1", "op2", "op3"])
    c = _seed(client, sid="pe_k", eligible=["nail_tech"])
    pkg = _seed_package(client, package_id="pe_pkg5", service_ids=[a, b, c])
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.json()["eligible_staff_ids"] is None


def test_three_components_all_sharing_one_operator_narrows_to_exactly_that_one(client):
    a = _seed(client, sid="pe_l", eligible=["op1", "op2"])
    b = _seed(client, sid="pe_m", eligible=["op1", "op3"])
    c = _seed(client, sid="pe_n", eligible=["op1", "op4"])
    pkg = _seed_package(client, package_id="pe_pkg6", service_ids=[a, b, c])
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.json()["eligible_staff_ids"] == ["op1"]


def test_a_retired_package_is_unrestricted_not_impossible_on_eligibility_too(client):
    a = _seed(client, sid="pe_o", eligible=["op1"])
    b = _seed(client, sid="pe_p", eligible=["op2"])
    pkg = _seed_package(client, package_id="pe_pkg7", service_ids=[a, b], active=False)
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.json()["eligible_staff_ids"] is None


def test_durations_and_eligibility_are_isolated_per_tenant(client):
    a = _seed(client, duration=20, sid="pe_iso_a")
    pkg = _seed_package(client, package_id="pe_iso_pkg", service_ids=[a, a])
    other_tenant_answer = client.post(
        DURATIONS_PATH, json={"tenant": "some_other_tenant", "package_id": pkg}, headers=INTERNAL)
    assert other_tenant_answer.json()["duration_minutes"] is None


def test_a_package_with_three_components_sums_all_three_durations(client):
    a = _seed(client, duration=10, sid="pd_x")
    b = _seed(client, duration=15, sid="pd_y")
    c = _seed(client, duration=20, sid="pd_z")
    pkg = _seed_package(client, package_id="pd_pkg5", service_ids=[a, b, c])
    r = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.json()["duration_minutes"] == 45


def test_the_middle_components_unconfigured_duration_still_nulls_the_whole_answer(client):
    a = _seed(client, duration=10, sid="pd_aa")
    b = _seed(client, duration=0, sid="pd_bb")     # unconfigured, in the MIDDLE of the list
    c = _seed(client, duration=20, sid="pd_cc")
    pkg = _seed_package(client, package_id="pd_pkg6", service_ids=[a, b, c])
    r = client.post(DURATIONS_PATH, json={"tenant": TENANT, "package_id": pkg}, headers=INTERNAL)
    assert r.json()["duration_minutes"] is None


# ── /internal/operations/package-offerable — deep pass ───────────────────────────────────────────
OFFERABLE_PATH = "/internal/operations/package-offerable"


def test_package_offerable_reflects_a_live_schedule_edit(client):
    """Not cached anywhere — editing the schedule must be reflected on the very next check."""
    from app.core.models import Package
    from app.core.stores import PackageStore

    pkg = Package(id="po_pkg1", tenant=TENANT, name="باقة", service_ids=["x", "y"],
                 price_minor=5000, active=True, recurrence="none")
    store = PackageStore(client.app.state.container.datastore)
    asyncio.run(store.save(pkg))

    first = client.post(OFFERABLE_PATH, json={"tenant": TENANT, "package_id": "po_pkg1", "at": 1780771200},
                        headers=INTERNAL)
    assert first.json()["offerable"] is True

    pkg.active = False
    asyncio.run(store.save(pkg))
    second = client.post(OFFERABLE_PATH, json={"tenant": TENANT, "package_id": "po_pkg1", "at": 1780771200},
                         headers=INTERNAL)
    assert second.json()["offerable"] is False


def test_package_offerable_is_isolated_per_tenant(client):
    from app.core.models import Package
    from app.core.stores import PackageStore

    pkg = Package(id="po_pkg2", tenant=TENANT, name="باقة", service_ids=["x", "y"],
                 price_minor=5000, active=True)
    asyncio.run(PackageStore(client.app.state.container.datastore).save(pkg))
    cross_tenant = client.post(
        OFFERABLE_PATH, json={"tenant": "some_other_tenant", "package_id": "po_pkg2", "at": 1780771200},
        headers=INTERNAL)
    assert cross_tenant.json()["offerable"] is False


def test_package_offerable_rejects_a_non_positive_at(client):
    r = client.post(OFFERABLE_PATH, json={"tenant": TENANT, "package_id": "x", "at": 0},
                    headers=INTERNAL)
    assert r.status_code == 422
