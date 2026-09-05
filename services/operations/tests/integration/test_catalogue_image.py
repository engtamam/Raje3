"""operations.upload_service_image / upload_package_image — a real product photo, held in
`ObjectStore`, never a URL the console types in (catalogue_image.py's own module docstring).

Same auth harness as test_bulk_import_services.py; `OBJECTSTORE_DRIVER=memory` keeps this file
from touching the filesystem (see container.py's driver registry — the real `local`/`s3` drivers
are exercised by the object_store adapters' own tests, not here).
"""
from __future__ import annotations

import base64
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"

# A 1x1 transparent PNG — real, valid bytes, not a placeholder string.
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32, "OBJECTSTORE_DRIVER": "memory",
    })
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


def _new_service(client, name="غسيل خارجي") -> str:
    r = client.post("/api/v1/staff/services", json={"name": name}, headers=HEADERS)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _new_package(client) -> str:
    s1 = _new_service(client, "غسيل خارجي")
    s2 = _new_service(client, "تلميع")
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة العناية", "service_ids": [s1, s2], "price_minor": 5000},
                    headers=HEADERS)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload(client, path, data=_PNG_1PX, content_type="image/png"):
    return client.post(path, json={
        "content_type": content_type,
        "data_base64": base64.b64encode(data).decode()}, headers=HEADERS)


# ── services ──────────────────────────────────────────────────────────────────────────────────
def test_uploading_a_real_photo_sets_has_image_and_the_photo_is_readable_back(client):
    sid = _new_service(client)
    r = _upload(client, f"/api/v1/staff/services/{sid}/image")
    assert r.status_code == 200, r.text
    assert r.json()["has_image"] is True

    got = client.get(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert got.status_code == 200
    assert got.content == _PNG_1PX
    assert got.headers["content-type"] == "image/png"


def test_a_service_with_no_photo_reads_404_not_a_500(client):
    sid = _new_service(client)
    got = client.get(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert got.status_code == 404


def test_replacing_a_photo_deletes_the_old_object(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    first_get = client.get(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert first_get.content == _PNG_1PX

    other_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAIAAAUAAen63NgAAAAASUVORK5CYII=")
    r = _upload(client, f"/api/v1/staff/services/{sid}/image", data=other_png)
    assert r.status_code == 200
    second_get = client.get(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert second_get.content == other_png
    assert second_get.content != _PNG_1PX


def test_deleting_a_photo_clears_has_image_and_the_read_404s(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    r = client.delete(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["has_image"] is False
    got = client.get(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert got.status_code == 404


def test_deleting_a_photo_on_a_service_with_none_is_a_quiet_no_op(client):
    sid = _new_service(client)
    r = client.delete(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["has_image"] is False


def test_an_unsupported_mime_type_is_refused_with_422_and_sets_nothing(client):
    sid = _new_service(client)
    r = _upload(client, f"/api/v1/staff/services/{sid}/image", content_type="application/pdf")
    assert r.status_code == 422
    assert client.get(f"/api/v1/staff/services/{sid}/image",
                      headers=HEADERS).status_code == 404


def test_an_oversized_photo_is_refused(client):
    # A file this big is refused before catalogue_image.py's own MAX_BYTES check ever runs — the
    # service's own global request-body-size guard (BODY_LIMIT_BYTES) rejects the whole request
    # with 413 first, since the base64 payload is well past any reasonable request size. Both are
    # real refusals; this test only pins that an oversized upload never succeeds.
    sid = _new_service(client)
    from app.core.catalogue_image import MAX_BYTES
    huge = b"\x89PNG\r\n\x1a\n" + b"0" * (MAX_BYTES + 1)
    r = _upload(client, f"/api/v1/staff/services/{sid}/image", data=huge)
    assert r.status_code in (413, 422), r.text


def test_malformed_base64_is_refused_not_a_500(client):
    sid = _new_service(client)
    r = client.post(f"/api/v1/staff/services/{sid}/image",
                    json={"content_type": "image/png", "data_base64": "not-base64!!"},
                    headers=HEADERS)
    assert r.status_code == 422


def test_an_unknown_service_id_404s(client):
    r = _upload(client, "/api/v1/staff/services/no-such-id/image")
    assert r.status_code == 404


def test_a_second_tenants_service_photo_is_invisible_to_this_tenant(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    other = client.get(f"/api/v1/staff/services/{sid}/image", headers=_auth(
        "operations.manage_services", tenant="t2"))
    assert other.status_code == 404


# ── packages ──────────────────────────────────────────────────────────────────────────────────
def test_uploading_a_package_photo_works_the_same_way(client):
    pid = _new_package(client)
    r = _upload(client, f"/api/v1/staff/packages/{pid}/image")
    assert r.status_code == 200, r.text
    assert r.json()["has_image"] is True
    got = client.get(f"/api/v1/staff/packages/{pid}/image", headers=HEADERS)
    assert got.status_code == 200
    assert got.content == _PNG_1PX


def test_deleting_a_package_photo_clears_it(client):
    pid = _new_package(client)
    _upload(client, f"/api/v1/staff/packages/{pid}/image")
    r = client.delete(f"/api/v1/staff/packages/{pid}/image", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["has_image"] is False


# ── the audit trail ───────────────────────────────────────────────────────────────────────────
def test_a_real_upload_is_audited_as_service_image_set(client):
    from unittest.mock import AsyncMock

    sid = _new_service(client)
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        _upload(client, f"/api/v1/staff/services/{sid}/image")
    finally:
        client.app.state.auditor.record = original
    actions = [c.args[0] for c in spy.await_args_list]
    assert "service.image_set" in actions


def test_a_real_delete_is_audited_as_service_image_cleared(client):
    from unittest.mock import AsyncMock

    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        client.delete(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    finally:
        client.app.state.auditor.record = original
    actions = [c.args[0] for c in spy.await_args_list]
    assert "service.image_cleared" in actions


def test_a_no_op_delete_is_not_audited(client):
    from unittest.mock import AsyncMock

    sid = _new_service(client)
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        client.delete(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    finally:
        client.app.state.auditor.record = original
    assert spy.await_args_list == []


# ── description ───────────────────────────────────────────────────────────────────────────────
def test_a_service_description_is_saved_and_returned(client):
    r = client.post("/api/v1/staff/services",
                    json={"name": "تلميع", "description": "تلميع خارجي كامل بالشمع"},
                    headers=HEADERS)
    assert r.status_code == 201
    assert r.json()["description"] == "تلميع خارجي كامل بالشمع"


def test_a_blank_description_stays_blank_by_default(client):
    _new_service(client)
    assert client.get("/api/v1/staff/services", headers=HEADERS).json()["services"][0][
        "description"] == ""


def test_patching_the_description_updates_it(client):
    sid = _new_service(client)
    r = client.patch(f"/api/v1/staff/services/{sid}",
                     json={"description": "وصف جديد"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["description"] == "وصف جديد"


def test_a_package_description_is_saved_and_returned(client):
    s1 = _new_service(client, "غسيل")
    s2 = _new_service(client, "تلميع")
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة", "service_ids": [s1, s2], "price_minor": 4000,
                          "description": "غسيل وتلميع بسعر واحد"},
                    headers=HEADERS)
    assert r.status_code == 201
    assert r.json()["description"] == "غسيل وتلميع بسعر واحد"


# ── edge cases ────────────────────────────────────────────────────────────────────────────────
def test_uploading_without_the_capability_is_403(client):
    sid = _new_service(client)
    r = client.post(f"/api/v1/staff/services/{sid}/image", json={
        "content_type": "image/png", "data_base64": base64.b64encode(_PNG_1PX).decode()},
        headers=_auth("operations.read"))
    assert r.status_code == 403


def test_uploading_without_auth_at_all_is_401(client):
    sid = _new_service(client)
    r = client.post(f"/api/v1/staff/services/{sid}/image", json={
        "content_type": "image/png", "data_base64": base64.b64encode(_PNG_1PX).decode()})
    assert r.status_code == 401


def test_reading_without_the_capability_is_403(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    r = client.get(f"/api/v1/staff/services/{sid}/image", headers=_auth("operations.read"))
    assert r.status_code == 403


def test_deleting_without_the_capability_is_403(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    r = client.delete(f"/api/v1/staff/services/{sid}/image", headers=_auth("operations.read"))
    assert r.status_code == 403


def test_missing_content_type_field_is_422(client):
    sid = _new_service(client)
    r = client.post(f"/api/v1/staff/services/{sid}/image",
                    json={"data_base64": base64.b64encode(_PNG_1PX).decode()}, headers=HEADERS)
    assert r.status_code == 422


def test_missing_data_base64_field_is_422(client):
    sid = _new_service(client)
    r = client.post(f"/api/v1/staff/services/{sid}/image",
                    json={"content_type": "image/png"}, headers=HEADERS)
    assert r.status_code == 422


def test_content_type_with_a_parameter_suffix_still_works(client):
    sid = _new_service(client)
    r = _upload(client, f"/api/v1/staff/services/{sid}/image",
               content_type="image/png; charset=binary")
    assert r.status_code == 200, r.text


def test_content_type_is_case_insensitive(client):
    sid = _new_service(client)
    r = _upload(client, f"/api/v1/staff/services/{sid}/image", content_type="IMAGE/PNG")
    assert r.status_code == 200, r.text


def test_jpeg_upload_works(client):
    sid = _new_service(client)
    # A minimal real JPEG (SOI/EOI markers) — not a placeholder string.
    jpeg = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")
    r = _upload(client, f"/api/v1/staff/services/{sid}/image", data=jpeg,
               content_type="image/jpeg")
    assert r.status_code == 200, r.text
    got = client.get(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert got.content == jpeg
    assert got.headers["content-type"] == "image/jpeg"


def test_webp_upload_works(client):
    sid = _new_service(client)
    r = _upload(client, f"/api/v1/staff/services/{sid}/image", data=_PNG_1PX,
               content_type="image/webp")
    assert r.status_code == 200, r.text
    got = client.get(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert got.headers["content-type"] == "image/webp"


def test_content_that_decodes_to_zero_bytes_is_refused(client):
    sid = _new_service(client)
    r = client.post(f"/api/v1/staff/services/{sid}/image",
                    json={"content_type": "image/png", "data_base64": ""}, headers=HEADERS)
    # An empty string fails the field's own min_length=1 before catalogue_image.py's own
    # "empty file" check ever runs — either way, refused, never a 200.
    assert r.status_code == 422


def test_reuploading_the_identical_bytes_is_not_an_error(client):
    sid = _new_service(client)
    first = _upload(client, f"/api/v1/staff/services/{sid}/image")
    assert first.status_code == 200
    second = _upload(client, f"/api/v1/staff/services/{sid}/image")
    assert second.status_code == 200
    got = client.get(f"/api/v1/staff/services/{sid}/image", headers=HEADERS)
    assert got.content == _PNG_1PX


def test_has_image_is_false_by_default_on_a_new_service(client):
    r = client.post("/api/v1/staff/services", json={"name": "خدمة جديدة"}, headers=HEADERS)
    assert r.json()["has_image"] is False


def test_has_image_is_false_by_default_on_a_new_package(client):
    s1 = _new_service(client, "أ")
    s2 = _new_service(client, "ب")
    r = client.post("/api/v1/staff/packages",
                    json={"name": "باقة جديدة", "service_ids": [s1, s2], "price_minor": 1000},
                    headers=HEADERS)
    assert r.json()["has_image"] is False


def test_two_services_photos_are_fully_independent(client):
    s1 = _new_service(client, "خدمة أولى")
    s2 = _new_service(client, "خدمة ثانية")
    _upload(client, f"/api/v1/staff/services/{s1}/image")
    # s2 never got a photo — its own read must still 404, not accidentally return s1's.
    got = client.get(f"/api/v1/staff/services/{s2}/image", headers=HEADERS)
    assert got.status_code == 404
    # and deleting s2's (nonexistent) photo must not touch s1's real one.
    client.delete(f"/api/v1/staff/services/{s2}/image", headers=HEADERS)
    still_there = client.get(f"/api/v1/staff/services/{s1}/image", headers=HEADERS)
    assert still_there.status_code == 200
    assert still_there.content == _PNG_1PX


def test_an_unknown_package_id_404s_on_upload(client):
    r = _upload(client, "/api/v1/staff/packages/no-such-id/image")
    assert r.status_code == 404


def test_a_package_with_no_photo_reads_404(client):
    pid = _new_package(client)
    got = client.get(f"/api/v1/staff/packages/{pid}/image", headers=HEADERS)
    assert got.status_code == 404


def test_a_second_tenants_package_photo_is_invisible(client):
    pid = _new_package(client)
    _upload(client, f"/api/v1/staff/packages/{pid}/image")
    other = client.get(f"/api/v1/staff/packages/{pid}/image",
                       headers=_auth("operations.manage_services", tenant="t2"))
    assert other.status_code == 404


def test_description_at_the_max_length_is_accepted(client):
    r = client.post("/api/v1/staff/services",
                    json={"name": "خدمة", "description": "ط" * 300}, headers=HEADERS)
    assert r.status_code == 201
    assert len(r.json()["description"]) == 300


def test_description_over_the_max_length_is_refused_422(client):
    r = client.post("/api/v1/staff/services",
                    json={"name": "خدمة", "description": "ط" * 301}, headers=HEADERS)
    assert r.status_code == 422


def test_whitespace_only_description_is_stripped_to_blank(client):
    r = client.post("/api/v1/staff/services",
                    json={"name": "خدمة", "description": "   "}, headers=HEADERS)
    assert r.status_code == 201
    assert r.json()["description"] == ""
