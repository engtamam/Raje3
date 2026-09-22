"""«/account/me/mobile-ai-assistant» — the one thing apps/mobile itself needs to ask before it
shows any AI surface at all: does this shop hold `feature.mobile_ai_assistant`. `require_user`
only, same posture `/account/me/locale`/`/account/me/name` already take — narrower than
`/subscription/apps` (owner-only, whole catalogue), because mobile needs exactly one boolean.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest


TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app():
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000", "SECRETS_KEK": "unit-test-kek-not-a-real-key",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(subject: str = "owner1", *, tenant: str = "t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD, "caps": [],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def client(env_guard):
    return _make_app()


def test_no_capability_needed_at_all_owner_included(client):
    """The whole point, same as /account/me/locale's own test of the same name: an owner with no
    `operations.*` capability at all can still ask this."""
    from app.core.apps import NullApps

    client.app.state.container.apps = NullApps(owned={"feature.mobile_ai_assistant"})
    r = client.get("/api/v1/account/me/mobile-ai-assistant", headers=_auth())
    assert r.status_code == 200
    assert r.json() == {"subscribed": True, "checked": True}


def test_a_shop_that_never_subscribed_reads_false_not_missing(client):
    from app.core.apps import NullApps

    client.app.state.container.apps = NullApps(owned=set())
    r = client.get("/api/v1/account/me/mobile-ai-assistant", headers=_auth())
    assert r.status_code == 200
    assert r.json() == {"subscribed": False, "checked": True}


def test_a_billing_outage_answers_checked_false_never_a_silent_unsubscribed(client):
    """Same `checked` honesty `/subscription/apps`'s own docstring states: a billing outage must
    never read to a paying shop as "you have not paid"."""
    from app.core.apps import NullApps

    fake = NullApps(owned={"feature.mobile_ai_assistant"})
    fake.reachable = False
    client.app.state.container.apps = fake
    r = client.get("/api/v1/account/me/mobile-ai-assistant", headers=_auth())
    assert r.status_code == 200
    assert r.json() == {"subscribed": False, "checked": False}
