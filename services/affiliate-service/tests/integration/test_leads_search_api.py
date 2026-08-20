"""The routes over §٦'s search job + assignment — managers-only gate, ownership boundaries, and
POST /internal/leads/tick's own internal-token gate + quiet no-op when nothing is pending.
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
INTERNAL_TOKEN = "t" * 40

RIYADH = {"name": "الرياض", "region": "منطقة الرياض", "lat": 24.7136, "lng": 46.6753,
         "w_km": 0.001, "h_km": 0.001}


def _make_app() -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
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
def leads_search_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(leads_search_env) -> TestClient:
    return _make_app()


def _token(**over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _seed_manager(client: TestClient, affiliate_id: str, person_id: str) -> None:
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=affiliate_id, person_id=person_id, phone=f"+96650555{affiliate_id[-1]}0001",
                        name="مدير", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())


def _seed_promoter(client: TestClient, affiliate_id: str, person_id: str) -> None:
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=affiliate_id, person_id=person_id, phone=f"+96650555{affiliate_id[-1]}0002",
                        name="مسوّق", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())


def test_start_search_refuses_with_no_token(client):
    r = client.post("/api/v1/affiliates/me/leads/search",
                    json={"keywords": ["صالون"], "cities": [RIYADH]})
    assert r.status_code == 401


def test_a_promoter_cannot_start_a_search(client):
    _seed_promoter(client, "aff-s1", "p-s1")
    r = client.post("/api/v1/affiliates/me/leads/search",
                    json={"keywords": ["صالون"], "cities": [RIYADH]},
                    headers={"Authorization": f"Bearer {_token(sub='p-s1')}"})
    assert r.status_code == 403


def test_a_manager_starts_a_search_and_polls_its_status(client):
    _seed_manager(client, "aff-s2", "p-s2")
    headers = {"Authorization": f"Bearer {_token(sub='p-s2')}"}
    started = client.post("/api/v1/affiliates/me/leads/search",
                          json={"place_type": "صالون", "keywords": ["صالون"], "cities": [RIYADH]},
                          headers=headers)
    assert started.status_code == 200, started.text
    job_id = started.json()["id"]
    assert started.json()["status"] == "queued"

    status = client.get(f"/api/v1/affiliates/me/leads/search/{job_id}", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["id"] == job_id

    listing = client.get("/api/v1/affiliates/me/leads/search", headers=headers)
    assert any(j["id"] == job_id for j in listing.json()["jobs"])


def test_a_manager_cannot_see_another_managers_job_status(client):
    _seed_manager(client, "aff-s3", "p-s3")
    _seed_manager(client, "aff-s4", "p-s4")
    started = client.post("/api/v1/affiliates/me/leads/search",
                          json={"keywords": ["صالون"], "cities": [RIYADH]},
                          headers={"Authorization": f"Bearer {_token(sub='p-s3')}"})
    job_id = started.json()["id"]

    r = client.get(f"/api/v1/affiliates/me/leads/search/{job_id}",
                   headers={"Authorization": f"Bearer {_token(sub='p-s4')}"})
    assert r.status_code == 404


def test_tick_refuses_without_the_internal_token(client):
    r = client.post("/internal/leads/tick")
    assert r.status_code == 401


def test_tick_is_a_quiet_no_op_when_nothing_is_pending(client):
    r = client.post("/internal/leads/tick", headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    # Either genuinely nothing pending, or (since this client is shared module-wide across the
    # tests above) an earlier test's queued job — either is a clean 200, never a 500.
    assert "ticked" in r.json()


def test_assign_refuses_a_lead_that_is_not_the_managers_own(client):
    _seed_manager(client, "aff-s5", "p-s5")
    r = client.post("/api/v1/affiliates/me/leads/does-not-exist/assign",
                    json={"promoter_id": "whoever"},
                    headers={"Authorization": f"Bearer {_token(sub='p-s5')}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "not_found"


def test_my_leads_branches_by_role_empty_either_way_with_no_data(client):
    _seed_manager(client, "aff-s6", "p-s6")
    _seed_promoter(client, "aff-s7", "p-s7")
    mgr = client.get("/api/v1/affiliates/me/leads",
                     headers={"Authorization": f"Bearer {_token(sub='p-s6')}"})
    assert mgr.status_code == 200, mgr.text
    assert mgr.json() == {"leads": []}

    prm = client.get("/api/v1/affiliates/me/leads",
                     headers={"Authorization": f"Bearer {_token(sub='p-s7')}"})
    assert prm.status_code == 200, prm.text
    assert prm.json() == {"leads": []}
