"""/api/v1/field/catalogue also returns packages now (Visit.tsx's own workspace redesign,
2026-09-14: the counter screen shows packages, not only single services). Same gate
(`operations.read`) as the service list beside it — a field operator sees both without carrying
`operations.manage_services`, which the manage-side package routes still require.

Covers three things at once: the catalogue actually lists an offerable package, the read-only
image mirror works without the manage capability, and a visit can now be tagged with a
`package_id`.
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


def _package(client, tenant="t2"):
    a = client.post("/api/v1/staff/services", json={"name": "غسيل خارجي"},
                    headers=_auth("operations.manage_services", tenant=tenant)).json()
    b = client.post("/api/v1/staff/services", json={"name": "تلميع"},
                    headers=_auth("operations.manage_services", tenant=tenant)).json()
    pkg = client.post("/api/v1/staff/packages",
                      json={"name": "باقة العناية", "service_ids": [a["id"], b["id"]],
                            "price_minor": 12000},
                      headers=_auth("operations.manage_services", tenant=tenant)).json()
    return a, b, pkg


def test_the_field_catalogue_lists_an_offerable_package(client):
    a, b, pkg = _package(client)
    out = client.get("/api/v1/field/catalogue", headers=_auth("operations.read", tenant="t2"))
    assert out.status_code == 200, out.text
    body = out.json()
    assert "packages" in body
    ids = {p["id"] for p in body["packages"]}
    assert pkg["id"] in ids


def test_the_field_catalogue_does_not_need_manage_services_to_see_packages(client):
    _package(client, tenant="t3")
    denied = client.get("/api/v1/field/catalogue",
                        headers=_auth("operations.manage_services", tenant="t3"))
    # NOT a refusal of the route itself — manage_services simply is not `operations.read`, and
    # the field door is not the manage door. This is just confirming the reverse holds too: a
    # plain read token, with no manage capability at all, still sees packages.
    read_only = client.get("/api/v1/field/catalogue", headers=_auth("operations.read", tenant="t3"))
    assert read_only.status_code == 200
    assert len(read_only.json()["packages"]) >= 1


def test_a_package_photo_is_readable_with_only_operations_read(client):
    a, b, pkg = _package(client, tenant="t4")
    # A 1x1 transparent PNG — real, valid bytes, matching test_catalogue_image.py's own fixture.
    png_1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    up = client.post(f"/api/v1/staff/packages/{pkg['id']}/image",
                     json={"content_type": "image/png", "data_base64": png_1x1},
                     headers=_auth("operations.manage_services", tenant="t4"))
    assert up.status_code == 200, up.text

    # THE MANAGE-ONLY ROUTE REFUSES A PLAIN READ TOKEN — confirming the two doors really are
    # separate, not that the new one happens to also work.
    manage_only = client.get(f"/api/v1/staff/packages/{pkg['id']}/image",
                             headers=_auth("operations.read", tenant="t4"))
    assert manage_only.status_code == 403

    got = client.get(f"/api/v1/field/catalogue/packages/{pkg['id']}/image",
                     headers=_auth("operations.read", tenant="t4"))
    assert got.status_code == 200, got.text
    assert got.headers["content-type"] == "image/png"


def test_a_visit_can_be_tagged_with_the_package_it_sold(client):
    a, b, pkg = _package(client, tenant="t5")
    out = client.post("/api/v1/field/visits",
                      json={"phone": "0501112222", "service_ids": [a["id"], b["id"]],
                            "package_id": pkg["id"]},
                      headers=_auth("operations.record", tenant="t5"))
    assert out.status_code == 201, out.text
    assert out.json()["visit"]["package_id"] == pkg["id"]


def test_a_forged_package_id_is_dropped_rather_than_trusted(client):
    a, b, _pkg = _package(client, tenant="t6")
    out = client.post("/api/v1/field/visits",
                      json={"phone": "0503334444", "service_ids": [a["id"], b["id"]],
                            "package_id": "pkg_does_not_exist"},
                      headers=_auth("operations.record", tenant="t6"))
    assert out.status_code == 201, out.text
    assert out.json()["visit"]["package_id"] == ""
