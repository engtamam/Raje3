"""The routes over §6's BYOK Google Places key — managers-only gate, write-only guarantee (never
returns the plaintext), and the 503 when SECRETS_KEK is unconfigured.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"


def _make_app(*, kek: str = "k" * 32) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 16,
        "IDENTITY_SERVICE_URL": "http://identity:8000",
        "AFFILIATE_TENANT": "raje3-affiliates",
        "SECRETS_KEK": kek,
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def leads_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(leads_env) -> TestClient:
    return _make_app()


def _token(**over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    # Every real affiliate token carries `affiliates.self` — see
    # app/core/models.py's own note. `**over` still lets a caller pass `caps=[...]` to test a
    # missing-capability 403 specifically.
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD, "caps": ["affiliates.self"],
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _seed_manager(client: TestClient, affiliate_id: str, person_id: str) -> None:
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=affiliate_id, person_id=person_id, phone="+966504440001",
                        name="مدير", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())


def _seed_promoter(client: TestClient, affiliate_id: str, person_id: str) -> None:
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=affiliate_id, person_id=person_id, phone="+966504440002",
                        name="مسوّق", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())


def test_set_places_api_key_refuses_with_no_token(client):
    r = client.put("/api/v1/affiliates/me/places-api-key", json={"api_key": "x"})
    assert r.status_code == 401


def test_a_promoter_cannot_set_a_places_api_key(client):
    _seed_promoter(client, "aff-l1", "p-l1")
    r = client.put("/api/v1/affiliates/me/places-api-key", json={"api_key": "AIzaX"},
                   headers={"Authorization": f"Bearer {_token(sub='p-l1')}"})
    assert r.status_code == 403


def test_a_manager_sets_and_reads_only_a_hint_never_the_value(client):
    _seed_manager(client, "aff-l2", "p-l2")
    headers = {"Authorization": f"Bearer {_token(sub='p-l2')}"}

    r = client.put("/api/v1/affiliates/me/places-api-key",
                   json={"api_key": "AIzaSuperSecretManagerKey"}, headers=headers)
    assert r.status_code == 200, r.text
    assert "AIzaSuperSecretManagerKey" not in r.text
    assert r.json()["hint"].endswith("rKey")

    got = client.get("/api/v1/affiliates/me/places-api-key", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["set"] is True
    assert "AIzaSuperSecretManagerKey" not in got.text


def test_a_manager_with_no_key_set_reports_unset(client):
    _seed_manager(client, "aff-l3", "p-l3")
    headers = {"Authorization": f"Bearer {_token(sub='p-l3')}"}
    r = client.get("/api/v1/affiliates/me/places-api-key", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"set": False}


def test_clearing_the_key_then_reading_reports_unset_again(client):
    _seed_manager(client, "aff-l4", "p-l4")
    headers = {"Authorization": f"Bearer {_token(sub='p-l4')}"}
    client.put("/api/v1/affiliates/me/places-api-key", json={"api_key": "AIzaTemp"},
              headers=headers)
    r = client.delete("/api/v1/affiliates/me/places-api-key", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["cleared"] is True

    got = client.get("/api/v1/affiliates/me/places-api-key", headers=headers)
    assert got.json() == {"set": False}


def test_no_kek_configured_is_a_clean_503_not_a_crash():
    client = _make_app(kek="")
    _seed_manager(client, "aff-l5", "p-l5")
    r = client.put("/api/v1/affiliates/me/places-api-key", json={"api_key": "AIzaX"},
                   headers={"Authorization": f"Bearer {_token(sub='p-l5')}"})
    assert r.status_code == 503
