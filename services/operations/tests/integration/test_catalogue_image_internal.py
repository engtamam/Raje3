"""GET /internal/operations/catalogue/{kind}/{item_id}/image — the same photo an owner reads via
/api/v1/staff/{services,packages}/{id}/image, streamed to a peer holding the internal token
instead (whatsapp-assistant's catalog provider, which has no owner bearer token at all).
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
INTERNAL_TOKEN = "t" * 40

# A 1x1 transparent PNG — real, valid bytes, not a placeholder string.
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
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
INTERNAL_HEADERS = {"X-Internal-Token": INTERNAL_TOKEN}


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


def test_a_services_photo_is_readable_by_the_internal_route(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")

    got = client.get(f"/internal/operations/catalogue/service/{sid}/image?tenant=t1",
                     headers=INTERNAL_HEADERS)
    assert got.status_code == 200
    assert got.content == _PNG_1PX
    assert got.headers["content-type"] == "image/png"


def test_a_packages_photo_is_readable_by_the_internal_route(client):
    pid = _new_package(client)
    _upload(client, f"/api/v1/staff/packages/{pid}/image")

    got = client.get(f"/internal/operations/catalogue/package/{pid}/image?tenant=t1",
                     headers=INTERNAL_HEADERS)
    assert got.status_code == 200
    assert got.content == _PNG_1PX


def test_no_internal_token_is_refused(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    got = client.get(f"/internal/operations/catalogue/service/{sid}/image?tenant=t1")
    assert got.status_code in (401, 403)


def test_an_item_with_no_photo_reads_404_not_a_500(client):
    sid = _new_service(client)
    got = client.get(f"/internal/operations/catalogue/service/{sid}/image?tenant=t1",
                     headers=INTERNAL_HEADERS)
    assert got.status_code == 404


def test_an_unknown_id_reads_404(client):
    got = client.get("/internal/operations/catalogue/service/srv_nope/image?tenant=t1",
                     headers=INTERNAL_HEADERS)
    assert got.status_code == 404


def test_an_unknown_kind_reads_404_not_a_500(client):
    """A caller only ever builds this URL from CatalogCard.kind ('service'|'package') — a third
    value is as absent as a real id nobody has, never a 400/500."""
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    got = client.get(f"/internal/operations/catalogue/gadget/{sid}/image?tenant=t1",
                     headers=INTERNAL_HEADERS)
    assert got.status_code == 404


def test_wrong_tenant_reads_404_not_someone_elses_photo(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    got = client.get(f"/internal/operations/catalogue/service/{sid}/image?tenant=t2",
                     headers=INTERNAL_HEADERS)
    assert got.status_code == 404


def test_catalogue_with_prices_reports_has_image(client):
    sid = _new_service(client)
    _upload(client, f"/api/v1/staff/services/{sid}/image")
    other = _new_service(client, "بدون صورة")

    got = client.post("/internal/operations/catalogue-with-prices", json={"tenant": "t1"},
                      headers=INTERNAL_HEADERS)
    assert got.status_code == 200
    rows = {r["id"]: r for r in got.json()["services"]}
    assert rows[sid]["has_image"] is True
    assert rows[other]["has_image"] is False


def test_packages_route_reports_has_image(client):
    pid = _new_package(client)
    _upload(client, f"/api/v1/staff/packages/{pid}/image")

    got = client.post("/internal/operations/packages", json={"tenant": "t1"},
                      headers=INTERNAL_HEADERS)
    assert got.status_code == 200
    row = next(r for r in got.json()["packages"] if r["id"] == pid)
    assert row["has_image"] is True
