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
