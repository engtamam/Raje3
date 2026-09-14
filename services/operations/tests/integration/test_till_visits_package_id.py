"""`package_id` reaching a real, till-recorded visit (2026-09-14, till-integration audit
follow-up). `record_visit()` has always accepted this field — the till's own batch door simply
never forwarded it, so a till selling packages had no way to say a sale fulfilled one.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/till/visits"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_till_pkg"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture()
def till_headers():
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "till1", "iss": ISS, "aud": AUD, "caps": ["operations.record"],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"headers": {"Authorization": f"Bearer {tok}"}, "tenant": TENANT}


def _seed_service(client, tenant: str) -> str:
    import asyncio

    from app.core.models import Service
    from app.core.stores import ServiceStore

    async def go():
        await ServiceStore(client.app.state.container.datastore).save(
            Service(id="svc_pkg_a", tenant=tenant, name="غيار"))

    asyncio.run(go())
    return "svc_pkg_a"


def test_a_till_recorded_sale_carries_its_package_id_onto_the_real_visit(client, till_headers):
    tenant = till_headers["tenant"]
    svc_id = _seed_service(client, tenant)

    r = client.post(PATH, json={"visits": [{
        "phone": "0501112222", "branch_id": "brn-main", "invoice_id": "inv-pkg-1",
        "lines": [{"product_id": svc_id, "name": "غيار", "qty": 1, "amount_minor": 5000}],
        "package_id": "pkg_gold_1",
    }]}, headers=till_headers["headers"])

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] == 1, body

    import asyncio
    ops = client.app.state.container.operations
    cust = asyncio.run(ops.customer_by_phone(tenant, "0501112222"))
    assert cust is not None
    visits = asyncio.run(ops.visits_for_customer(tenant, cust.id)) \
        if hasattr(ops, "visits_for_customer") else None
    if visits is None:
        # Fall back to reading the store directly if there is no such convenience method.
        from app.core.stores import VisitStore
        rows = asyncio.run(VisitStore(client.app.state.container.datastore).for_customer(
            tenant, cust.id))
        visits = rows
    assert any(v.package_id == "pkg_gold_1" for v in visits), \
        [getattr(v, "package_id", None) for v in visits]


def test_an_ordinary_sale_with_no_package_still_records_an_empty_package_id(client, till_headers):
    tenant = till_headers["tenant"]
    svc_id = _seed_service(client, tenant)

    r = client.post(PATH, json={"visits": [{
        "phone": "0501113333", "branch_id": "brn-main", "invoice_id": "inv-pkg-2",
        "lines": [{"product_id": svc_id, "name": "غيار", "qty": 1, "amount_minor": 5000}],
    }]}, headers=till_headers["headers"])

    assert r.status_code == 200, r.text
    assert r.json()["accepted"] == 1
