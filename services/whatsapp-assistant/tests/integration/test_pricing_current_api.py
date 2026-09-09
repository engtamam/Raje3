"""GET /api/v1/assistant/pricing/current — the shop's OWN app-store-card read (never
platform.config): the current effective price, and anything already scheduled but not yet in
effect, per app/api/v1/__init__.py's own route docstring.
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

PATH = "/api/v1/assistant/pricing/current"


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


@pytest.fixture
def shop_auth() -> dict:
    return _auth("whatsapp_assistant.pricing_read")


def test_unauthenticated_is_refused(client):
    assert client.get(PATH).status_code == 401


def test_a_shop_without_the_capability_is_refused(client):
    r = client.get(PATH, headers=_auth("reports.read"))
    assert r.status_code == 403


def test_platform_config_alone_does_not_grant_this_read(client):
    """The operator capability and the shop capability are deliberately different — a platform
    operator token has no reason to double as a shop session, and vice versa."""
    r = client.get(PATH, headers=_auth("platform.config"))
    assert r.status_code == 403


def test_the_deploy_time_defaults_with_nothing_pending(client, shop_auth):
    body = client.get(PATH, headers=shop_auth).json()
    assert body == {
        "ai_unit_units_per_halala": 1000,
        "pending_changes": [],
    }


def test_a_change_scheduled_by_the_operator_shows_up_here_with_its_effective_date(
    client, shop_auth,
):
    operator_auth = _auth("platform.config")
    r = client.post("/api/v1/assistant/operator/pricing/schedule",
                    json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0,
                          "effective_in_days": 15},
                    headers=operator_auth)
    assert r.status_code == 200, r.text
    effective_at = r.json()["effective_at"]

    body = client.get(PATH, headers=shop_auth).json()
    # STILL THE OLD EFFECTIVE VALUE — it has not landed yet.
    assert body["ai_unit_units_per_halala"] == 1000
    # BUT VISIBLE, WITH THE REAL DATE — this is the whole feature: "ما كنت أعرف" is never true.
    assert body["pending_changes"] == [
        {"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0, "effective_at": effective_at},
    ]


def test_a_landed_ai_unit_rate_change_is_reflected_here(client, shop_auth):
    """`ai_unit_units_per_halala` is the ONE AI-unit field this route ever returns — a shop reads
    the fixed display scale, never a margin or a per-model cost (our own internal cost basis)."""
    operator_auth = _auth("platform.config")
    now = int(__import__("time").time())

    import asyncio

    from app.core.pricing_schedule import apply_due, schedule

    container = client.app.state.container
    asyncio.run(schedule(container.datastore, key="PRICING_AI_UNIT_UNITS_PER_HALALA",
                         value=2000, effective_at=now - 1, actor="op1", now=now - 100))
    asyncio.run(apply_due(container.datastore, container.runtime_config, now=now))

    body = client.get(PATH, headers=shop_auth).json()
    assert body["ai_unit_units_per_halala"] == 2000
