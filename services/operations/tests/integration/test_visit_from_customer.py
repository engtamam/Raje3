"""`/internal/operations/visits/from-customer` — bookings' booking->visit gateway (§4).

Resolves by `customer_id`, hands off to the SAME `record_visit()` every other path uses — this
file proves the hand-off, not `record_visit()`'s own rules (covered by its own tests).
"""
from __future__ import annotations

import asyncio

import pytest

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/visits/from-customer"
TENANT = "tnt_from_customer"


def _seed(client):
    from app.core.models import Customer, Service
    from app.core.stores import CustomerStore, ServiceStore

    cust = Customer(id="cus_fc1", tenant=TENANT, phone="966500000001", name="عميلة",
                    subject_ref="sub_" + "b" * 24, created=1786860000)
    svc = Service(id="svc_fc1", tenant=TENANT, name="حلاقة", duration_minutes=30, active=True)
    c = client.app.state.container
    asyncio.run(CustomerStore(c.datastore).save(cust))
    asyncio.run(ServiceStore(c.datastore).save(svc))
    return cust.id, svc.id


def test_a_known_customer_gets_a_real_visit(client):
    cust_id, svc_id = _seed(client)
    r = client.post(PATH, json={"tenant": TENANT, "customer_id": cust_id,
                                "service_ids": [svc_id], "idempotency_key": "bkg_1"},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["customer_id"] == cust_id
    assert body["duplicate"] is False


def test_a_retried_attendance_returns_the_same_visit_not_a_second_one(client):
    cust_id, svc_id = _seed(client)
    first = client.post(PATH, json={"tenant": TENANT, "customer_id": cust_id,
                                    "service_ids": [svc_id], "idempotency_key": "bkg_retry"},
                        headers=INTERNAL).json()
    second = client.post(PATH, json={"tenant": TENANT, "customer_id": cust_id,
                                     "service_ids": [svc_id], "idempotency_key": "bkg_retry"},
                         headers=INTERNAL).json()
    assert first["visit_id"] == second["visit_id"]
    assert second["duplicate"] is True


def test_a_customer_that_does_not_exist_is_refused_not_500(client):
    r = client.post(PATH, json={"tenant": TENANT, "customer_id": "cus_missing",
                                "service_ids": ["svc_x"], "idempotency_key": "bkg_2"},
                    headers=INTERNAL)
    assert r.status_code == 404


def test_no_token_is_refused(client):
    r = client.post(PATH, json={"tenant": TENANT, "customer_id": "x", "service_ids": ["y"],
                                "idempotency_key": "z"})
    assert r.status_code == 401
