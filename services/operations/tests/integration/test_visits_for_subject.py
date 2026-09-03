"""`/internal/operations/visits-for-subject` — the FULL visit record, for the internal-only
case-timeline investigation tool (ops-mcp). Same safe identity resolution as `customer-visits`
(subject_ref -> CustomerStore.by_refs, never a phone, never a create), but unlike that route
(deliberately shaped for a public/portal-facing page) this one returns every field — operator,
note, amount — since it is reachable only over the internal token, never a public link.
"""
from __future__ import annotations

import asyncio
import os

import pytest

INTERNAL_TOKEN = "t" * 40


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss",
        "TOKEN_AUDIENCE": "aud",
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _h() -> dict:
    return {"X-Internal-Token": INTERNAL_TOKEN}


def _seed(client, *, tenant: str, customer_id: str, subject_ref: str, visits: list) -> None:
    from app.core.models import Customer, Visit
    from app.core.stores import CustomerStore, VisitStore

    store = client.app.state.container.datastore

    async def run():
        await CustomerStore(store).save(Customer(id=customer_id, tenant=tenant,
                                                 phone="+9665" + customer_id[-8:],
                                                 subject_ref=subject_ref, created=1))
        vs = VisitStore(store)
        for v in visits:
            await vs.save(v)

    asyncio.run(run())


def test_refuses_without_the_internal_token(client):
    r = client.post("/internal/operations/visits-for-subject",
                    json={"tenant": "t1", "subject_ref": "sub_1"})
    assert r.status_code == 401


def test_returns_the_full_record_not_the_display_shaped_one(client):
    """UNLIKE customer-visits (operator/note/amount deliberately omitted), this route is
    internal-only and must carry the full evidence a case investigation needs."""
    from app.core.models import Visit

    _seed(client, tenant="tnt_full", customer_id="cus_full", subject_ref="sub_full", visits=[
        Visit(id="vis_full_1", tenant="tnt_full", customer_id="cus_full", operator_id="op_9",
             note="عميل طلب خصم إضافي", total_minor=15000, created=100, occurred_at=100),
    ])
    r = client.post("/internal/operations/visits-for-subject",
                    json={"tenant": "tnt_full", "subject_ref": "sub_full"}, headers=_h())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1
    v = body["visits"][0]
    assert v["operator_id"] == "op_9"
    assert v["note"] == "عميل طلب خصم إضافي"
    assert v["total_minor"] == 15000


def test_returns_only_that_subjects_own_visits_even_in_a_busy_shop(client):
    """SAME bug class customer-visits was fixed for (the shop's last 200 filtered down to him,
    silently returning nothing for a busy shop's month-old customer) — proven again here since
    this is a SEPARATE route reading the same store."""
    from app.core.models import Visit

    _seed(client, tenant="tnt_busy2", customer_id="cus_mine2", subject_ref="sub_mine2", visits=[
        Visit(id="vis_mine2", tenant="tnt_busy2", customer_id="cus_mine2",
             service_ids=["srv_1"], created=1, occurred_at=1),
        *[Visit(id=f"vis_o2_{i}", tenant="tnt_busy2", customer_id="cus_other2",
               service_ids=["srv_1"], created=100 + i, occurred_at=100 + i) for i in range(250)],
    ])
    r = client.post("/internal/operations/visits-for-subject",
                    json={"tenant": "tnt_busy2", "subject_ref": "sub_mine2", "limit": 10},
                    headers=_h())
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1
    assert r.json()["visits"][0]["id"] == "vis_mine2"


def test_returns_empty_never_404_for_an_unknown_subject(client):
    r = client.post("/internal/operations/visits-for-subject",
                    json={"tenant": "t1", "subject_ref": "sub_never_existed"}, headers=_h())
    assert r.status_code == 200
    assert r.json() == {"visits": [], "count": 0}


def test_sorted_newest_first(client):
    from app.core.models import Visit

    _seed(client, tenant="tnt_sort", customer_id="cus_sort", subject_ref="sub_sort", visits=[
        Visit(id="vis_old", tenant="tnt_sort", customer_id="cus_sort", created=100, occurred_at=100),
        Visit(id="vis_new", tenant="tnt_sort", customer_id="cus_sort", created=300, occurred_at=300),
        Visit(id="vis_mid", tenant="tnt_sort", customer_id="cus_sort", created=200, occurred_at=200),
    ])
    r = client.post("/internal/operations/visits-for-subject",
                    json={"tenant": "tnt_sort", "subject_ref": "sub_sort"}, headers=_h())
    ids = [v["id"] for v in r.json()["visits"]]
    assert ids == ["vis_new", "vis_mid", "vis_old"]


def test_isolated_per_tenant(client):
    from app.core.models import Visit

    _seed(client, tenant="tnt_iso_a", customer_id="cus_iso", subject_ref="sub_iso_shared", visits=[
        Visit(id="vis_iso_a", tenant="tnt_iso_a", customer_id="cus_iso", created=1, occurred_at=1)])
    _seed(client, tenant="tnt_iso_b", customer_id="cus_iso", subject_ref="sub_iso_shared", visits=[
        Visit(id="vis_iso_b", tenant="tnt_iso_b", customer_id="cus_iso", created=1, occurred_at=1)])
    r = client.post("/internal/operations/visits-for-subject",
                    json={"tenant": "tnt_iso_a", "subject_ref": "sub_iso_shared"}, headers=_h())
    assert r.json()["count"] == 1
    assert r.json()["visits"][0]["id"] == "vis_iso_a"


def test_refuses_a_malformed_body_rather_than_500ing(client):
    r = client.post("/internal/operations/visits-for-subject", json={"tenant": "t1"}, headers=_h())
    assert r.status_code == 422   # subject_ref missing
