"""§٦'s managed sector taxonomy + the lead follow-up pipeline — capability gating on the admin
side, ownership on the marketer side, and the manual link-registration boundary.
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
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def sectors_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(sectors_env) -> TestClient:
    return _make_app()


def _token(caps=None, **over) -> str:
    # Default to the one capability every approved affiliate token holds
    # (`affiliates.self`, 2026-08-22) — a test wanting to prove a 403 from a MISSING
    # capability passes `caps=[]` explicitly; every ordinary self-service call gets
    # the real baseline instead of an empty list that never existed on a real token.
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    claims["caps"] = list(caps) if caps is not None else ["affiliates.self"]
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


ADMIN = {"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"}


# ── admin sector management ──────────────────────────────────────────────────────────────────

def test_create_sector_refuses_without_the_capability(client):
    r = client.put("/api/v1/admin/sectors", json={"code": "x", "name": "س"},
                   headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_create_then_list_active_sector(client):
    r = client.put("/api/v1/admin/sectors", json={"code": "salons", "name": "صالونات نسائية"},
                   headers=ADMIN)
    assert r.status_code == 200, r.text

    admin_list = client.get("/api/v1/admin/sectors", headers=ADMIN)
    assert any(s["code"] == "salons" for s in admin_list.json()["sectors"])


def test_a_signed_in_affiliate_reads_the_active_sector_list(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id="aff-sec1", person_id="p-sec1", phone="+966501230001",
                        name="مسوّق", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())
    r = client.get("/api/v1/affiliates/me/sectors",
                   headers={"Authorization": f"Bearer {_token(sub='p-sec1')}"})
    assert r.status_code == 200, r.text
    assert any(s["code"] == "salons" for s in r.json()["sectors"])


def test_deactivate_then_it_drops_from_the_active_list_but_not_the_admin_one(client):
    client.put("/api/v1/admin/sectors", json={"code": "carwash", "name": "مغاسل سيارات"},
              headers=ADMIN)
    r = client.delete("/api/v1/admin/sectors/carwash", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["deactivated"] is True

    active = client.get("/api/v1/admin/sectors", headers=ADMIN).json()["sectors"]
    row = next(s for s in active if s["code"] == "carwash")
    assert row["active"] is False   # still listed for the admin, just off


def test_platform_sector_stats_refuses_without_the_capability(client):
    r = client.get("/api/v1/admin/sectors/stats", headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_platform_sector_stats_is_reachable_with_the_capability(client):
    r = client.get("/api/v1/admin/sectors/stats", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert "stats" in r.json()


# ── the lead follow-up pipeline + manual registration link ──────────────────────────────────────

def _seed_promoter_with_lead(client: TestClient, *, affiliate_id: str, person_id: str,
                             lead_id: str) -> None:
    from app.core.models import ACTIVE, AFFILIATES, LEADS, Affiliate, Lead

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=affiliate_id, person_id=person_id, phone=f"+96650124{affiliate_id[-1]}001",
                        name="مسوّق", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())
        lead = Lead(id=lead_id, place_id=lead_id, source_manager_id="some-manager",
                   assigned_to=affiliate_id, status="assigned")
        await c.datastore.put(LEADS, lead_id, lead.to_dict())

    asyncio.run(seed())


def test_set_lead_status_by_the_assigned_promoter(client):
    _seed_promoter_with_lead(client, affiliate_id="aff-pl1", person_id="p-pl1", lead_id="lead-pl1")
    r = client.post("/api/v1/affiliates/me/leads/lead-pl1/status",
                    json={"status": "interested", "text": "متحمس يبدأ الأسبوع الجاي"},
                    headers={"Authorization": f"Bearer {_token(sub='p-pl1')}"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "interested"
    assert r.json()["notes"][-1]["text"] == "متحمس يبدأ الأسبوع الجاي"


def test_set_lead_status_refuses_for_an_unrelated_affiliate(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id="aff-pl2", person_id="p-pl2", phone="+966501240002",
                        name="آخر", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())
    r = client.post("/api/v1/affiliates/me/leads/lead-pl1/status",
                    json={"status": "interested"},
                    headers={"Authorization": f"Bearer {_token(sub='p-pl2')}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "not_yours"


def test_link_registration_end_to_end(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        mgr = Affiliate(id="aff-lr1", person_id="p-lr1", phone="+966501250001",
                        name="مدير", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, mgr.id, mgr.to_dict())
        await c.referrals.stamp(tenant="t-lr1", affiliate_id="aff-lr1")

    asyncio.run(seed())
    from app.core.models import LEADS, Lead

    async def seed_lead():
        c = client.app.state.container
        lead = Lead(id="lead-lr1", place_id="lead-lr1", source_manager_id="aff-lr1")
        await c.datastore.put(LEADS, "lead-lr1", lead.to_dict())

    asyncio.run(seed_lead())

    r = client.post("/api/v1/affiliates/me/leads/lead-lr1/link-registration",
                    json={"tenant": "t-lr1"},
                    headers={"Authorization": f"Bearer {_token(sub='p-lr1')}"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "registered"
    assert r.json()["converted_tenant"] == "t-lr1"


def test_sector_stats_route_for_a_manager(client):
    from app.core.models import ACTIVE, AFFILIATES, LEADS, Affiliate, Lead

    async def seed():
        c = client.app.state.container
        mgr = Affiliate(id="aff-ss1", person_id="p-ss1", phone="+966501260001",
                        name="مدير", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, mgr.id, mgr.to_dict())
        lead = Lead(id="lead-ss1", place_id="lead-ss1", source_manager_id="aff-ss1",
                   sector_code="salons", city="الرياض")
        await c.datastore.put(LEADS, "lead-ss1", lead.to_dict())

    asyncio.run(seed())
    r = client.get("/api/v1/affiliates/me/leads/sector-stats",
                   headers={"Authorization": f"Bearer {_token(sub='p-ss1')}"})
    assert r.status_code == 200, r.text
    assert any(s["sector_code"] == "salons" for s in r.json()["stats"])
