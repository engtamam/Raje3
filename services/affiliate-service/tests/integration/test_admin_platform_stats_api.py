"""The admin panel's own cross-affiliate dashboard reads (phase 11 of the admin panel plan):
active-affiliate count + platform revenue, the leaderboard, and the leads geo map. All three are
platform.affiliates-gated, cross-manager reads — no manager-scoped route exposes any of this.
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
def stats_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(stats_env) -> TestClient:
    return _make_app()


def _token(caps=None, **over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    claims["caps"] = list(caps) if caps is not None else ["affiliates.self"]
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


ADMIN = {"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"}
NO_CAP = {"Authorization": f"Bearer {_token(caps=[])}"}


# ── GET /api/v1/admin/affiliates/stats ──────────────────────────────────────────────────────

def test_platform_stats_refuses_without_the_capability(client):
    r = client.get("/api/v1/admin/affiliates/stats", headers=NO_CAP)
    assert r.status_code == 403


def test_platform_stats_counts_only_active_affiliates(client):
    from app.core.models import ACTIVE, AFFILIATES, PROMOTER, SUSPENDED, Affiliate

    async def go():
        c = client.app.state.container
        await c.datastore.put(AFFILIATES, "stat-a1",
                              Affiliate(id="stat-a1", person_id="p-stat1", phone="+966501120001",
                                       name="نشط A", role=PROMOTER, status=ACTIVE).to_dict())
        await c.datastore.put(AFFILIATES, "stat-a2",
                              Affiliate(id="stat-a2", person_id="p-stat2", phone="+966501120002",
                                       name="نشط B", role=PROMOTER, status=ACTIVE).to_dict())
        await c.datastore.put(AFFILIATES, "stat-a3",
                              Affiliate(id="stat-a3", person_id="p-stat3", phone="+966501120003",
                                       name="موقوف", role=PROMOTER, status=SUSPENDED).to_dict())

    asyncio.run(go())
    r = client.get("/api/v1/admin/affiliates/stats", headers=ADMIN)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["active_affiliates"] >= 2
    assert body["total_affiliates"] >= 3
    assert "total_net_revenue_minor" in body
    assert "revenue_partial" in body


# ── GET /api/v1/admin/affiliates/leaderboard ────────────────────────────────────────────────

def test_leaderboard_refuses_without_the_capability(client):
    r = client.get("/api/v1/admin/affiliates/leaderboard", headers=NO_CAP)
    assert r.status_code == 403


def test_leaderboard_includes_only_active_affiliates_ranked_by_referrals(client):
    from app.core.models import (ACTIVE, AFFILIATES, PROMOTER, REFERRED, REFERRALS, SUSPENDED,
                                 Affiliate, Referral)

    async def go():
        c = client.app.state.container
        await c.datastore.put(AFFILIATES, "board-a1",
                              Affiliate(id="board-a1", person_id="p-board1", phone="+966501130001",
                                       name="الأول", role=PROMOTER, status=ACTIVE).to_dict())
        await c.datastore.put(AFFILIATES, "board-a2",
                              Affiliate(id="board-a2", person_id="p-board2", phone="+966501130002",
                                       name="موقوف", role=PROMOTER, status=SUSPENDED).to_dict())
        ref = Referral(id="ref-board1", affiliate_id="board-a1", tenant="tnt-board1",
                       status=REFERRED, commission_amount_halalas=5000)
        await c.datastore.put(REFERRALS, ref.id, ref.to_dict())

    asyncio.run(go())
    r = client.get("/api/v1/admin/affiliates/leaderboard", headers=ADMIN)
    assert r.status_code == 200, r.text
    board = r.json()["leaderboard"]
    ids = [row["affiliate_id"] for row in board]
    assert "board-a1" in ids
    assert "board-a2" not in ids   # suspended — never ranked
    row = next(row for row in board if row["affiliate_id"] == "board-a1")
    assert row["total_referrals"] >= 1
    assert "retention_rate" in row and "refund_rate" in row


def test_leaderboard_respects_the_limit_param(client):
    r = client.get("/api/v1/admin/affiliates/leaderboard?limit=1", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert len(r.json()["leaderboard"]) <= 1


# ── GET /api/v1/admin/leads/geo ─────────────────────────────────────────────────────────────

def test_leads_geo_refuses_without_the_capability(client):
    r = client.get("/api/v1/admin/leads/geo", headers=NO_CAP)
    assert r.status_code == 403


def test_leads_geo_drops_unlocated_rows_and_never_exposes_pii(client):
    from app.core.models import LEAD_NEW, LEADS, Lead

    async def go():
        c = client.app.state.container
        located = Lead(id="geo-lead1", place_id="geo-lead1", city="الرياض", sector_code="salon",
                       lat=24.71, lng=46.68, status=LEAD_NEW, phone="+966500000000",
                       name="اسم حقيقي لن يظهر")
        unlocated = Lead(id="geo-lead2", place_id="geo-lead2", city="جدة", status=LEAD_NEW)
        await c.datastore.put(LEADS, located.id, located.to_dict())
        await c.datastore.put(LEADS, unlocated.id, unlocated.to_dict())

    asyncio.run(go())
    r = client.get("/api/v1/admin/leads/geo", headers=ADMIN)
    assert r.status_code == 200, r.text
    points = r.json()["points"]
    ids = [p["id"] for p in points]
    assert "geo-lead1" in ids
    assert "geo-lead2" not in ids   # no lat/lng — dropped, not shown at (0, 0)
    row = next(p for p in points if p["id"] == "geo-lead1")
    assert set(row.keys()) == {"id", "lat", "lng", "city", "sector_code"}
    assert "phone" not in row and "name" not in row
