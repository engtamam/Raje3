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


def test_an_unknown_package_is_null(client):
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": "does_not_exist"},
                    headers=INTERNAL)
    assert r.json()["eligible_staff_ids"] is None


def test_no_token_is_refused_on_eligibility(client):
    r = client.post(ELIGIBILITY_PATH, json={"tenant": TENANT, "package_id": "x"})
    assert r.status_code == 401
