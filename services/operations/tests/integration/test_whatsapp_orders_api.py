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


def test_a_created_order_with_no_payments_peer_reports_created_but_no_pay_url(client):
    """The owner's own rule: an order is never 'received' until it is paid. This test's
    environment wires no payments-service at all -- the order itself must still be created
    (idempotency intact for a retry) while `pay_url` stays empty and `pay_reason` carries a real
    sentence, never a silent/blank refusal."""
    _seed_branch(client)
    sid = _seed_service(client)
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": sid, "quantity": 1}])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    assert body["pay_url"] == ""
    assert body["pay_reason"]


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


# ── hardening: the HTTP boundary itself (bad tokens, out-of-range inputs, oversized payloads) ────

def test_an_empty_internal_token_is_rejected(client):
    r = client.post("/internal/operations/whatsapp-orders",
                    headers={"X-Internal-Token": ""},
                    json={"tenant": TENANT, "phone": "0501234567",
                         "items": [{"service_id": "x", "quantity": 1}],
                         "lat": 24.7, "lng": 46.6, "idempotency_key": "w1"})
    assert r.status_code in (401, 403)


def test_a_wrong_length_internal_token_is_rejected(client):
    r = client.post("/internal/operations/whatsapp-orders",
                    headers={"X-Internal-Token": "x" * 5},
                    json={"tenant": TENANT, "phone": "0501234567",
                         "items": [{"service_id": "x", "quantity": 1}],
                         "lat": 24.7, "lng": 46.6, "idempotency_key": "w1"})
    assert r.status_code in (401, 403)


def test_latitude_just_past_the_valid_range_is_refused_422(client):
    r = _post(client, lat=90.0001, lng=46.6, items=[{"service_id": "x", "quantity": 1}])
    assert r.status_code == 422


def test_longitude_just_past_the_valid_range_is_refused_422(client):
    r = _post(client, lat=24.7, lng=-180.0001, items=[{"service_id": "x", "quantity": 1}])
    assert r.status_code == 422


def test_latitude_and_longitude_exactly_at_the_valid_boundary_are_accepted(client):
    _seed_branch(client, lat=90.0, lng=180.0, delivery_radius_km=100)
    sid = _seed_service(client)
    r = _post(client, lat=90.0, lng=180.0, items=[{"service_id": sid, "quantity": 1}])
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True


def test_an_oversized_item_list_is_refused_422(client):
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": f"s{i}", "quantity": 1} for i in range(41)])
    assert r.status_code == 422


def test_a_zero_quantity_item_is_refused_422(client):
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": "x", "quantity": 0}])
    assert r.status_code == 422


def test_a_branch_belonging_to_another_tenant_is_never_matched(client):
    """`nearest_branch_for_point` is handed only `BranchStore.list(body.tenant)` -- a branch seeded
    for a DIFFERENT tenant at the exact same coordinates must never be offered to this one."""
    from app.core.models import Branch
    from app.core.stores import BranchStore
    asyncio.run(BranchStore(client.app.state.container.datastore).save(
        Branch(id="other_tenants_branch", tenant="a_different_tenant",
              name="فرع تاجر آخر", lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
              delivery_radius_km=100, active=True)))
    sid = _seed_service(client)
    r = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
             items=[{"service_id": sid, "quantity": 1}])
    assert r.json()["created"] is False, "no branch of THIS tenant covers the point"


def test_replaying_the_same_idempotency_key_with_different_items_settles_on_the_original_order(client):
    """A webhook retry (or a tampered replay) of an already-claimed idempotency key must never
    reprice or recreate the order from the NEW body -- the first cart that actually claimed the key
    is the one that counts."""
    _seed_branch(client)
    sid1 = _seed_service(client, service_id="svc1", price_minor=5000)
    sid2 = _seed_service(client, service_id="svc2", price_minor=99900)
    r1 = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
              items=[{"service_id": sid1, "quantity": 1}], idempotency_key="wamid_replay")
    r2 = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
              items=[{"service_id": sid2, "quantity": 1}], idempotency_key="wamid_replay")
    assert r1.json()["order_id"] == r2.json()["order_id"]
    assert r2.json()["total_minor"] == 5000, "the replay must not have repriced to svc2's amount"


class _FakePaymentsDesk:
    """A real gateway connected -- the full lifecycle this test proves end-to-end, with the one
    external peer (payments-service) swapped for a deterministic double. Idempotent BY `reference`,
    same as the real service (whatsapp-ordering-app-gap-analysis.md's own note: "same reference ->
    same link, not a second one") -- `request_payment()` itself calls this on every invocation with
    no short-circuit of its own; the dedup is payments-service's job, never operations'."""

    def __init__(self):
        self.requests: list[dict] = []
        self._by_reference: dict[str, dict] = {}

    async def create_request(self, *, tenant, reference, amount_minor, metadata):
        self.requests.append({"tenant": tenant, "reference": reference,
                             "amount_minor": amount_minor, "metadata": metadata})
        if reference not in self._by_reference:
            self._by_reference[reference] = {
                "ok": True, "request_id": f"req_{reference}",
                "pay_url": f"https://pay.example/r/{reference}"}
        return self._by_reference[reference]


def test_end_to_end_full_order_lifecycle_through_the_real_http_door(client):
    """The complete real customer journey through ONE HTTP door: nearest-branch geo resolution,
    server-side pricing from the catalogue (never the caller's own numbers), a minted pay link from
    a connected gateway, and a webhook-retry of the exact same event settling on the identical
    order AND the identical pay link rather than minting a second one."""
    _seed_branch(client, delivery_radius_km=15)
    sid = _seed_service(client, price_minor=12000)
    client.app.state.container.orders._payments = _FakePaymentsDesk()

    r1 = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
              items=[{"service_id": sid, "quantity": 3}], idempotency_key="wamid_e2e")
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["created"] is True
    assert body1["branch_id"] == "br1"
    assert body1["total_minor"] == 36000
    assert body1["pay_url"] == f"https://pay.example/r/{body1['order_id']}"
    assert body1["pay_reason"] == ""

    # THE SAME EVENT, REDELIVERED (Meta's own at-least-once guarantee) -- settles on the IDENTICAL
    # order and the IDENTICAL pay link, never a second mint.
    r2 = _post(client, lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
              items=[{"service_id": sid, "quantity": 3}], idempotency_key="wamid_e2e")
    body2 = r2.json()
    assert body2["order_id"] == body1["order_id"]
    # SAME LINK ON REDELIVERY -- operations calls `create_request` again each time (no short-circuit
    # of its own: `request_payment()` has none), but the SAME reference (`Order.id`) must settle on
    # the SAME link regardless, via the gateway's own idempotency.
    assert body2["pay_url"] == body1["pay_url"]
    assert len(client.app.state.container.orders._payments.requests) == 2
    assert len({r["reference"] for r in client.app.state.container.orders._payments.requests}) == 1
