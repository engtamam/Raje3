"""`?locale=` on /staff/services and /staff/procedure-steps — see core/translations.py's own
module docstring for the hash-based detection this overlay reads from. Phase 2: the storage and
the Arabic fallback exist and are correct; nothing produces a real translation yet (phase 3), so
every locale here answers with the Arabic source — the point of this file is that it does so
CORRECTLY (no crash, no blank field), not that a translation appears.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000", "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(tenant: str = "t_locale") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": ["operations.manage_services"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_service_falls_back_to_arabic_in_an_unanswered_locale(client):
    headers = _auth()
    r = client.post("/api/v1/staff/services",
                    json={"name": "غسيل خارجي", "description": "غسيل شامل للسيارة"},
                    headers=headers)
    assert r.status_code == 201, r.text

    r = client.get("/api/v1/staff/services?locale=en", headers=headers)
    assert r.status_code == 200, r.text
    row = next(s for s in r.json()["services"] if s["name"] == "غسيل خارجي")
    assert row["description"] == "غسيل شامل للسيارة"


def test_a_junk_locale_is_treated_as_arabic_not_an_error(client):
    headers = _auth(tenant="t_locale_junk")
    r = client.post("/api/v1/staff/services", json={"name": "تلميع"}, headers=headers)
    assert r.status_code == 201, r.text

    r = client.get("/api/v1/staff/services?locale=xx", headers=headers)
    assert r.status_code == 200, r.text
    row = next(s for s in r.json()["services"] if s["name"] == "تلميع")
    assert row["name"] == "تلميع"


def test_procedure_step_text_falls_back_to_arabic(client):
    headers = _auth(tenant="t_locale_step")
    r = client.post("/api/v1/staff/procedure-steps", json={"text": "اغسل بالماء"}, headers=headers)
    assert r.status_code == 201, r.text

    r = client.get("/api/v1/staff/procedure-steps?locale=ur", headers=headers)
    assert r.status_code == 200, r.text
    row = next(s for s in r.json()["procedure_steps"] if s["text"] == "اغسل بالماء")
    assert row["text"] == "اغسل بالماء"
