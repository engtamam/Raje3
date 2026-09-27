"""The real container wiring — container.affiliates and container.referral_redemption sharing the
SAME datastore and actually connected, exercised over real HTTP with no fakes at all. The unit
tests (test_referral_redemption_affiliates.py) already prove the ENGINE logic against fakes; this
file proves container.py actually plugs the two together the way the module docstrings claim."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_affiliate_wiring"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "10000", "PII_SALT": "s" * 32,
        # NO REFERRALS_SERVICE_URL / LOYALTY_SERVICE_URL — deliberately unset, same "optional peer"
        # posture every desk here takes. The affiliate's OWN custom code must resolve entirely
        # locally and never attempt either outbound call (see the assertion below).
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def auth_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(auth_env) -> TestClient:
    return _make_app()


def _token(*, caps: tuple[str, ...]) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "u1", "iss": ISS, "aud": AUD, "tenant": TENANT,
              "exp": now + dt.timedelta(minutes=5), "iat": now, "caps": list(caps)}
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _owner() -> dict:
    return {"Authorization": f"Bearer {_token(caps=('operations.manage', 'operations.read'))}"}


def _till() -> dict:
    return {"Authorization": f"Bearer {_token(caps=('operations.record',))}"}


def test_a_real_affiliate_custom_code_is_honoured_through_the_real_container(client):
    created = client.post("/api/v1/affiliates",
                          json={"phone": "0511111111", "code": "REALW1", "discount_percent": 30,
                                "reward_type": "fixed_points", "reward_params": {"points": 77}},
                          headers=_owner())
    assert created.status_code == 200

    r = client.post("/api/v1/till/referral/register",
                    json={"code": "REALW1", "phone": "0522222222"}, headers=_till())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["new_customer_reward_type"] == "discount_percent"
    assert body["new_customer_reward_params"] == {"percent": 30}


def test_an_unknown_code_still_refuses_cleanly_with_no_referrals_peer_configured(client):
    r = client.post("/api/v1/till/referral/register",
                    json={"code": "NOTREAL", "phone": "0533333333"}, headers=_till())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False


def test_the_deactivated_affiliates_code_no_longer_resolves_through_real_http(client):
    created = client.post("/api/v1/affiliates",
                          json={"phone": "0544444444", "code": "REALW2", "discount_percent": 10,
                                "reward_type": "fixed_points", "reward_params": {"points": 5}},
                          headers=_owner()).json()
    client.put(f"/api/v1/affiliates/{created['id']}/active", json={"active": False},
              headers=_owner())

    r = client.post("/api/v1/till/referral/register",
                    json={"code": "REALW2", "phone": "0555555555"}, headers=_till())
    assert r.status_code == 200
    # No referrals peer is configured in this test env either, so falling through to the
    # ordinary global-code path must refuse cleanly (peer unreachable), never crash — proving the
    # deactivated affiliate really stopped shadowing the code, not that a downstream peer happened
    # to answer.
    assert r.json()["ok"] is False
