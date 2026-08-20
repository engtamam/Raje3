"""The routes over the withdrawal itself — capability gating for the admin/finance side, and
the self-tier's own 404-when-not-an-affiliate discipline (test_onboarding_api.py's own pattern).
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


def _make_app() -> TestClient:
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
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def payouts_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(payouts_env) -> TestClient:
    return _make_app()


def _token(caps=None, **over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    if caps is not None:
        claims["caps"] = caps
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_set_payout_method_refuses_with_no_token(client):
    r = client.put("/api/v1/affiliates/me/payout-method",
                   json={"channel": "bank_iban", "account_ref": "SA00"})
    assert r.status_code == 401


def test_set_payout_method_404s_for_a_non_affiliate(client):
    r = client.put("/api/v1/affiliates/me/payout-method",
                   json={"channel": "bank_iban", "account_ref": "SA00"},
                   headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 404


def test_balance_404s_for_a_non_affiliate(client):
    r = client.get("/api/v1/affiliates/me/balance",
                   headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 404


def test_request_withdrawal_404s_for_a_non_affiliate(client):
    r = client.post("/api/v1/affiliates/me/withdrawals",
                    headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 404


def test_admin_withdrawals_queue_refuses_without_the_finance_capability(client):
    r = client.get("/api/v1/admin/withdrawals",
                   headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_admin_withdrawals_queue_refuses_with_the_wrong_affiliates_capability(client):
    # platform.affiliates (application review) must NOT double as platform.affiliates_payouts
    # (settling money) — the whole point of splitting them.
    r = client.get("/api/v1/admin/withdrawals",
                   headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"})
    assert r.status_code == 403


def test_admin_withdrawals_queue_works_with_the_finance_capability(client):
    r = client.get("/api/v1/admin/withdrawals",
                   headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates_payouts'])}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"withdrawals": []}


def test_complete_refuses_without_the_finance_capability(client):
    r = client.post("/api/v1/admin/withdrawals/does-not-exist/complete",
                    json={"receipt_reference": "r"},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_completing_an_unknown_withdrawal_is_a_clean_400(client):
    r = client.post("/api/v1/admin/withdrawals/does-not-exist/complete",
                    json={"receipt_reference": "r"},
                    headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates_payouts'])}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "not_found"


def test_reject_refuses_without_the_finance_capability(client):
    r = client.post("/api/v1/admin/withdrawals/does-not-exist/reject", json={},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403
