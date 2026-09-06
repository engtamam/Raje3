"""The operator surface.

The load-bearing tests here are negative ones: that the capability is required, and that a knob
which must stay deploy-time is refused. The happy paths are easy and were never the risk.
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
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


@pytest.fixture
def operator_auth() -> dict:
    return _auth("platform.config")


@pytest.fixture
def reader_auth() -> dict:
    """Holds a capability, but not this one."""
    return _auth("reports.read")


# ── authorisation ─────────────────────────────────────────────────────────────
def test_config_needs_its_own_capability(client, reader_auth):
    assert client.get("/api/v1/loyalty/operator/config", headers=reader_auth).status_code == 403


def test_unauthenticated_is_refused(client):
    assert client.get("/api/v1/loyalty/operator/config").status_code == 401


# ── policy ────────────────────────────────────────────────────────────────────
def test_a_deploy_time_knob_is_refused(client, operator_auth):
    """Wiring changed under a live request is a class of bug nobody can reproduce."""
    for key in ("DATASTORE_DRIVER", "SECRETS_KEK", "PII_SALT", "INTERNAL_SERVICE_TOKEN"):
        r = client.put("/api/v1/loyalty/operator/config",
                       json={"key": key, "value": "anything"}, headers=operator_auth)
        assert r.status_code == 400, f"{key} was accepted at runtime"


def test_the_config_view_never_carries_a_credential(client, operator_auth):
    view = client.get("/api/v1/loyalty/operator/config", headers=operator_auth).json()["config"]
    for banned in ("SECRETS_KEK", "INTERNAL_SERVICE_TOKEN", "PII_SALT", "DATASTORE_DSN"):
        assert banned not in view


def test_the_scaffold_declares_no_runtime_policy_so_it_offers_none(client, operator_auth):
    """The template deliberately declares nothing, and the surface must reflect that rather than
    advertising every settable field.

    A generated service adds a key to RUNTIME_POLICY in the same change that wires the read. Until
    then the knob is unavailable, which is honest — an advertised knob nothing consults reports a
    change that never happened, with an audit entry to prove it.
    """
    h = {"headers": operator_auth}
    assert client.get("/api/v1/loyalty/operator/config", **h).json()["config"] == {}
    r = client.put("/api/v1/loyalty/operator/config", json={"key": "RATELIMIT_MAX", "value": 250}, **h)
    assert r.status_code == 400, "an undeclared knob was accepted and would have been inert"
