"""GET /me/home — the composite home-screen endpoint: one call instead of six-to-eight, server-
side fan-out over data every other route already exposes separately.
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
        "SECRETS_KEK": "k" * 32,
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def home_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(home_env) -> TestClient:
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


def test_home_refuses_with_no_token(client):
    r = client.get("/api/v1/affiliates/me/home")
    assert r.status_code == 401


def test_a_promoters_home_has_no_team_section(client):
    from app.core.models import ACTIVE, AFFILIATES, PROMOTER, Affiliate

    async def go():
        c = client.app.state.container
        aff = Affiliate(id="pro-home1", person_id="p-home1", phone="+966501110001",
                        name="مسوّق", role=PROMOTER, status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(go())
    r = client.get("/api/v1/affiliates/me/home",
                   headers={"Authorization": f"Bearer {_token(sub='p-home1')}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "team" not in body
    assert "places_api_key_set" not in body
    assert body["affiliate"]["id"] == "pro-home1"
    assert body["balance"]["pending_halalas"] == 0
    assert body["payout_method_set"] is False
    assert body["stale_leads_count"] == 0
    assert body["wafa_eligibility"]["active_shops"] == 0
    assert body["employment_eligibility"]["converted_customers"] == 0
    assert body["top_template_this_period"] is None


def test_a_managers_home_has_the_team_section(client):
    from app.core.models import ACTIVE, AFFILIATES, MANAGER, PROMOTER, Affiliate

    async def go():
        c = client.app.state.container
        mgr = Affiliate(id="mgr-home1", person_id="p-home2", phone="+966501110002",
                        name="مدير", role=MANAGER, status=ACTIVE)
        await c.datastore.put(AFFILIATES, mgr.id, mgr.to_dict())
        pro = Affiliate(id="pro-home2", person_id="p-home3", phone="+966501110003",
                        name="مسوّق", role=PROMOTER, status=ACTIVE, parent_id=mgr.id)
        await c.datastore.put(AFFILIATES, pro.id, pro.to_dict())

    asyncio.run(go())
    r = client.get("/api/v1/affiliates/me/home",
                   headers={"Authorization": f"Bearer {_token(sub='p-home2')}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["team"]["member_count"] == 1
    assert body["team"]["pending_wafa_requests_count"] == 0
    assert body["places_api_key_set"] is False


def test_stale_leads_surface_on_the_promoters_home(client):
    from app.core.models import ACTIVE, AFFILIATES, LEADS, LEAD_ASSIGNED, PROMOTER, Affiliate, Lead

    async def go():
        c = client.app.state.container
        aff = Affiliate(id="pro-home3", person_id="p-home4", phone="+966501110004",
                        name="مسوّق", role=PROMOTER, status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())
        old_lead = Lead(id="lead-home1", place_id="lead-home1", assigned_to=aff.id,
                        status=LEAD_ASSIGNED, found_at=0)   # epoch — unambiguously stale
        await c.datastore.put(LEADS, old_lead.id, old_lead.to_dict())

    asyncio.run(go())
    r = client.get("/api/v1/affiliates/me/home",
                   headers={"Authorization": f"Bearer {_token(sub='p-home4')}"})
    assert r.status_code == 200, r.text
    assert r.json()["stale_leads_count"] == 1


def test_pending_withdrawal_flag_appears_only_when_one_is_requested(client):
    from app.core.models import ACTIVE, AFFILIATES, PROMOTER, Affiliate

    async def go():
        c = client.app.state.container
        aff = Affiliate(id="pro-home5", person_id="p-home5", phone="+966501110005",
                        name="مسوّق", role=PROMOTER, status=ACTIVE,
                        payout_channel="bank_iban", payout_account_ref="SA0000000000000000000000")
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(go())
    tok = {"Authorization": f"Bearer {_token(sub='p-home5')}"}
    r = client.get("/api/v1/affiliates/me/home", headers=tok)
    assert r.status_code == 200, r.text
    assert r.json()["payout_method_set"] is True
    assert "pending_withdrawal" not in r.json()   # nothing requested yet
