"""create_service / update_service / upload_service_image all schedule
`catalog_item_sync_trigger.sync` with the real, just-saved Service object — the operations-side
wiring for WhatsApp Direct Ordering's own catalog item sync (core/catalog_item_sync_trigger.py)."""
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


def _stub_trigger(client):
    calls = []

    async def _fake_sync(*, tenant, service):
        calls.append({"tenant": tenant, "service_id": service.id, "name": service.name,
                     "price_minor": service.price_minor, "active": service.active})
        return True

    client.app.state.container.catalog_item_sync_trigger.sync = _fake_sync
    return calls


def test_create_service_schedules_the_sync_trigger(client):
    calls = _stub_trigger(client)
    r = client.post("/api/v1/staff/services", json={"name": "غسيل خارجي", "price_minor": 3000},
                    headers=HEADERS)
    assert r.status_code == 201, r.text
    assert len(calls) == 1
    assert calls[0]["service_id"] == r.json()["id"]
    assert calls[0]["price_minor"] == 3000
    assert calls[0]["active"] is True


def test_update_service_schedules_the_sync_trigger_with_the_new_values(client):
    calls = _stub_trigger(client)
    r = client.post("/api/v1/staff/services", json={"name": "غسيل خارجي"}, headers=HEADERS)
    sid = r.json()["id"]
    calls.clear()

    r = client.patch(f"/api/v1/staff/services/{sid}", json={"price_minor": 7000, "active": False},
                     headers=HEADERS)
    assert r.status_code == 200, r.text
    assert len(calls) == 1
    assert calls[0]["price_minor"] == 7000
    assert calls[0]["active"] is False


def test_upload_service_image_schedules_the_sync_trigger(client):
    calls = _stub_trigger(client)
    r = client.post("/api/v1/staff/services", json={"name": "غسيل خارجي"}, headers=HEADERS)
    sid = r.json()["id"]
    calls.clear()

    r = client.post(f"/api/v1/staff/services/{sid}/image", json={
        "content_type": "image/png", "data_base64": base64.b64encode(_PNG_1PX).decode()},
        headers=HEADERS)
    assert r.status_code == 200, r.text
    assert len(calls) == 1
    assert calls[0]["service_id"] == sid


def test_a_failed_image_upload_never_schedules_the_trigger(client):
    """An unsupported mime type is refused BEFORE the service is ever saved with a new image_key
    -- the trigger must not fire for a change that never actually happened."""
    calls = _stub_trigger(client)
    r = client.post("/api/v1/staff/services", json={"name": "غسيل خارجي"}, headers=HEADERS)
    sid = r.json()["id"]
    calls.clear()

    r = client.post(f"/api/v1/staff/services/{sid}/image", json={
        "content_type": "application/pdf", "data_base64": base64.b64encode(b"not an image").decode()},
        headers=HEADERS)
    assert r.status_code == 422, r.text
    assert calls == []
