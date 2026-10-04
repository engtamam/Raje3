"""WhatsApp Direct Ordering -- concurrency/race coverage for `OrderService.create()`'s own atomic
claim (`ORDER_CLAIMS`, orders.py::create). Meta's at-least-once delivery guarantee means the exact
same webhook event CAN arrive twice nearly simultaneously (two worker processes, a retry racing the
original), and a flood of DISTINCT customers can hit the same branch's capacity question at once --
both must be handled correctly under real concurrent asyncio tasks, not just sequential calls (see
test_whatsapp_orders_api.py's own `test_the_same_idempotency_key_twice_returns_the_same_order_not_two`
for the sequential version of the first case)."""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

INTERNAL_TOKEN = "t" * 40
TENANT = "tnt_wa_orders_race"
NEAR_RIYADH = (24.72, 46.68)


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


def _seed(client, *, branch_id="br1"):
    from app.core.models import Branch, Service
    from app.core.stores import BranchStore, ServiceStore

    asyncio.run(BranchStore(client.app.state.container.datastore).save(
        Branch(id=branch_id, tenant=TENANT, name="الفرع الرئيسي", lat=NEAR_RIYADH[0],
              lng=NEAR_RIYADH[1], delivery_radius_km=10, active=True)))
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id="svc1", tenant=TENANT, name="غسيل خارجي", price_minor=5000, active=True)))
    return branch_id


def test_twenty_concurrent_requests_with_the_same_idempotency_key_settle_on_exactly_one_order(client):
    """The exact real-world race: Meta's webhook and a client-side retry both racing to create the
    SAME cart at once. Every concurrent caller must either get back the one real order or a clean
    "try again" -- never a second, duplicate order, and never an unhandled exception."""
    branch_id = _seed(client)
    orders = client.app.state.container.orders

    async def _one():
        from app.core.orders import OrderError
        try:
            row = await orders.create(
                tenant=TENANT, branch_id=branch_id, phone="0501234567", customer_name="سباق",
                items=[("svc1", 1)], lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
                idempotency_key="race_key_1")
            return ("ok", row.id)
        except OrderError as exc:
            return ("retry", str(exc))

    async def _run_all():
        return await asyncio.gather(*(_one() for _ in range(20)))

    results = asyncio.run(_run_all())
    ok_ids = {order_id for status, order_id in results if status == "ok"}
    assert len(ok_ids) == 1, f"exactly one real order must have been created, got {ok_ids}"
    # EVERY caller that did not get the order back directly was told to retry, never silently
    # dropped and never an unhandled exception (asyncio.gather would have raised one).
    assert all(status in ("ok", "retry") for status, _ in results)

    final = asyncio.run(orders.by_idempotency_key(TENANT, "race_key_1"))
    assert final is not None and final.id in ok_ids


def test_fifty_concurrent_distinct_orders_at_the_same_branch_all_succeed_independently(client):
    """A load burst of fifty DIFFERENT customers ordering from the same branch at once -- no shared
    lock between distinct idempotency keys should ever make one customer's order block or corrupt
    another's."""
    branch_id = _seed(client)
    orders = client.app.state.container.orders

    async def _one(n: int):
        return await orders.create(
            tenant=TENANT, branch_id=branch_id, phone=f"05012340{n:02d}", customer_name=f"c{n}",
            items=[("svc1", 1)], lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
            idempotency_key=f"load_key_{n}")

    async def _run_all():
        return await asyncio.gather(*(_one(n) for n in range(50)))

    rows = asyncio.run(_run_all())
    assert len({row.id for row in rows}) == 50, "every distinct customer must get their own order"
    assert all(row.total_minor == 5000 for row in rows)


def test_a_retry_that_loses_the_race_still_gets_the_real_order_back_not_a_stale_refusal(client):
    """The claim lane's own TTL-vs-permanent-ledger distinction (orders.py::create's own comment):
    a caller that loses the claim race but checks AFTER the winner has already finished must see
    the real order, never a refusal for a cart that in fact already succeeded."""
    branch_id = _seed(client)
    orders = client.app.state.container.orders

    async def _winner_then_loser():
        from app.core.orders import OrderError
        winner = await orders.create(
            tenant=TENANT, branch_id=branch_id, phone="0501234567", customer_name="أول",
            items=[("svc1", 1)], lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
            idempotency_key="sequential_key")
        try:
            loser = await orders.create(
                tenant=TENANT, branch_id=branch_id, phone="0501234567", customer_name="ثاني",
                items=[("svc1", 1)], lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
                idempotency_key="sequential_key")
        except OrderError:
            pytest.fail("a retry AFTER the winner already finished must get the real order back")
        assert loser.id == winner.id

    asyncio.run(_winner_then_loser())
