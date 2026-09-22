"""POST /api/v1/subscription/renew-now — the console's own path to the SAME early-renewal
mechanism (`adapters/renewal_provider.py::RenewalProvider.renew_now`) the WhatsApp renewal Flow's
own "جدد الآن" button already uses. See that module's own docstring for the full ownership-check/
run-cycle/pay-link sequence this route calls unchanged."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant="tnt_renew_now"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _FakeRenewalProvider:
    def __init__(self, result: dict) -> None:
        self._result = result
        self.calls: list[dict] = []

    async def renew_now(self, *, tenant: str) -> dict:
        self.calls.append({"tenant": tenant})
        return self._result


def _swap(client, provider):
    c = client.app.state.container
    saved = c.renewal_provider
    c.renewal_provider = provider
    return saved


def _restore(client, saved):
    client.app.state.container.renewal_provider = saved


def test_a_successful_early_renewal_returns_the_real_pay_urls(client):
    fake = _FakeRenewalProvider({"ok": True, "refs": ["https://pay.example/tok_abc",
                                                       "https://pay.example/tok_def"]})
    saved = _swap(client, fake)
    try:
        r = client.post("/api/v1/subscription/renew-now", json={}, headers=_headers())
    finally:
        _restore(client, saved)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "pay_urls": ["https://pay.example/tok_abc",
                                                 "https://pay.example/tok_def"]}
    # THE REAL TENANT, FROM THE TOKEN — never trusted from the request body (there is none to
    # trust any more; `renew_now` takes only `tenant`, the whole group, never one sub_id).
    assert fake.calls == [{"tenant": "tnt_renew_now"}]


def test_a_refused_renewal_is_a_409_with_the_real_reason(client):
    fake = _FakeRenewalProvider({"ok": False, "reason": "لا يوجد اشتراك نشط يستحق تجديدًا الآن."})
    saved = _swap(client, fake)
    try:
        r = client.post("/api/v1/subscription/renew-now", json={}, headers=_headers())
    finally:
        _restore(client, saved)
    assert r.status_code == 409, r.text
    assert r.json()["message"] == "لا يوجد اشتراك نشط يستحق تجديدًا الآن."


def test_refuses_without_a_token(client):
    r = client.post("/api/v1/subscription/renew-now", json={})
    assert r.status_code in (401, 403)
