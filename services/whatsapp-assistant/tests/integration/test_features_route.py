"""GET /api/v1/assistant/features — the app-store card's own read, reachable before a shop owns
واتساب الذكي at all (see app/api/v1/__init__.py's own route docstring — same posture as
pricing/current right beside it).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
KEK = "unit-test-kek-not-a-real-key"

PATH = "/api/v1/assistant/features"


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
        "SECRETS_KEK": KEK,
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "shop1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": "t1",
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client() -> TestClient:
    saved = dict(os.environ)
    app = _make_app()
    yield app
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def test_a_shop_with_no_purchase_still_reads_the_catalog(client):
    r = client.get(PATH, headers=_auth("whatsapp_assistant.pricing_read"))
    assert r.status_code == 200, r.text
    ids = {f["id"] for f in r.json()["features"]}
    assert "whatsapp.escalates_when_frustrated" in ids


def test_an_unauthenticated_request_is_refused(client):
    r = client.get(PATH)
    assert r.status_code in (401, 403), r.text
