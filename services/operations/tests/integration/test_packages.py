"""/api/v1/staff/packages — a named, priced group of the owner's OWN services (core/models.py's
Package). Same gate as the service catalogue (`operations.manage_services`), same
deactivate-never-delete convention, but its own validation: at least two live services, price > 0,
never derived from the components.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = "t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


def _two_services(client, tenant="t1"):
    a = client.post("/api/v1/staff/services", json={"name": "غيار زيت"},
                    headers=_auth("operations.manage_services", tenant=tenant)).json()
    b = client.post("/api/v1/staff/services", json={"name": "فحص فرامل"},
                    headers=_auth("operations.manage_services", tenant=tenant)).json()
    return a, b


def test_creating_a_package_needs_manage_services(client):
    a, b = _two_services(client)
    denied = client.post("/api/v1/staff/packages",
                         json={"name": "باقة", "service_ids": [a["id"], b["id"]],
                               "price_minor": 5000},
                         headers=_auth("operations.manage"))
    assert denied.status_code == 403

    allowed = client.post("/api/v1/staff/packages",
                          json={"name": "باقة", "service_ids": [a["id"], b["id"]],
                                "price_minor": 5000},
                          headers=_auth("operations.manage_services"))
    assert allowed.status_code == 201, allowed.text
    body = allowed.json()
    assert body["name"] == "باقة"
    assert set(body["service_ids"]) == {a["id"], b["id"]}
    assert body["price_minor"] == 5000
    assert body["active"] is True
    assert body["source"] == "manual"


def test_a_single_service_is_refused_a_package_needs_at_least_two(client):
    a, _ = _two_services(client)
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة فردية", "service_ids": [a["id"]], "price_minor": 5000},
                    headers=_auth("operations.manage_services"))
    # Pydantic's own min_length=2 refuses this before the handler ever runs.
    assert r.status_code == 422


def test_a_zero_price_is_refused_a_package_is_never_free_by_accident(client):
    a, b = _two_services(client)
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة", "service_ids": [a["id"], b["id"]], "price_minor": 0},
                    headers=_auth("operations.manage_services"))
    assert r.status_code == 422


def test_a_service_from_another_tenant_is_refused(client):
    a, b = _two_services(client, tenant="t1")
    foreign = client.post("/api/v1/staff/services", json={"name": "شيء آخر"},
                          headers=_auth("operations.manage_services", tenant="t2")).json()
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة", "service_ids": [a["id"], foreign["id"]],
                          "price_minor": 5000},
                    headers=_auth("operations.manage_services", tenant="t1"))
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_SERVICES"


def test_a_retired_service_is_refused(client):
    a, b = _two_services(client)
    client.patch(f"/api/v1/staff/services/{b['id']}", json={"active": False},
                headers=_auth("operations.manage_services"))
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة", "service_ids": [a["id"], b["id"]], "price_minor": 5000},
                    headers=_auth("operations.manage_services"))
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_SERVICES"


def test_a_service_may_belong_to_more_than_one_active_package(client):
    a, b = _two_services(client)
    c = client.post("/api/v1/staff/services", json={"name": "تلميع"},
                    headers=_auth("operations.manage_services")).json()
    first = client.post("/api/v1/staff/packages",
                        json={"name": "باقة رقم 1", "service_ids": [a["id"], b["id"]],
                              "price_minor": 5000},
                        headers=_auth("operations.manage_services"))
    second = client.post("/api/v1/staff/packages",
                         json={"name": "باقة رقم 2", "service_ids": [a["id"], c["id"]],
                               "price_minor": 7000},
                         headers=_auth("operations.manage_services"))
    assert first.status_code == 201
    assert second.status_code == 201


def test_listing_and_deactivating_a_package(client):
    a, b = _two_services(client)
    created = client.post("/api/v1/staff/packages",
                          json={"name": "باقة للإيقاف", "service_ids": [a["id"], b["id"]],
                                "price_minor": 4000},
                          headers=_auth("operations.manage_services")).json()

    listed = client.get("/api/v1/staff/packages",
                        headers=_auth("operations.manage_services")).json()
    assert any(p["id"] == created["id"] for p in listed["packages"])

    stopped = client.patch(f"/api/v1/staff/packages/{created['id']}", json={"active": False},
                           headers=_auth("operations.manage_services"))
    assert stopped.status_code == 200
    assert stopped.json()["active"] is False

    listed_again = client.get("/api/v1/staff/packages",
                             headers=_auth("operations.manage_services")).json()
    assert not any(p["id"] == created["id"] for p in listed_again["packages"])
    listed_with_retired = client.get("/api/v1/staff/packages?include_retired=true",
                                     headers=_auth("operations.manage_services")).json()
    assert any(p["id"] == created["id"] for p in listed_with_retired["packages"])


def test_editing_a_package_price(client):
    a, b = _two_services(client)
    created = client.post("/api/v1/staff/packages",
                          json={"name": "باقة", "service_ids": [a["id"], b["id"]],
                                "price_minor": 5000},
                          headers=_auth("operations.manage_services")).json()
    edited = client.patch(f"/api/v1/staff/packages/{created['id']}", json={"price_minor": 6500},
                          headers=_auth("operations.manage_services"))
    assert edited.status_code == 200
    assert edited.json()["price_minor"] == 6500


def test_a_suggested_package_carries_its_source_pair(client):
    a, b = _two_services(client)
    created = client.post("/api/v1/staff/packages",
                          json={"name": "باقة مقترحة", "service_ids": [a["id"], b["id"]],
                                "price_minor": 5000, "source": "suggested",
                                "source_service_ids": [a["id"], b["id"]]},
                          headers=_auth("operations.manage_services")).json()
    assert created["source"] == "suggested"
    assert set(created["source_service_ids"]) == {a["id"], b["id"]}


# ── /internal/operations/packages — insights' read of the catalogue's own packages ──────────────
def test_internal_packages_route_includes_retired_ones(client):
    a, b = _two_services(client)
    created = client.post("/api/v1/staff/packages",
                          json={"name": "باقة داخلية", "service_ids": [a["id"], b["id"]],
                                "price_minor": 5000},
                          headers=_auth("operations.manage_services")).json()
    client.patch(f"/api/v1/staff/packages/{created['id']}", json={"active": False},
                headers=_auth("operations.manage_services"))

    r = client.post("/internal/operations/packages",
                    json={"tenant": "t1"}, headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    rows = {p["id"]: p for p in r.json()["packages"]}
    assert created["id"] in rows
    assert rows[created["id"]]["active"] is False
    assert set(rows[created["id"]]["service_ids"]) == {a["id"], b["id"]}


def test_internal_packages_route_needs_a_token(client):
    r = client.post("/internal/operations/packages", json={"tenant": "t1"})
    assert r.status_code == 401


# ── scheduling (packages feature, phase 2) ────────────────────────────────────────────────────
def test_creating_a_package_with_a_weekly_schedule(client):
    a, b = _two_services(client)
    created = client.post("/api/v1/staff/packages",
                          json={"name": "باقة السبت", "service_ids": [a["id"], b["id"]],
                                "price_minor": 5000, "recurrence": "weekly",
                                "recurrence_weekdays": [5]},
                          headers=_auth("operations.manage_services"))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["recurrence"] == "weekly"
    assert body["recurrence_weekdays"] == [5]
    assert "offerable_now" in body


def test_a_weekly_package_with_no_weekdays_is_refused(client):
    a, b = _two_services(client)
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة", "service_ids": [a["id"], b["id"]],
                          "price_minor": 5000, "recurrence": "weekly"},
                    headers=_auth("operations.manage_services"))
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_SCHEDULE"


def test_an_end_date_before_the_start_date_is_refused(client):
    a, b = _two_services(client)
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة", "service_ids": [a["id"], b["id"]],
                          "price_minor": 5000, "starts_at": 2000000000, "ends_at": 1000000000},
                    headers=_auth("operations.manage_services"))
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_SCHEDULE"


def test_listing_reports_offerable_now_honestly(client):
    a, b = _two_services(client)
    # A package bound to a start date far in the future is not offerable today.
    client.post("/api/v1/staff/packages",
               json={"name": "باقة مستقبلية", "service_ids": [a["id"], b["id"]],
                     "price_minor": 5000, "starts_at": 9999999999},
               headers=_auth("operations.manage_services"))
    listed = client.get("/api/v1/staff/packages",
                        headers=_auth("operations.manage_services")).json()
    future = next(p for p in listed["packages"] if p["name"] == "باقة مستقبلية")
    assert future["offerable_now"] is False


def test_editing_only_the_recurrence_mode_is_checked_against_the_packages_own_existing_days(client):
    """A PATCH that sends only `recurrence` (no weekdays) must be validated against the days the
    package ALREADY has, not against an empty list — the "None = leave it" convention applied to
    a whole shape, not just one field of it."""
    a, b = _two_services(client)
    created = client.post("/api/v1/staff/packages",
                          json={"name": "باقة", "service_ids": [a["id"], b["id"]],
                                "price_minor": 5000, "recurrence": "weekly",
                                "recurrence_weekdays": [5]},
                          headers=_auth("operations.manage_services")).json()
    # Switching to "monthly" without ever sending days_of_month must be refused — there is
    # nothing for the new mode to recur on yet.
    r = client.patch(f"/api/v1/staff/packages/{created['id']}", json={"recurrence": "monthly"},
                     headers=_auth("operations.manage_services"))
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_SCHEDULE"

    # Sending both together succeeds.
    ok = client.patch(f"/api/v1/staff/packages/{created['id']}",
                      json={"recurrence": "monthly", "recurrence_days_of_month": [1]},
                      headers=_auth("operations.manage_services"))
    assert ok.status_code == 200, ok.text
    assert ok.json()["recurrence"] == "monthly"
    assert ok.json()["recurrence_days_of_month"] == [1]


def test_a_package_with_person_count_carries_it_through(client):
    a, b = _two_services(client)
    created = client.post("/api/v1/staff/packages",
                          json={"name": "باقة العائلة", "service_ids": [a["id"], b["id"]],
                                "price_minor": 20000, "person_count": 3},
                          headers=_auth("operations.manage_services")).json()
    assert created["person_count"] == 3
