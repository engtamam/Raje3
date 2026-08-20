"""The routes over «برنامج دعم الوفاء» (spec §8) — capability gating for the admin side, the
manager's own team-scoped ownership check, and the marketer's own request path end to end.
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
        "WAFA_TIER_SHOPS": "50",
        "WAFA_TIER_AMOUNT_HALALAS": "50000",
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def wafa_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(wafa_env) -> TestClient:
    return _make_app()


def _token(caps=None, **over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    if caps is not None:
        claims["caps"] = caps
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


FINANCE = {"Authorization": f"Bearer {_token(caps=['platform.affiliates_payouts'])}"}
_seed_counter = [0]


def _seed_eligible_promoter(client: TestClient, *, manager_id: str = "") -> str:
    """Seeds ONE promoter with exactly the WAFA_TIER_SHOPS he needs to be request-eligible.
    Returns his affiliate id. A fresh id set per call, same reasoning as test_payouts_api.py's
    own `_seed_counter` — the client/container is shared module-wide."""
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    _seed_counter[0] += 1
    n = _seed_counter[0]

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=f"aff-w{n}", person_id=f"p-w{n}", phone=f"+96650222{n:04d}",
                        name="مسوّق", role="affiliate_promoter", parent_id=manager_id, status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())
        for i in range(50):
            await c.referrals.stamp(tenant=f"t-w{n}-{i}", affiliate_id=aff.id)
        return aff.id

    return asyncio.run(seed())


def test_wafa_request_refuses_with_no_token(client):
    r = client.post("/api/v1/affiliates/me/wafa-requests")
    assert r.status_code == 401


def test_wafa_request_below_threshold_is_a_clean_400(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id="aff-w-low", person_id="p-w-low", phone="+966502229999",
                        name="مسوّق قليل", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())
    r = client.post("/api/v1/affiliates/me/wafa-requests",
                    headers={"Authorization": f"Bearer {_token(sub='p-w-low')}"})
    assert r.status_code == 400, r.text
    assert r.json()["ok"] is False
    assert r.json()["reason"] == "below_threshold"


def test_wafa_request_then_a_second_one_is_already_pending(client):
    aff_id = _seed_eligible_promoter(client)
    person_id = aff_id.replace("aff-w", "p-w")
    headers = {"Authorization": f"Bearer {_token(sub=person_id)}"}

    first = client.post("/api/v1/affiliates/me/wafa-requests", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["ok"] is True
    assert first.json()["tier_amount_halalas"] == 50000
    assert first.json()["system_recommendation"] == "approve"

    second = client.post("/api/v1/affiliates/me/wafa-requests", headers=headers)
    assert second.json()["reason"] == "already_pending"

    mine = client.get("/api/v1/affiliates/me/wafa-requests", headers=headers)
    assert mine.status_code == 200, mine.text
    assert len(mine.json()["wafa_requests"]) == 1


def test_admin_decision_refuses_without_the_capability(client):
    r = client.post("/api/v1/admin/wafa-requests/does-not-exist/decision",
                    json={"decision": "approve"},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_admin_can_grant_a_request_and_it_leaves_the_pending_queue(client):
    aff_id = _seed_eligible_promoter(client)
    person_id = aff_id.replace("aff-w", "p-w")
    headers = {"Authorization": f"Bearer {_token(sub=person_id)}"}
    req = client.post("/api/v1/affiliates/me/wafa-requests", headers=headers).json()

    before = client.get("/api/v1/admin/wafa-requests", headers=FINANCE)
    assert any(r["id"] == req["id"] for r in before.json()["wafa_requests"])

    decided = client.post(f"/api/v1/admin/wafa-requests/{req['id']}/decision",
                          json={"decision": "approve"}, headers=FINANCE)
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "granted"

    after = client.get("/api/v1/admin/wafa-requests", headers=FINANCE)
    assert not any(r["id"] == req["id"] for r in after.json()["wafa_requests"])


def test_a_manager_sees_only_his_own_teams_pending_requests(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed_manager():
        c = client.app.state.container
        mgr = Affiliate(id="mgr-w1", person_id="p-mgr-w1", phone="+966502230001",
                        name="مدير", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, mgr.id, mgr.to_dict())

    asyncio.run(seed_manager())
    mine = _seed_eligible_promoter(client, manager_id="mgr-w1")
    other = _seed_eligible_promoter(client)   # no manager — must not show up in mgr-w1's queue

    mine_headers = {"Authorization": f"Bearer {_token(sub=mine.replace('aff-w', 'p-w'))}"}
    other_headers = {"Authorization": f"Bearer {_token(sub=other.replace('aff-w', 'p-w'))}"}
    my_req = client.post("/api/v1/affiliates/me/wafa-requests", headers=mine_headers).json()
    client.post("/api/v1/affiliates/me/wafa-requests", headers=other_headers)

    mgr_headers = {"Authorization": f"Bearer {_token(sub='p-mgr-w1')}"}
    queue = client.get("/api/v1/affiliates/me/team/wafa-requests", headers=mgr_headers)
    assert queue.status_code == 200, queue.text
    ids = {r["id"] for r in queue.json()["wafa_requests"]}
    assert my_req["id"] in ids
    assert len(ids) == 1   # the other promoter's request is NOT his to see


def test_a_manager_cannot_decide_a_request_outside_his_own_team(client):
    other = _seed_eligible_promoter(client)
    other_headers = {"Authorization": f"Bearer {_token(sub=other.replace('aff-w', 'p-w'))}"}
    req = client.post("/api/v1/affiliates/me/wafa-requests", headers=other_headers).json()

    mgr_headers = {"Authorization": f"Bearer {_token(sub='p-mgr-w1')}"}   # from the previous test's seed
    r = client.post(f"/api/v1/affiliates/me/team/wafa-requests/{req['id']}/decision",
                    json={"decision": "approve"}, headers=mgr_headers)
    assert r.status_code == 404


def test_manager_decision_is_advisory_admin_still_binds(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed_manager():
        c = client.app.state.container
        mgr = Affiliate(id="mgr-w2", person_id="p-mgr-w2", phone="+966502230002",
                        name="مدير ثانٍ", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, mgr.id, mgr.to_dict())

    asyncio.run(seed_manager())
    mine = _seed_eligible_promoter(client, manager_id="mgr-w2")
    promoter_headers = {"Authorization": f"Bearer {_token(sub=mine.replace('aff-w', 'p-w'))}"}
    req = client.post("/api/v1/affiliates/me/wafa-requests", headers=promoter_headers).json()

    mgr_headers = {"Authorization": f"Bearer {_token(sub='p-mgr-w2')}"}
    decision = client.post(f"/api/v1/affiliates/me/team/wafa-requests/{req['id']}/decision",
                           json={"decision": "reject", "reason": "لا يخدم عملاءه"},
                           headers=mgr_headers)
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "requested"   # STILL pending — advisory only

    granted = client.post(f"/api/v1/admin/wafa-requests/{req['id']}/decision",
                          json={"decision": "approve"}, headers=FINANCE)
    assert granted.json()["status"] == "granted"
    assert granted.json()["manager_decision"] == "reject"   # documented, not overwritten
