"""WhatsApp Direct Ordering, Step 4 — `/internal/operations/whatsapp-orders`: resolves the
nearest branch from the customer's real coordinates, then creates a real orders.py Order. See
whatsapp-catalog-ordering-execution-plan.md's own Step 4."""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

INTERNAL_TOKEN = "t" * 40
TENANT = "tnt_wa_orders"
RIYADH = (24.7136, 46.6753)
NEAR_RIYADH = (24.72, 46.68)
JEDDAH = (21.4858, 39.1925)


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss", "TOKEN_AUDIENCE": "aud", "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def client():
    saved = dict(os.environ)
    c = _make_app()
    yield c
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _seed_branch(client, *, branch_id="br1", lat=RIYADH[0], lng=RIYADH[1],
                 delivery_radius_km=10, active=True) -> str:
    from app.core.models import Branch
    from app.core.stores import BranchStore

    asyncio.run(BranchStore(client.app.state.container.datastore).save(
        Branch(id=branch_id, tenant=TENANT, name="الفرع الرئيسي", lat=lat, lng=lng,
              delivery_radius_km=delivery_radius_km, active=active)))
    return branch_id


def _seed_service(client, *, service_id="svc1", price_minor=5000, active=True) -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id=service_id, tenant=TENANT, name="غسيل خارجي", price_minor=price_minor,
               active=active)))
    return service_id


def _post(client, *, lat, lng, items, idempotency_key="wamid_1", phone="0501234567"):
    return client.post("/internal/operations/whatsapp-orders",
                       headers={"X-Internal-Token": INTERNAL_TOKEN},
                       json={"tenant": TENANT, "phone": phone, "customer_name": "أحمد",
                            "items": items, "lat": lat, "lng": lng,
                            "idempotency_key": idempotency_key})


def test_requires_the_internal_token(client):
    r = client.post("/internal/operations/whatsapp-orders",
                    json={"tenant": TENANT, "phone": "0501234567",
                         "items": [{"service_id": "x", "quantity": 1}],
                         "lat": 24.7, "lng": 46.6, "idempotency_key": "w1"})
    assert r.status_code in (401, 403)


def test_a_covered_point_creates_a_real_order(client):
    _seed_branch(client)
    sid = _seed_service(client)
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": sid, "quantity": 2}])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    assert body["order_id"].startswith("ord_")
    assert body["branch_id"] == "br1"
    assert body["total_minor"] == 10000


def test_a_point_outside_every_branchs_radius_is_refused_clearly(client):
    _seed_branch(client, lat=JEDDAH[0], lng=JEDDAH[1], delivery_radius_km=5)
    sid = _seed_service(client)
    r = _post(client, lat=RIYADH[0], lng=RIYADH[1], items=[{"service_id": sid, "quantity": 1}])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is False
    assert "نطاق" in body["reason"]


def test_an_unpriced_service_is_refused_not_charged_zero(client):
    _seed_branch(client)
    sid = _seed_service(client, price_minor=0)
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": sid, "quantity": 1}])
    assert r.status_code == 200, r.text
    assert r.json()["created"] is False


def test_an_unknown_service_id_is_refused(client):
    _seed_branch(client)
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": "no_such_service", "quantity": 1}])
    assert r.status_code == 200, r.text
    assert r.json()["created"] is False


def test_the_same_idempotency_key_twice_returns_the_same_order_not_two(client):
    _seed_branch(client)
    sid = _seed_service(client)
    r1 = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
              items=[{"service_id": sid, "quantity": 1}], idempotency_key="wamid_dup")
    r2 = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
              items=[{"service_id": sid, "quantity": 1}], idempotency_key="wamid_dup")
    assert r1.json()["created"] is True
    assert r2.json()["created"] is True
    assert r1.json()["order_id"] == r2.json()["order_id"]


def test_an_inactive_branch_is_never_matched_even_if_it_covers_the_point(client):
    _seed_branch(client, active=False)
    sid = _seed_service(client)
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": sid, "quantity": 1}])
    assert r.json()["created"] is False


def test_the_nearer_of_two_covering_branches_is_chosen(client):
    _seed_branch(client, branch_id="far", lat=RIYADH[0], lng=RIYADH[1], delivery_radius_km=100)
    _seed_branch(client, branch_id="near", lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
                delivery_radius_km=100)
    sid = _seed_service(client)
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": sid, "quantity": 1}])
    assert r.json()["branch_id"] == "near"
