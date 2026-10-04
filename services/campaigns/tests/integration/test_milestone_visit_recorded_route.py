"""`/internal/campaigns/milestone/visit-recorded` — the one hook operations' own `record_visit`
(the single point-of-sale every channel goes through) calls once per real visit, fanning out to
every active `community_milestone` campaign it matches.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from tests.conftest import INTERNAL_TOKEN


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN})
    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    app = create_app()
    tc = TestClient(app, raise_server_exceptions=False)
    tc.container = app.state.container
    yield tc
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _seed_campaign(client, *, tenant="t1", campaign_id="cmp_1", threshold=2,
                   service_id="", scope_service_ids=None, package_id="", state="active"):
    row = {"id": campaign_id, "tenant": tenant, "goal": "community_milestone", "state": state,
          "milestone_threshold": threshold, "service_id": service_id,
          "scope_service_ids": list(scope_service_ids or []), "package_id": package_id,
          "created": 1}
    run(client.container.datastore.put("campaigns", f"{tenant}|{campaign_id}", row))
    return row


def _post(client, **body):
    payload = {"tenant": "t1", "subject_ref": "cust_1", "service_ids": [], "package_id": "",
              "occurred_at": 0}
    payload.update(body)
    return client.post("/internal/campaigns/milestone/visit-recorded",
                       headers={"X-Internal-Token": INTERNAL_TOKEN}, json=payload)


def test_requires_the_internal_token(client):
    r = client.post("/internal/campaigns/milestone/visit-recorded",
                    json={"tenant": "t1", "subject_ref": "c1"})
    assert r.status_code == 401


def test_an_unscoped_campaign_counts_any_visit(client):
    _seed_campaign(client, threshold=5)
    r = _post(client)
    assert r.status_code == 200, r.text
    assert r.json() == {"contributed": 1, "fired": 0}


def test_a_scoped_campaign_ignores_a_visit_for_a_different_service(client):
    _seed_campaign(client, threshold=5, service_id="svc_wash")
    r = _post(client, service_ids=["svc_oil"])
    assert r.json() == {"contributed": 0, "fired": 0}


def test_a_scoped_campaign_counts_a_matching_service(client):
    _seed_campaign(client, threshold=5, service_id="svc_wash")
    r = _post(client, service_ids=["svc_wash"])
    assert r.json() == {"contributed": 1, "fired": 0}


def test_crossing_the_threshold_is_reported_as_fired(client):
    _seed_campaign(client, threshold=1)
    r = _post(client, subject_ref="cust_1")
    assert r.json() == {"contributed": 1, "fired": 1}


def test_one_visit_can_contribute_to_several_campaigns_at_once(client):
    _seed_campaign(client, campaign_id="cmp_1", threshold=10)
    _seed_campaign(client, campaign_id="cmp_2", threshold=10, service_id="svc_wash")
    r = _post(client, service_ids=["svc_wash"])
    assert r.json() == {"contributed": 2, "fired": 0}


def test_a_paused_campaign_is_never_counted(client):
    _seed_campaign(client, threshold=5, state="paused")
    r = _post(client)
    assert r.json() == {"contributed": 0, "fired": 0}


def test_another_tenants_campaign_is_never_counted(client):
    _seed_campaign(client, tenant="t2", threshold=5)
    r = _post(client, tenant="t1")
    assert r.json() == {"contributed": 0, "fired": 0}


def test_an_empty_subject_ref_never_crashes_the_route(client):
    _seed_campaign(client, threshold=5)
    r = _post(client, subject_ref="")
    assert r.status_code == 200
    assert r.json() == {"contributed": 0, "fired": 0}
