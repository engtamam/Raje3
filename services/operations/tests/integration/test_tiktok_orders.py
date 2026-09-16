"""`/api/v1/tiktok/orders` — Phase 1 of the TikTok app plan (see
[[task-tiktok-app-phases]] memory). Same machine-credential shape as `till.py`'s own tests
(`test_till_visits_package_id.py`), with the two behaviours specific to this door: a masked or
missing phone lands on the tenant's anonymous placeholder rather than being refused, and a real
one records an ordinary, named customer exactly like any other visit source.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/tiktok/orders"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_tiktok_p1"


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


def _seed_catchall(client, tenant: str) -> None:
    """Every real tenant gets a "خدمة أخرى" row at signup (`ensure_main`'s own catalogue
    counterpart) — a fresh test tenant does not go through that provisioning, so tests that rely
    on the catch-all (a name-only TikTok line, or no lines at all) seed it exactly as production
    already has it, rather than the route inventing one at request time."""
    import asyncio

    from app.core.models import Service
    from app.core.stores import ServiceStore

    async def go():
        await ServiceStore(client.app.state.container.datastore).save(
            Service(id="svc_catchall", tenant=tenant, name="خدمة أخرى", catchall=True))

    asyncio.run(go())


@pytest.fixture()
def tiktok_headers():
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "tiktok1", "iss": ISS, "aud": AUD, "caps": ["operations.record"],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"headers": {"Authorization": f"Bearer {tok}"}, "tenant": TENANT}


def test_a_real_phone_records_an_ordinary_named_customer(client, tiktok_headers):
    _seed_catchall(client, tiktok_headers['tenant'])
    r = client.post(PATH, json={
        "order_id": "tt-order-1", "phone": "0501234567", "name": "سارة",
        "branch_id": "brn-main",
        "lines": [{"name": "غسيل خارجي", "qty": 2, "amount_minor": 3000}],
    }, headers=tiktok_headers["headers"])

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is True, body
    assert body["anonymous"] is False

    import asyncio
    ops = client.app.state.container.operations
    cust = asyncio.run(ops.customer_by_phone(tiktok_headers["tenant"], "0501234567"))
    assert cust is not None and cust.name == "سارة"


def test_tiktoks_own_masked_phone_lands_on_the_anonymous_placeholder(client, tiktok_headers):
    _seed_catchall(client, tiktok_headers['tenant'])
    r = client.post(PATH, json={
        "order_id": "tt-order-2", "phone": "1**-***-**23", "branch_id": "brn-main",
        "lines": [{"name": "تلميع", "qty": 1, "amount_minor": 5000}],
    }, headers=tiktok_headers["headers"])

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is True, body
    assert body["anonymous"] is True

    import asyncio
    from app.core.stores import CustomerStore

    anon = asyncio.run(CustomerStore(client.app.state.container.datastore)
                       .anonymous(tiktok_headers["tenant"]))
    assert anon is not None


def test_a_missing_phone_also_lands_on_the_anonymous_placeholder(client, tiktok_headers):
    _seed_catchall(client, tiktok_headers['tenant'])
    r = client.post(PATH, json={
        "order_id": "tt-order-3", "branch_id": "brn-main",
        "lines": [{"name": "تلميع", "qty": 1, "amount_minor": 5000}],
    }, headers=tiktok_headers["headers"])

    assert r.status_code == 200, r.text
    assert r.json()["anonymous"] is True


def test_the_same_order_id_twice_is_a_duplicate_not_a_second_visit(client, tiktok_headers):
    _seed_catchall(client, tiktok_headers['tenant'])
    payload = {
        "order_id": "tt-order-dup", "phone": "0501119999", "branch_id": "brn-main",
        "lines": [{"name": "غسيل داخلي", "qty": 1, "amount_minor": 2000}],
    }
    first = client.post(PATH, json=payload, headers=tiktok_headers["headers"])
    second = client.post(PATH, json=payload, headers=tiktok_headers["headers"])

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert first.json()["visit_id"] == second.json()["visit_id"]


def test_an_unknown_branch_is_refused_by_name(client, tiktok_headers):
    _seed_catchall(client, tiktok_headers['tenant'])
    r = client.post(PATH, json={
        "order_id": "tt-order-4", "phone": "0501118888", "branch_id": "brn-does-not-exist",
        "lines": [{"name": "غسيل خارجي", "qty": 1, "amount_minor": 3000}],
    }, headers=tiktok_headers["headers"])

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is False
    assert body["reason"] == "UNKNOWN_BRANCH"


def _watch_seams(client) -> list:
    """Same recorder `test_free_visit_earns_nothing.py` uses — what the seams DO (earning,
    reminders, search) belongs to those consumers; what is at stake here is only whether a real
    TikTok order rings them at all."""
    seen: list = []

    async def after_visit(result):
        seen.append(result)

    client.app.state.container.seams.after_visit = after_visit
    return seen


def test_a_real_phone_order_runs_the_seams(client, tiktok_headers):
    """FOUND 2026-09-16: this route recorded a real visit and never once rang the seams — no
    points earned, no reminder cycle restarted, no search-index row refreshed for a single real,
    paid TikTok order. Every other visit-recording door in this service already does this."""
    _seed_catchall(client, tiktok_headers["tenant"])
    seen = _watch_seams(client)

    r = client.post(PATH, json={
        "order_id": "tt-order-seam-1", "phone": "0501234567", "branch_id": "brn-main",
        "lines": [{"name": "غسيل خارجي", "qty": 1, "amount_minor": 3000}],
    }, headers=tiktok_headers["headers"])

    assert r.status_code == 200, r.text
    assert len(seen) == 1
    assert seen[0].visit.id == r.json()["visit_id"]


def test_an_anonymous_order_never_rings_the_seams(client, tiktok_headers):
    """The tenant's ONE shared anonymous placeholder must never receive a reminder or a rating
    request meant for a single buyer, and earning points nobody can ever spend is nonsense — see
    Customer.anonymous's own docstring."""
    _seed_catchall(client, tiktok_headers["tenant"])
    seen = _watch_seams(client)

    r = client.post(PATH, json={
        "order_id": "tt-order-seam-2", "branch_id": "brn-main",
        "lines": [{"name": "غسيل خارجي", "qty": 1, "amount_minor": 3000}],
    }, headers=tiktok_headers["headers"])

    assert r.status_code == 200, r.text
    assert r.json()["anonymous"] is True
    assert seen == []


def test_a_repeated_order_id_rings_the_seams_only_once(client, tiktok_headers):
    _seed_catchall(client, tiktok_headers["tenant"])
    seen = _watch_seams(client)
    payload = {
        "order_id": "tt-order-seam-3", "phone": "0501119999", "branch_id": "brn-main",
        "lines": [{"name": "غسيل داخلي", "qty": 1, "amount_minor": 2000}],
    }

    first = client.post(PATH, json=payload, headers=tiktok_headers["headers"])
    again = client.post(PATH, json=payload, headers=tiktok_headers["headers"])

    assert first.status_code == 200 and again.status_code == 200
    assert again.json()["duplicate"] is True
    assert len(seen) == 1


def test_no_capability_is_refused(client):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "nope", "iss": ISS, "aud": AUD, "caps": [],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    r = client.post(PATH, json={
        "order_id": "tt-order-5", "phone": "0501110000", "branch_id": "brn-main", "lines": [],
    }, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
