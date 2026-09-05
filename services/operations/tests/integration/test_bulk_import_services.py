"""operations.bulk_import_services — create/update a whole catalogue from one uploaded file.

Same auth harness as test_manage_services_capability.py (its own header explains the fixtures);
this file only adds the bulk_import-specific behaviour: matching, duplicates, reactivation, and
the opt-in deactivate_missing.
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


@pytest.fixture()
def client():
    saved = dict(os.environ)
    c = _make_app()
    yield c
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


HEADERS = _auth("operations.manage_services")


def _import(client, rows, **extra):
    return client.post("/api/v1/staff/services/bulk_import",
                       json={"rows": rows, **extra}, headers=HEADERS)


def test_a_bad_row_refuses_the_whole_file_and_writes_nothing(client):
    # name empty on the second row — the whole request is refused before this handler even runs
    # (Pydantic's own field validation), so the FIRST row is never written either.
    r = _import(client, [{"name": "قص شعر"}, {"name": ""}])
    assert r.status_code == 422
    assert client.get("/api/v1/staff/services", headers=HEADERS).json()["services"] == []


def test_duplicate_names_in_one_file_are_refused(client):
    r = _import(client, [{"name": "قص شعر"}, {"name": " قص شعر "}])  # same after strip/lower
    assert r.status_code == 400
    assert r.json()["error"] == "DUPLICATE_NAMES"


def test_creates_new_rows(client):
    r = _import(client, [{"name": "قص شعر", "price_minor": 5000}, {"name": "غسيل", "price_minor": 2000}])
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 2, "updated": 0, "reactivated": 0, "deactivated": 0}
    names = {s["name"] for s in client.get("/api/v1/staff/services", headers=HEADERS).json()["services"]}
    assert names == {"قص شعر", "غسيل"}


def test_reuploading_the_same_file_updates_in_place_not_a_duplicate(client):
    _import(client, [{"name": "قص شعر", "price_minor": 5000}])
    r = _import(client, [{"name": "قص شعر", "price_minor": 6000}])
    assert r.json() == {"created": 0, "updated": 1, "reactivated": 0, "deactivated": 0}
    rows = client.get("/api/v1/staff/services", headers=HEADERS).json()["services"]
    assert len(rows) == 1
    assert rows[0]["price_minor"] == 6000


def test_external_id_survives_a_rename(client):
    _import(client, [{"name": "قص شعر", "external_id": "SKU-1", "price_minor": 5000}])
    # Renamed in the file, same external_id — matches the SAME row, not a new one.
    r = _import(client, [{"name": "قص شعر (رجالي)", "external_id": "SKU-1", "price_minor": 5000}])
    assert r.json()["created"] == 0
    assert r.json()["updated"] == 1
    rows = client.get("/api/v1/staff/services", headers=HEADERS).json()["services"]
    assert len(rows) == 1
    assert rows[0]["name"] == "قص شعر (رجالي)"


def test_a_stopped_service_reappearing_in_the_file_is_reactivated(client):
    created = client.post("/api/v1/staff/services", json={"name": "قص شعر"}, headers=HEADERS).json()
    client.patch(f"/api/v1/staff/services/{created['id']}", json={"active": False}, headers=HEADERS)

    r = _import(client, [{"name": "قص شعر"}])
    assert r.json() == {"created": 0, "updated": 0, "reactivated": 1, "deactivated": 0}
    rows = client.get("/api/v1/staff/services", headers=HEADERS).json()["services"]
    assert rows[0]["active"] is True


def test_deactivate_missing_defaults_off_so_a_partial_file_leaves_the_rest_alone(client):
    _import(client, [{"name": "قص شعر"}, {"name": "غسيل"}])
    r = _import(client, [{"name": "قص شعر"}])   # "غسيل" simply absent from this upload
    assert r.json()["deactivated"] == 0
    active = {s["name"] for s in client.get("/api/v1/staff/services", headers=HEADERS).json()["services"]}
    assert active == {"قص شعر", "غسيل"}   # both still active — nothing silently retired


def test_deactivate_missing_opted_in_retires_only_what_the_new_file_left_out(client):
    _import(client, [{"name": "قص شعر"}, {"name": "غسيل"}])
    r = _import(client, [{"name": "قص شعر"}], deactivate_missing=True)
    assert r.json()["deactivated"] == 1
    # include_retired=true — the plain list is active-only, and the point being proven here is
    # exactly that "غسيل" left it (retired), which the default view would not show either way.
    rows = {s["name"]: s["active"] for s in
           client.get("/api/v1/staff/services?include_retired=true", headers=HEADERS).json()["services"]}
    assert rows == {"قص شعر": True, "غسيل": False}


def test_needs_manage_services_capability(client):
    denied = client.post("/api/v1/staff/services/bulk_import", json={"rows": [{"name": "قص شعر"}]},
                         headers=_auth("operations.manage"))
    assert denied.status_code == 403


def test_a_description_column_is_saved_on_a_new_row(client):
    r = _import(client, [{"name": "قص شعر", "description": "قص وتصفيف بالمقص والمكينة"}])
    assert r.status_code == 200, r.text
    rows = client.get("/api/v1/staff/services", headers=HEADERS).json()["services"]
    assert rows[0]["description"] == "قص وتصفيف بالمقص والمكينة"


def test_a_blank_description_column_clears_an_existing_description_same_as_a_blank_price(client):
    # THE FILE WINS COMPLETELY, same convention price_minor/duration_minutes already hold — a
    # blank column is not "leave it alone", it is the file's own value: nothing.
    _import(client, [{"name": "قص شعر", "description": "وصف أول"}])
    _import(client, [{"name": "قص شعر"}])
    rows = client.get("/api/v1/staff/services", headers=HEADERS).json()["services"]
    assert rows[0]["description"] == ""
