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


@pytest.fixture()
def client_mem():
    """Same app, `OBJECTSTORE_DRIVER=memory` — for the image-in-import tests, so a real photo's
    bytes are exercised without touching the filesystem (see test_catalogue_image.py's own note)."""
    saved = dict(os.environ)
    c = _make_app(OBJECTSTORE_DRIVER="memory")
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


# ── an image embedded in an import row, end to end — this is the real thing, not a stub ────────
import base64  # noqa: E402 — kept beside the tests that use it, matching this file's own style

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def _image_get(client, service_id):
    return client.get(f"/api/v1/staff/services/{service_id}/image", headers=HEADERS)


def test_a_new_row_with_an_embedded_image_ends_up_a_real_readable_photo_on_the_service(client_mem):
    r = client_mem.post("/api/v1/staff/services/bulk_import", json={"rows": [{
        "name": "غسيل خارجي", "image_base64": base64.b64encode(_PNG_1PX).decode(),
        "image_content_type": "image/png"}]}, headers=HEADERS)
    assert r.status_code == 200, r.text

    rows = client_mem.get("/api/v1/staff/services", headers=HEADERS).json()["services"]
    assert len(rows) == 1
    assert rows[0]["has_image"] is True

    got = _image_get(client_mem, rows[0]["id"])
    assert got.status_code == 200
    assert got.content == _PNG_1PX
    assert got.headers["content-type"] == "image/png"


def test_reimporting_the_same_row_without_an_image_keeps_the_existing_photo(client_mem):
    # UNLIKE description/price, a blank image column is NOT "clear it" — see ServiceImportRow's
    # own note: a partial photo-refresh file must not wipe every OTHER row's picture.
    client_mem.post("/api/v1/staff/services/bulk_import", json={"rows": [{
        "name": "غسيل خارجي", "image_base64": base64.b64encode(_PNG_1PX).decode(),
        "image_content_type": "image/png"}]}, headers=HEADERS)
    sid = client_mem.get("/api/v1/staff/services", headers=HEADERS).json()["services"][0]["id"]

    r = client_mem.post("/api/v1/staff/services/bulk_import",
                       json={"rows": [{"name": "غسيل خارجي", "price_minor": 7000}]},
                       headers=HEADERS)
    assert r.status_code == 200, r.text
    assert client_mem.get("/api/v1/staff/services", headers=HEADERS).json()["services"][0][
        "has_image"] is True
    assert _image_get(client_mem, sid).content == _PNG_1PX


def test_an_invalid_embedded_image_refuses_the_whole_import_and_writes_nothing(client_mem):
    r = client_mem.post("/api/v1/staff/services/bulk_import", json={"rows": [
        {"name": "خدمة سليمة"},
        {"name": "خدمة صورتها تالفة", "image_base64": "not-base64!!",
         "image_content_type": "image/png"},
    ]}, headers=HEADERS)
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_IMAGE"
    assert client_mem.get("/api/v1/staff/services", headers=HEADERS).json()["services"] == []


def test_an_unsupported_embedded_image_type_refuses_the_whole_import(client_mem):
    r = client_mem.post("/api/v1/staff/services/bulk_import", json={"rows": [{
        "name": "خدمة", "image_base64": base64.b64encode(b"not-a-real-file").decode(),
        "image_content_type": "application/pdf"}]}, headers=HEADERS)
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_IMAGE"


def test_replacing_a_photo_via_reimport_deletes_the_old_object(client_mem):
    client_mem.post("/api/v1/staff/services/bulk_import", json={"rows": [{
        "name": "غسيل خارجي", "image_base64": base64.b64encode(_PNG_1PX).decode(),
        "image_content_type": "image/png"}]}, headers=HEADERS)
    sid = client_mem.get("/api/v1/staff/services", headers=HEADERS).json()["services"][0]["id"]

    other_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAIAAAUAAen63NgAAAAASUVORK5CYII=")
    client_mem.post("/api/v1/staff/services/bulk_import", json={"rows": [{
        "name": "غسيل خارجي", "image_base64": base64.b64encode(other_png).decode(),
        "image_content_type": "image/png"}]}, headers=HEADERS)

    got = _image_get(client_mem, sid)
    assert got.content == other_png
    assert got.content != _PNG_1PX
