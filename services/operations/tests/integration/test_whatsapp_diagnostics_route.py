"""The admin panel's «ليش واتساب هذا المحل معطّل» read — proxying `notification-service`'s own
internal-token route behind a capability a person holds and an audit that names them, per
`api/v1/platform.py::evidence_file`'s own stated rule for every internal peer this service asks.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
ROUTE = "/api/v1/platform/whatsapp/diagnostics"


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

    app = create_app()
    with TestClient(app) as c:
        yield c
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant: str, caps=("platform.operations",)) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Desk:
    def __init__(self, by_tenant_result=None, by_phone_result=None):
        self._by_tenant = by_tenant_result
        self._by_phone = by_phone_result

    async def by_tenant(self, tenant):
        return self._by_tenant

    async def by_phone_number_id(self, phone_number_id):
        return self._by_phone


def test_refuses_without_either_filter(client):
    r = client.get(ROUTE, headers=_headers("_platform"))
    assert r.status_code == 400


def test_refuses_without_the_capability(client):
    r = client.get(ROUTE, params={"tenant": "tnt_x"}, headers=_headers("_platform", caps=("operations.manage",)))
    assert r.status_code == 403


def test_by_tenant_returns_the_peers_own_body(client):
    saved = client.app.state.container.whatsapp_diagnostics
    client.app.state.container.whatsapp_diagnostics = _Desk(
        by_tenant_result={"deliveries": [{"status": "failed", "reason": "template not approved"}]})
    try:
        r = client.get(ROUTE, params={"tenant": "tnt_x"}, headers=_headers("_platform"))
        assert r.status_code == 200
        assert r.json()["deliveries"][0]["reason"] == "template not approved"
    finally:
        client.app.state.container.whatsapp_diagnostics = saved


def test_by_phone_number_id_asks_the_desk_for_that_number(client):
    saved = client.app.state.container.whatsapp_diagnostics
    client.app.state.container.whatsapp_diagnostics = _Desk(by_phone_result={"deliveries": []})
    try:
        r = client.get(ROUTE, params={"phone_number_id": "1234567890"}, headers=_headers("_platform"))
        assert r.status_code == 200
        assert r.json() == {"deliveries": []}
    finally:
        client.app.state.container.whatsapp_diagnostics = saved


def test_an_unreachable_peer_answers_honestly_not_an_empty_list(client):
    saved = client.app.state.container.whatsapp_diagnostics
    client.app.state.container.whatsapp_diagnostics = _Desk(by_tenant_result=None)
    try:
        r = client.get(ROUTE, params={"tenant": "tnt_x"}, headers=_headers("_platform"))
        assert r.status_code == 502
        assert r.json()["error"] == "UNAVAILABLE"
    finally:
        client.app.state.container.whatsapp_diagnostics = saved
