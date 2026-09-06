"""POST /internal/operations/ratings-summary — the weekly digest's rating line (rating-app-
feature.md phase 6). insights' HttpPeers.digest_extras calls this once per tenant per week."""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

PATH = "/internal/operations/ratings-summary"
TOKEN = "t" * 40
TENANT = "tnt_ratings_summary"


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss", "TOKEN_AUDIENCE": "aud", "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _internal() -> dict:
    return {"X-Internal-Token": TOKEN}


def _seed(client, *, visit_id: str, tenant: str = TENANT, rating: int, rated_at: int,
         rating_handled_at: int = 0) -> None:
    from app.core.models import Visit
    from app.core.stores import VisitStore

    v = Visit(id=visit_id, tenant=tenant, customer_id="cus_1", service_ids=["svc_1"],
              created=rated_at, occurred_at=rated_at, rating=rating, rated_at=rated_at,
              rating_handled_at=rating_handled_at)
    asyncio.run(VisitStore(client.app.state.container.datastore).save(v))


def test_no_token_is_refused(client):
    r = client.post(PATH, json={"tenant": TENANT, "since": 0})
    assert r.status_code == 401


def test_a_tenant_with_no_ratings_reads_zero(client):
    r = client.post(PATH, headers=_internal(), json={"tenant": TENANT, "since": 0})
    assert r.status_code == 200, r.text
    assert r.json() == {"count": 0, "average": 0.0, "unhandled": 0}


def test_counts_and_averages_this_weeks_ratings(client):
    _seed(client, visit_id="v1", rating=5, rated_at=1_000)
    _seed(client, visit_id="v2", rating=3, rated_at=1_001)
    _seed(client, visit_id="v_old", rating=1, rated_at=100)
    r = client.post(PATH, headers=_internal(), json={"tenant": TENANT, "since": 500})
    body = r.json()
    assert body["count"] == 2
    assert body["average"] == 4.0
    assert body["unhandled"] == 2


def test_one_tenants_summary_is_not_anothers(client):
    _seed(client, visit_id="v1", tenant="tnt_other", rating=5, rated_at=1_000)
    r = client.post(PATH, headers=_internal(), json={"tenant": TENANT, "since": 0})
    assert r.json()["count"] == 0
