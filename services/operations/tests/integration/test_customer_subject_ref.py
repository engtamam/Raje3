"""`/internal/operations/customers/subject-ref` — the pseudonym every peer already needs, for a
peer (bookings) that holds only `customer_id`. NOT `/recipient`'s sibling — see the route's own
docstring for why this one is far less sensitive.
"""
from __future__ import annotations

import asyncio

import pytest

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/customers/subject-ref"
TENANT = "tnt_subject_ref"


def _seed(client):
    from app.core.models import Customer
    from app.core.stores import CustomerStore

    cust = Customer(id="cus_sr1", tenant=TENANT, phone="966500000002", name="عميلة",
                    subject_ref="sub_" + "c" * 24, created=1786860000)
    asyncio.run(CustomerStore(client.app.state.container.datastore).save(cust))
    return cust


def test_a_known_customer_returns_its_subject_ref(client):
    cust = _seed(client)
    r = client.post(PATH, json={"tenant": TENANT, "customer_id": cust.id}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["subject_ref"] == cust.subject_ref


def test_an_unknown_customer_returns_empty_not_404(client):
    r = client.post(PATH, json={"tenant": TENANT, "customer_id": "cus_missing"}, headers=INTERNAL)
    assert r.status_code == 200
    assert r.json()["subject_ref"] == ""


def test_no_token_is_refused(client):
    r = client.post(PATH, json={"tenant": TENANT, "customer_id": "x"})
    assert r.status_code == 401
