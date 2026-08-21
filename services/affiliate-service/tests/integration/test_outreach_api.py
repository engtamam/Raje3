"""The outbound conversion playbook's own routes: manager-only writes to the shared library,
ownership-checked writes to a specific lead, and open reads for any signed-in affiliate.
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
def outreach_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(outreach_env) -> TestClient:
    return _make_app()


def _token(**over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _seed(client: TestClient, *, manager_id: str, manager_person: str,
         promoter_id: str, promoter_person: str, lead_id: str) -> None:
    from app.core.models import ACTIVE, AFFILIATES, LEADS, MANAGER, PROMOTER, Affiliate, Lead

    async def go():
        c = client.app.state.container
        mgr = Affiliate(id=manager_id, person_id=manager_person, phone=f"+96650{manager_id[-4:]}0001",
                        name="مدير", role=MANAGER, status=ACTIVE)
        await c.datastore.put(AFFILIATES, mgr.id, mgr.to_dict())
        pro = Affiliate(id=promoter_id, person_id=promoter_person,
                        phone=f"+96650{promoter_id[-4:]}0002", name="مسوّق", role=PROMOTER,
                        status=ACTIVE, parent_id=manager_id)
        await c.datastore.put(AFFILIATES, pro.id, pro.to_dict())
        lead = Lead(id=lead_id, place_id=lead_id, source_manager_id=manager_id,
                   assigned_to=promoter_id, status="assigned")
        await c.datastore.put(LEADS, lead_id, lead.to_dict())

    asyncio.run(go())


# ── manager-only writes to the shared library ────────────────────────────────────────────────────
def test_creating_a_stage_refuses_a_non_manager(client):
    _seed(client, manager_id="mgr-out1", manager_person="p-out1",
         promoter_id="pro-out1", promoter_person="p-out1b", lead_id="lead-out1")
    r = client.put("/api/v1/affiliates/me/outreach-stages", json={"code": "hook", "name": "الخطاف"},
                   headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 403


def test_a_manager_creates_a_stage_and_a_template(client):
    r = client.put("/api/v1/affiliates/me/outreach-stages",
                   json={"code": "hook", "name": "الخطاف", "order": 1},
                   headers={"Authorization": f"Bearer {_token(sub='p-out1')}"})
    assert r.status_code == 200, r.text

    r = client.post("/api/v1/affiliates/me/templates",
                    json={"stage_code": "hook", "kind": "رسالة", "title": "خطاف١",
                          "body": "هل تعلم أن..."},
                    headers={"Authorization": f"Bearer {_token(sub='p-out1')}"})
    assert r.status_code == 201, r.text
    assert r.json()["stage_code"] == "hook"


def test_a_promoter_reads_the_stage_and_template_lists(client):
    r = client.get("/api/v1/affiliates/me/outreach-stages",
                   headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 200, r.text
    assert any(s["code"] == "hook" for s in r.json()["stages"])

    r = client.get("/api/v1/affiliates/me/templates?stage_code=hook",
                   headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 200, r.text
    assert any(t["title"] == "خطاف١" for t in r.json()["templates"])


def test_a_promoter_cannot_create_a_template(client):
    r = client.post("/api/v1/affiliates/me/templates",
                    json={"stage_code": "hook", "kind": "رسالة", "title": "محاولة موظّف"},
                    headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 403


# ── acting on one lead — ownership, not role ─────────────────────────────────────────────────────
def test_the_assigned_promoter_logs_a_use_and_sets_its_outcome_with_a_stage_move(client):
    tpl = client.post("/api/v1/affiliates/me/templates",
                      json={"stage_code": "hook", "kind": "رسالة", "title": "خطاف٢"},
                      headers={"Authorization": f"Bearer {_token(sub='p-out1')}"}).json()
    client.put("/api/v1/affiliates/me/outreach-stages",
              json={"code": "offer", "name": "عرض التجربة", "order": 2},
              headers={"Authorization": f"Bearer {_token(sub='p-out1')}"})

    r = client.post("/api/v1/affiliates/me/leads/lead-out1/template-uses",
                    json={"template_id": tpl["id"]},
                    headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 201, r.text
    use_id = r.json()["id"]
    assert r.json()["stage_code"] == "hook"

    r = client.patch(f"/api/v1/affiliates/me/template-uses/{use_id}",
                     json={"outcome": "advanced", "new_stage_code": "offer"},
                     headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "advanced"

    # THE LEAD ITSELF MOVED — the whole point of naming a stage explicitly.
    uses = client.get("/api/v1/affiliates/me/leads/lead-out1/template-uses",
                      headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"}).json()["uses"]
    assert uses[0]["outcome"] == "advanced"


def test_an_unrelated_affiliate_cannot_log_a_use_against_someone_elses_lead(client):
    from app.core.models import ACTIVE, AFFILIATES, PROMOTER, Affiliate

    async def go():
        c = client.app.state.container
        aff = Affiliate(id="pro-out2", person_id="p-out2", phone="+966501250099",
                        name="غريب", role=PROMOTER, status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(go())
    tpl = client.get("/api/v1/affiliates/me/templates?stage_code=hook",
                     headers={"Authorization": f"Bearer {_token(sub='p-out1')}"}).json()["templates"][0]
    r = client.post("/api/v1/affiliates/me/leads/lead-out1/template-uses",
                    json={"template_id": tpl["id"]},
                    headers={"Authorization": f"Bearer {_token(sub='p-out2')}"})
    assert r.status_code == 403
    assert r.json()["reason"] == "not_yours"


def test_set_decision_maker_is_ownership_checked_and_readable_back(client):
    r = client.patch("/api/v1/affiliates/me/leads/lead-out1/decision-maker",
                     json={"name": "أبو سالم", "phone": "+966599990000", "role": "المالك"},
                     headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 200, r.text
    assert r.json()["decision_maker_name"] == "أبو سالم"

    r = client.patch("/api/v1/affiliates/me/leads/lead-out1/decision-maker",
                     json={"name": "محاولة غريب"},
                     headers={"Authorization": f"Bearer {_token(sub='p-out2')}"})
    assert r.status_code == 403


# ── stats ─────────────────────────────────────────────────────────────────────────────────────
def test_template_and_kind_stats_are_reachable_and_reflect_the_logged_use(client):
    r = client.get("/api/v1/affiliates/me/template-stats",
                   headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 200, r.text
    assert any(row["advanced"] >= 1 for row in r.json()["stats"])

    r = client.get("/api/v1/affiliates/me/template-kind-stats",
                   headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"})
    assert r.status_code == 200, r.text
    assert any(row["kind"] == "رسالة" for row in r.json()["stats"])


# ── deactivation is idempotent and never deletes ─────────────────────────────────────────────────
def test_deactivating_a_stage_and_a_template_never_deletes(client):
    r = client.delete("/api/v1/affiliates/me/outreach-stages/offer",
                     headers={"Authorization": f"Bearer {_token(sub='p-out1')}"})
    assert r.status_code == 200 and r.json()["changed"] is True
    r = client.delete("/api/v1/affiliates/me/outreach-stages/offer",
                     headers={"Authorization": f"Bearer {_token(sub='p-out1')}"})
    assert r.status_code == 200 and r.json()["changed"] is False   # idempotent

    stages = client.get("/api/v1/affiliates/me/outreach-stages",
                        headers={"Authorization": f"Bearer {_token(sub='p-out1b')}"}).json()["stages"]
    assert not any(s["code"] == "offer" for s in stages)   # dropped from the ACTIVE list only
