"""GET /api/v1/public_catalog/{token} — the one route on this service reachable with no
login at all. See core/public_catalog_image.py's own module docstring for the full threat model.
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


def _upload(client, sid) -> None:
    r = client.post(f"/api/v1/staff/services/{sid}/image", json={
        "content_type": "image/png", "data_base64": base64.b64encode(_PNG_1PX).decode()},
        headers=HEADERS)
    assert r.status_code == 200, r.text


def _public_token(client, sid) -> str:
    """The upload route never returns the raw token (console has no reason to see it) — read it
    straight off the stored row the same way the sync desk eventually will."""
    import asyncio

    from app.core.stores import ServiceStore
    store = ServiceStore(client.app.state.container.datastore)
    s = asyncio.run(store.get("t1", sid))
    return s.public_image_token


# ── the happy path, and that it needs NO auth header at all ───────────────────────────────────
def test_a_valid_token_serves_the_photo_with_no_auth_header(client):
    sid = _new_service(client)
    _upload(client, sid)
    token = _public_token(client, sid)
    r = client.get(f"/api/v1/public_catalog/{token}")
    assert r.status_code == 200
    assert r.content == _PNG_1PX
    assert r.headers["content-type"] == "image/png"


def test_the_response_is_cached_hard_and_immutable(client):
    sid = _new_service(client)
    _upload(client, sid)
    token = _public_token(client, sid)
    r = client.get(f"/api/v1/public_catalog/{token}")
    assert "immutable" in r.headers["cache-control"]
    assert "max-age=31536000" in r.headers["cache-control"]


# ── every failure shape reads identically — no oracle ──────────────────────────────────────────
def test_an_unknown_token_is_a_plain_404(client):
    r = client.get("/api/v1/public_catalog/totally-made-up")
    assert r.status_code == 404


def test_an_empty_path_segment_is_not_a_crash(client):
    r = client.get("/api/v1/public_catalog/")
    assert r.status_code in (404, 307, 308)  # routing 404/redirect, never a 500


def test_a_revoked_token_from_a_reupload_goes_dead_immediately(client):
    sid = _new_service(client)
    _upload(client, sid)
    old_token = _public_token(client, sid)
    _upload(client, sid)  # re-upload — mints a NEW token, must revoke the old one
    new_token = _public_token(client, sid)
    assert new_token != old_token

    dead = client.get(f"/api/v1/public_catalog/{old_token}")
    assert dead.status_code == 404
    alive = client.get(f"/api/v1/public_catalog/{new_token}")
    assert alive.status_code == 200


def test_the_old_tokens_404_and_the_new_tokens_200_carry_identical_error_shape(client):
    """No distinguishing a dead-but-once-real token from one that never existed — both must be the
    exact same generic 404 body, never a different message that would let a prober learn which."""
    sid = _new_service(client)
    _upload(client, sid)
    old_token = _public_token(client, sid)
    _upload(client, sid)
    never_issued = client.get("/api/v1/public_catalog/never-issued-at-all")
    revoked = client.get(f"/api/v1/public_catalog/{old_token}")
    assert never_issued.status_code == revoked.status_code == 404
    # Same error CODE, never a different message — `request_id` legitimately differs per response
    # (normal trace-id behaviour, not an information leak).
    assert never_issued.json()["error"] == revoked.json()["error"]


def test_two_tenants_services_each_get_their_own_independent_working_token(client):
    s1 = _new_service(client, "خدمة 1")
    _upload(client, s1)
    tok1 = _public_token(client, s1)

    other_headers = _auth("operations.manage_services", tenant="t2")
    r2 = client.post("/api/v1/staff/services", json={"name": "خدمة 2"}, headers=other_headers)
    s2 = r2.json()["id"]
    client.post(f"/api/v1/staff/services/{s2}/image", json={
        "content_type": "image/png", "data_base64": base64.b64encode(_PNG_1PX).decode()},
        headers=other_headers)
    import asyncio

    from app.core.stores import ServiceStore
    store = ServiceStore(client.app.state.container.datastore)
    tok2 = asyncio.run(store.get("t2", s2)).public_image_token

    assert tok1 != tok2
    assert client.get(f"/api/v1/public_catalog/{tok1}").status_code == 200
    assert client.get(f"/api/v1/public_catalog/{tok2}").status_code == 200


def test_a_brand_new_service_with_no_photo_has_no_working_token(client):
    sid = _new_service(client)
    import asyncio

    from app.core.stores import ServiceStore
    store = ServiceStore(client.app.state.container.datastore)
    s = asyncio.run(store.get("t1", sid))
    assert s.public_image_token == ""


def test_the_route_needs_no_rate_limit_bypass_header_or_anything_special(client):
    """Sanity: a bare, header-less GET is the ONLY thing a real caller (Meta's crawler) can send —
    prove the route tolerates exactly that, nothing more."""
    sid = _new_service(client)
    _upload(client, sid)
    token = _public_token(client, sid)
    r = client.get(f"/api/v1/public_catalog/{token}", headers={})
    assert r.status_code == 200
