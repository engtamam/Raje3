"""`GET /api/v1/field/visits/offer/preview` — the field screen's pre-save preview, over real
HTTP, real auth. The business logic is unit-tested exhaustively in `test_preview_offer.py`; this
file proves only that the route is real and wired to `Operations.preview_offer`.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_field_offer_preview"
RECORD_CAPS = ("operations.record",)


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "10000", "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def client():
    return _make_app()


def _auth(tenant: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(RECORD_CAPS),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_nothing_wired_answers_a_null_offer_not_an_error(client):
    r = client.get("/api/v1/field/visits/offer/preview",
                   params={"phone": "0544440001", "subject_ref": "sub_1"},
                   headers=_auth(TENANT))
    assert r.status_code == 200, r.text
    assert r.json() == {"offer": None}


def test_a_live_campaign_offer_is_previewed_over_http(client):
    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "خصم ترحيبي", "campaign_id": "camp"}

    client.app.state.container.operations.with_offer_chooser(campaign_chooser)
    r = client.get("/api/v1/field/visits/offer/preview",
                   params={"phone": "0544440002", "subject_ref": "sub_2",
                          "service_ids": "svc_a,svc_b"},
                   headers=_auth(TENANT))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["offer"]["text"] == "خصم ترحيبي"
