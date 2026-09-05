"""package_offer — a campaign that promotes a PACKAGE, not a service (packages feature).

Creation refuses without a real, currently-offerable package (same "ask fresh, never assume" rule
dispatch.fire() applies again at every pass — see core/dispatch.py's own test coverage for that
half). This file proves the API-level half: the request body's package_id/package_name actually
reach the stored Campaign row.
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


class _FixedOfferable:
    def __init__(self, offerable: bool = True) -> None:
        self._offerable = offerable
        self.calls: list[tuple] = []

    async def offerable(self, tenant: str, package_id: str, at: int) -> bool:
        self.calls.append((tenant, package_id, at))
        return self._offerable


@pytest.fixture
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
    from app.adapters.peers import NullTemplates
    app.state.container.templates = NullTemplates([
        {"type": "mkt_offer", "name": "mkt_offer",
         "fills": ["system", "system", "amount", "catalogue", "date"],
         "variables": [1, 2, 3, 4, 5],
         "body": "{{1}} — {{2}}: خصم {{3}} على {{4}} حتى {{5}}"},
    ])
    yield app, TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(tenant="tnt_pkgoffer"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant,
                      "caps": ["campaigns.read", "campaigns.manage"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _body(**over):
    body = {"goal": "package_offer", "owner_text": "", "package_id": "pkg1",
           "package_name": "باقة الصيانة", "offer_value": "20%",
           "expires_at": int(dt.datetime.now(dt.timezone.utc).timestamp()) + 604_800}
    body.update(over)
    return body


def test_creating_a_package_offer_stores_its_package_id(client):
    app, http = client
    app.state.container.package_offerable = _FixedOfferable(offerable=True)
    r = http.post("/api/v1/campaigns", json=_body(), headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")

    listed = http.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["package_id"] == "pkg1"
    assert row["service_id"] == ""


def test_a_package_offer_with_no_package_id_is_refused(client):
    app, http = client
    app.state.container.package_offerable = _FixedOfferable(offerable=True)
    r = http.post("/api/v1/campaigns", json=_body(package_id=""), headers=_auth())
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_a_package_that_is_not_currently_offerable_refuses_creation(client):
    app, http = client
    app.state.container.package_offerable = _FixedOfferable(offerable=False)
    r = http.post("/api/v1/campaigns", json=_body(), headers=_auth())
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"
    assert "متاحة" in r.json()["reason"]


def test_the_offerable_check_is_asked_for_this_tenant_and_this_package(client):
    app, http = client
    check = _FixedOfferable(offerable=True)
    app.state.container.package_offerable = check
    http.post("/api/v1/campaigns", json=_body(), headers=_auth(tenant="tnt_specific"))
    assert check.calls
    assert check.calls[0][0] == "tnt_specific"
    assert check.calls[0][1] == "pkg1"


def test_the_message_names_the_package_not_a_service(client):
    app, http = client
    app.state.container.package_offerable = _FixedOfferable(offerable=True)
    r = http.post("/api/v1/campaigns/preview", json=_body(), headers=_auth())
    assert r.status_code == 200, r.text
    assert "باقة الصيانة" in r.json()["message"]
