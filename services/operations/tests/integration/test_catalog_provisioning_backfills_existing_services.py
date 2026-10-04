"""A successful WhatsApp connect, once catalog provisioning itself succeeds, backfills every
service this tenant already has — see app/api/v1/connect.py::_provision_catalog_and_backfill and
core/catalog_item_sync_trigger.py::backfill. The real case this closes: a shop that built its
whole priced-and-photographed catalogue BEFORE ever connecting WhatsApp must not sit with an
empty Meta catalog until someone happens to edit each service again."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD,
                      "caps": ["billing.self", "operations.manage_services"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _FakeExchange:
    async def exchange(self, *, tenant, code, waba_id, phone_number_id, branch_id="", root_tenant=""):
        return True, ""


def test_backfill_runs_over_every_existing_service_when_provisioning_succeeds(client, monkeypatch):
    tenant = "tnt_backfill_ok"
    headers = _headers(tenant)
    s1 = client.post("/api/v1/staff/services", json={"name": "خدمة 1"}, headers=headers).json()["id"]
    s2 = client.post("/api/v1/staff/services", json={"name": "خدمة 2"}, headers=headers).json()["id"]

    synced_ids: list[str] = []

    async def _fake_sync(*, tenant, service):
        synced_ids.append(service.id)
        return True

    async def _fake_trigger(*, tenant, business_id, waba_id, phone_number_id):
        return True

    import app.core.connect as connect_module

    monkeypatch.setattr(connect_module, "build_exchange", lambda settings: _FakeExchange())
    c = client.app.state.container
    c.catalog_provision_trigger.trigger = _fake_trigger
    c.catalog_item_sync_trigger.sync = _fake_sync

    r = client.post("/api/v1/whatsapp/connect", json={
        "event": "FINISH", "code": "a-code", "waba_id": "waba_backfill",
        "phone_number_id": "pn_backfill_123", "business_id": "biz_backfill",
    }, headers=headers)
    assert r.status_code == 200, r.text
    assert sorted(synced_ids) == sorted([s1, s2])


def test_backfill_never_runs_when_provisioning_itself_fails(client, monkeypatch):
    tenant = "tnt_backfill_fail"
    headers = _headers(tenant)
    client.post("/api/v1/staff/services", json={"name": "خدمة 1"}, headers=headers)

    sync_calls: list[str] = []

    async def _fake_sync(*, tenant, service):
        sync_calls.append(service.id)
        return True

    async def _fake_trigger_fails(*, tenant, business_id, waba_id, phone_number_id):
        return False

    import app.core.connect as connect_module

    monkeypatch.setattr(connect_module, "build_exchange", lambda settings: _FakeExchange())
    c = client.app.state.container
    c.catalog_provision_trigger.trigger = _fake_trigger_fails
    c.catalog_item_sync_trigger.sync = _fake_sync

    r = client.post("/api/v1/whatsapp/connect", json={
        "event": "FINISH", "code": "a-code", "waba_id": "waba_backfill_fail",
        "phone_number_id": "pn_backfill_fail_123", "business_id": "biz_backfill_fail",
    }, headers=headers)
    assert r.status_code == 200, r.text
    assert sync_calls == []


def test_backfill_only_reaches_the_connecting_tenants_own_services(client, monkeypatch):
    other_tenant = "tnt_backfill_other"
    client.post("/api/v1/staff/services", json={"name": "خدمة غريبة"},
               headers=_headers(other_tenant))

    tenant = "tnt_backfill_isolated"
    headers = _headers(tenant)
    s1 = client.post("/api/v1/staff/services", json={"name": "خدمتي"}, headers=headers).json()["id"]

    synced_ids: list[str] = []

    async def _fake_sync(*, tenant, service):
        synced_ids.append(service.id)
        return True

    async def _fake_trigger(*, tenant, business_id, waba_id, phone_number_id):
        return True

    import app.core.connect as connect_module

    monkeypatch.setattr(connect_module, "build_exchange", lambda settings: _FakeExchange())
    c = client.app.state.container
    c.catalog_provision_trigger.trigger = _fake_trigger
    c.catalog_item_sync_trigger.sync = _fake_sync

    r = client.post("/api/v1/whatsapp/connect", json={
        "event": "FINISH", "code": "a-code", "waba_id": "waba_isolated",
        "phone_number_id": "pn_isolated_123", "business_id": "biz_isolated",
    }, headers=headers)
    assert r.status_code == 200, r.text
    assert synced_ids == [s1]
