"""The routes over «رشّح نفسك لوظيفة» (spec §8) — capability gating on the platform.affiliates
side (an HR decision, deliberately NOT platform.affiliates_payouts), and the marketer's own
request path end to end.
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
        "AFFILIATE_EMPLOYMENT_THRESHOLD_CUSTOMERS": "3",
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def employment_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(employment_env) -> TestClient:
    return _make_app()


def _token(caps=None, **over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    if caps is not None:
        claims["caps"] = caps
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


ADMIN = {"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"}
_seed_counter = [0]


def _seed_eligible_affiliate(client: TestClient) -> str:
    """Three CONFIRMED conversion commissions — meets the test env's threshold of 3."""
    from app.core.models import ACTIVE, AFFILIATES, COMMISSIONS, CONFIRMED, CONVERSION, Affiliate, Commission

    _seed_counter[0] += 1
    n = _seed_counter[0]

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=f"aff-e{n}", person_id=f"p-e{n}", phone=f"+96650333{n:04d}",
                        name="مسوّق", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())
        for i in range(3):
            commission = Commission(id=f"inv-e{n}-{i}", tenant=f"t-e{n}-{i}", affiliate_id=aff.id,
                                    kind=CONVERSION, amount_halalas=4000, status=CONFIRMED)
            await c.datastore.put(COMMISSIONS, commission.id, commission.to_dict())
        return aff.id

    return asyncio.run(seed())


def test_employment_request_refuses_with_no_token(client):
    r = client.post("/api/v1/affiliates/me/employment-requests")
    assert r.status_code == 401


def test_employment_request_below_threshold_is_a_clean_400(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id="aff-e-low", person_id="p-e-low", phone="+966503339999",
                        name="مسوّق قليل", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())
    r = client.post("/api/v1/affiliates/me/employment-requests",
                    headers={"Authorization": f"Bearer {_token(sub='p-e-low')}"})
    assert r.status_code == 400, r.text
    assert r.json()["reason"] == "below_threshold"


def test_employment_request_then_a_second_one_is_already_pending(client):
    aff_id = _seed_eligible_affiliate(client)
    headers = {"Authorization": f"Bearer {_token(sub=aff_id.replace('aff-e', 'p-e'))}"}

    first = client.post("/api/v1/affiliates/me/employment-requests", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["converted_customers"] == 3

    second = client.post("/api/v1/affiliates/me/employment-requests", headers=headers)
    assert second.json()["reason"] == "already_pending"

    mine = client.get("/api/v1/affiliates/me/employment-requests", headers=headers)
    assert len(mine.json()["employment_requests"]) == 1


def test_admin_decision_refuses_without_the_capability(client):
    r = client.post("/api/v1/admin/employment-requests/does-not-exist/decision",
                    json={"decision": "approved"},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_admin_approves_a_request_and_a_further_one_is_a_no_op(client):
    aff_id = _seed_eligible_affiliate(client)
    headers = {"Authorization": f"Bearer {_token(sub=aff_id.replace('aff-e', 'p-e'))}"}
    req = client.post("/api/v1/affiliates/me/employment-requests", headers=headers).json()

    decided = client.post(f"/api/v1/admin/employment-requests/{req['id']}/decision",
                          json={"decision": "approved"}, headers=ADMIN)
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"

    again = client.post("/api/v1/affiliates/me/employment-requests", headers=headers)
    assert again.json() == {"ok": True, "already_approved": True}


def test_a_rejected_request_can_be_retried_with_no_cooldown(client):
    aff_id = _seed_eligible_affiliate(client)
    headers = {"Authorization": f"Bearer {_token(sub=aff_id.replace('aff-e', 'p-e'))}"}
    req = client.post("/api/v1/affiliates/me/employment-requests", headers=headers).json()
    client.post(f"/api/v1/admin/employment-requests/{req['id']}/decision",
               json={"decision": "rejected"}, headers=ADMIN)

    retry = client.post("/api/v1/affiliates/me/employment-requests", headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] != req["id"]
