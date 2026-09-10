"""POST /internal/whatsapp/renewal-provider — the subscription-renewal WhatsApp Flow's data source
(platform v0.19.12's LoyaltyEngine(name="subscription_renewal")), gated by the shared internal
token, dispatching balance/rewards/redeem to `container.renewal_provider`."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

INTERNAL_TOKEN = "t" * 40


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss",
        "TOKEN_AUDIENCE": "aud",
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


class _Provider:
    def __init__(self, *, balance_result=None, rewards_result=None, redeem_result=None,
                raises=None):
        self._balance = balance_result
        self._rewards = rewards_result if rewards_result is not None else []
        self._redeem = redeem_result
        self._raises = raises

    async def balance(self, *, tenant, customer):
        if self._raises:
            raise self._raises
        return self._balance

    async def rewards(self, *, tenant, customer):
        if self._raises:
            raise self._raises
        return self._rewards

    async def redeem(self, *, tenant, customer, reward, idempotency_key):
        if self._raises:
            raise self._raises
        return self._redeem


def _swap(client, provider):
    saved = client.app.state.container.renewal_provider
    client.app.state.container.renewal_provider = provider
    return saved


def _post(client, body, token=INTERNAL_TOKEN):
    headers = {"X-Internal-Token": token} if token is not None else {}
    return client.post("/internal/whatsapp/renewal-provider", json=body, headers=headers)


def test_requires_the_internal_token(client):
    r = _post(client, {"op": "balance"}, token="wrong")
    assert r.status_code == 401


def test_balance_returns_the_providers_own_body(client):
    saved = _swap(client, _Provider(balance_result={"label": "المستحق: 150.00 SAR"}))
    try:
        r = _post(client, {"op": "balance", "tenant": "t1", "customer": "inv_1"})
        assert r.status_code == 200
        assert r.json() == {"label": "المستحق: 150.00 SAR"}
    finally:
        client.app.state.container.renewal_provider = saved


def test_rewards_wraps_the_list(client):
    saved = _swap(client, _Provider(rewards_result=[{"id": "inv_1", "title": "تجديد"}]))
    try:
        r = _post(client, {"op": "rewards", "tenant": "t1", "customer": "inv_1"})
        assert r.status_code == 200
        assert r.json() == {"rewards": [{"id": "inv_1", "title": "تجديد"}]}
    finally:
        client.app.state.container.renewal_provider = saved


def test_redeem_returns_the_pay_link_ref(client):
    saved = _swap(client, _Provider(redeem_result={"ok": True, "ref": "https://pay.raje3.sa/x"}))
    try:
        r = _post(client, {"op": "redeem", "tenant": "t1", "customer": "inv_1",
                          "reward": "inv_1", "idempotency_key": "tok_1"})
        assert r.status_code == 200
        assert r.json() == {"ok": True, "ref": "https://pay.raje3.sa/x"}
    finally:
        client.app.state.container.renewal_provider = saved


def test_unknown_op_is_422(client):
    r = _post(client, {"op": "bogus", "tenant": "t1"})
    assert r.status_code == 422


def test_unavailable_provider_is_502_never_a_fake_answer(client):
    from app.adapters.renewal_provider import RenewalUnavailable

    saved = _swap(client, _Provider(raises=RenewalUnavailable("billing unreachable")))
    try:
        r = _post(client, {"op": "balance", "tenant": "t1", "customer": "inv_1"})
        assert r.status_code == 502
    finally:
        client.app.state.container.renewal_provider = saved
