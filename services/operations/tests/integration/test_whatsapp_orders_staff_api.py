"""WhatsApp Direct Ordering, Step 7 — the shop's own staff door to move an order through its
lifecycle (`api/v1/whatsapp_orders.py`). Each transition already fires `operations.order.changed`
on success (`OrderService._emit`) — services/reminders' own subscriber (a separate microservice,
not exercised here) is what actually turns that into the customer's WhatsApp message; this suite
proves the event itself carries the right status for every real transition, and that every refusal
(wrong capability, wrong current status) is a real, honest refusal rather than a silent no-op."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
INTERNAL_TOKEN = "t" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_wa_orders_staff"
NEAR_RIYADH = (24.72, 46.68)


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT, sub: str = "staff1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": sub, "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client():
    saved = dict(os.environ)
    c = _make_app()
    yield c
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


class _RecordingEventBus:
    def __init__(self):
        self.published: list[dict] = []

    async def publish(self, topic, event):
        self.published.append({"topic": topic, "payload": dict(event.payload)})


def _seed_order(client, *, status: str = "received") -> str:
    """A real Order, created through the real `OrderService.create()` -- seeded straight to a
    later status only by directly setting+saving the row (never re-deriving the state machine),
    exactly like test_orders.py's own fixtures do for the same reason."""
    from app.core.models import Branch, Service
    from app.core.stores import BranchStore, ServiceStore

    asyncio.run(BranchStore(client.app.state.container.datastore).save(
        Branch(id="br1", tenant=TENANT, name="الفرع الرئيسي", lat=NEAR_RIYADH[0],
              lng=NEAR_RIYADH[1], delivery_radius_km=10, active=True)))
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id="svc1", tenant=TENANT, name="غسيل خارجي", price_minor=5000, active=True)))
    orders = client.app.state.container.orders
    import uuid
    row = asyncio.run(orders.create(
        tenant=TENANT, branch_id="br1", phone="0501234567", customer_name="أحمد",
        items=[("svc1", 1)], lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
        idempotency_key=f"wamid_{uuid.uuid4().hex}"))
    if status != "received":
        row.status = status
        asyncio.run(orders._save(row))
    return row.id


def test_requires_operations_record_capability(client):
    order_id = _seed_order(client)
    r = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/preparing",
                    headers=_auth("some.other.capability"))
    assert r.status_code == 403


def test_the_full_lifecycle_fires_the_right_event_at_every_real_transition(client):
    events = _RecordingEventBus()
    order_id = _seed_order(client, status="confirmed")
    client.app.state.container.orders._events = events
    headers = _auth("operations.record")

    r1 = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/preparing", headers=headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "preparing"

    r2 = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/ready", headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "ready"

    r3 = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/out-for-delivery", headers=headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["status"] == "out_for_delivery"

    r4 = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/delivered", headers=headers)
    assert r4.status_code == 200, r4.text
    assert r4.json()["status"] == "delivered"
    assert r4.json()["visit_id"], "delivery must record a real visit"

    statuses_published = [e["payload"]["status"] for e in events.published]
    assert statuses_published == ["preparing", "ready", "out_for_delivery", "delivered"]
    for e in events.published:
        assert e["topic"] == "operations.order.changed"
        assert e["payload"]["order_id"] == order_id
        assert e["payload"]["tenant"] == TENANT


def test_jumping_straight_from_confirmed_to_ready_is_refused(client):
    order_id = _seed_order(client, status="confirmed")
    r = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/ready",
                    headers=_auth("operations.record"))
    assert r.status_code == 400


def test_cancelling_before_preparation_starts_succeeds_and_fires_the_cancelled_event(client):
    events = _RecordingEventBus()
    order_id = _seed_order(client, status="received")
    client.app.state.container.orders._events = events
    r = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/cancel",
                    json={"reason": "العميل غيّر رأيه"}, headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    assert events.published[0]["payload"]["status"] == "cancelled"


def test_cancelling_after_preparation_has_started_is_refused(client):
    """`CANCELLABLE_FROM` stops at `CONFIRMED` -- once the shop has begun fulfilling it, cancelling
    is a conversation with the customer, never a button."""
    order_id = _seed_order(client, status="preparing")
    r = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/cancel",
                    json={}, headers=_auth("operations.record"))
    assert r.status_code == 400


def test_resolving_a_payment_mismatch_moves_the_order_to_confirmed(client):
    events = _RecordingEventBus()
    order_id = _seed_order(client, status="payment_mismatch")
    client.app.state.container.orders._events = events
    r = client.post(f"/api/v1/staff/whatsapp-orders/{order_id}/resolve-mismatch",
                    headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    assert events.published[0]["payload"]["status"] == "confirmed"


def test_getting_an_unknown_order_id_is_a_clean_404(client):
    r = client.get("/api/v1/staff/whatsapp-orders/ord_does_not_exist",
                   headers=_auth("operations.record"))
    assert r.status_code == 404


# ── the list door, Step 8's own backend gap (found 2026-10-05) ───────────────────────────────────

def test_list_requires_operations_record_capability(client):
    r = client.get("/api/v1/staff/whatsapp-orders", headers=_auth("some.other.capability"))
    assert r.status_code == 403


def test_list_returns_every_real_order(client):
    """Sorting itself (newest-first) is `OrderService.list()`'s own, already-tested contract
    (test_orders.py) — two orders created in the same test, same wall-clock second, cannot
    prove an ordering claim here without a flaky sleep; this proves the route's own job: nothing
    created is silently missing from the response."""
    id1 = _seed_order(client, status="received")
    id2 = _seed_order(client, status="confirmed")
    r = client.get("/api/v1/staff/whatsapp-orders", headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    ids = {o["id"] for o in r.json()["orders"]}
    assert {id1, id2} <= ids


def test_list_filters_by_status(client):
    _seed_order(client, status="received")
    confirmed_id = _seed_order(client, status="confirmed")
    r = client.get("/api/v1/staff/whatsapp-orders", params={"status_filter": "confirmed"},
                   headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    orders = r.json()["orders"]
    assert len(orders) == 1 and orders[0]["id"] == confirmed_id


def test_list_narrows_to_the_callers_own_branch_scope(client):
    """Same rule this module's own docstring states for the status-change actions: branch scope
    narrows READS, never writes — this is that narrowing, applied for the first time to the
    order list itself."""
    from app.core.models import Branch
    from app.core.stores import BranchStore

    asyncio.run(BranchStore(client.app.state.container.datastore).save(
        Branch(id="br2", tenant=TENANT, name="فرع ثاني", lat=NEAR_RIYADH[0],
              lng=NEAR_RIYADH[1], delivery_radius_km=10, active=True)))
    br1_order = _seed_order(client, status="received")
    from app.core.models import Service
    from app.core.stores import ServiceStore
    import uuid

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id="svc2", tenant=TENANT, name="تلميع", price_minor=3000, active=True)))
    br2_order = asyncio.run(client.app.state.container.orders.create(
        tenant=TENANT, branch_id="br2", phone="0509998888", customer_name="سالم",
        items=[("svc2", 1)], lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
        idempotency_key=f"wamid_{uuid.uuid4().hex}")).id

    r = client.get("/api/v1/staff/whatsapp-orders", params={"branch_id": "br1"},
                   headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    ids = {o["id"] for o in r.json()["orders"]}
    assert br1_order in ids
    assert br2_order not in ids


# ── the pause door, the same backend gap ─────────────────────────────────────────────────────────

def test_pause_requires_operations_record_capability(client):
    r = client.get("/api/v1/staff/whatsapp-orders/pause", params={"branch_id": "br1"},
                   headers=_auth("some.other.capability"))
    assert r.status_code == 403


def test_a_branch_never_paused_reads_as_open(client):
    r = client.get("/api/v1/staff/whatsapp-orders/pause", params={"branch_id": "br1"},
                   headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    assert r.json() == {"branch_id": "br1", "paused": False, "reason": ""}


def test_pausing_a_branch_is_read_back_with_its_reason(client):
    r = client.post("/api/v1/staff/whatsapp-orders/pause",
                    json={"branch_id": "br1", "paused": True, "reason": "ازدحام مؤقت"},
                    headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    assert r.json()["paused"] is True
    assert r.json()["reason"] == "ازدحام مؤقت"

    read_back = client.get("/api/v1/staff/whatsapp-orders/pause", params={"branch_id": "br1"},
                           headers=_auth("operations.record"))
    assert read_back.json() == {"branch_id": "br1", "paused": True, "reason": "ازدحام مؤقت"}


def test_a_paused_branch_actually_refuses_a_new_order():
    """THE WHOLE POINT — proves the button this door exists for actually reaches the real,
    already-enforced check inside OrderService.create()."""
    from app.core.orders import OrderError

    client = _make_app()
    from app.core.models import Branch, Service
    from app.core.stores import BranchStore, ServiceStore

    asyncio.run(BranchStore(client.app.state.container.datastore).save(
        Branch(id="br1", tenant=TENANT, name="الفرع الرئيسي", lat=NEAR_RIYADH[0],
              lng=NEAR_RIYADH[1], delivery_radius_km=10, active=True)))
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id="svc1", tenant=TENANT, name="غسيل خارجي", price_minor=5000, active=True)))

    client.post("/api/v1/staff/whatsapp-orders/pause",
               json={"branch_id": "br1", "paused": True, "reason": "إغلاق مبكر"},
               headers=_auth("operations.record"))

    import uuid
    with pytest.raises(OrderError, match="متوقف"):
        asyncio.run(client.app.state.container.orders.create(
            tenant=TENANT, branch_id="br1", phone="0501234567", customer_name="أحمد",
            items=[("svc1", 1)], lat=NEAR_RIYADH[0], lng=NEAR_RIYADH[1],
            idempotency_key=f"wamid_{uuid.uuid4().hex}"))


def test_resuming_clears_the_reason(client):
    client.post("/api/v1/staff/whatsapp-orders/pause",
               json={"branch_id": "br1", "paused": True, "reason": "صيانة"},
               headers=_auth("operations.record"))
    r = client.post("/api/v1/staff/whatsapp-orders/pause",
                   json={"branch_id": "br1", "paused": False},
                   headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    assert r.json()["paused"] is False
    assert r.json()["reason"] == ""


# ── Step 9's own on/off switch for the "share with the delivery rep" button ─────────────────────

def test_share_toggle_requires_operations_record_capability(client):
    r = client.get("/api/v1/staff/whatsapp-orders/share-toggle",
                   headers=_auth("some.other.capability"))
    assert r.status_code == 403


def test_a_shop_that_never_touched_it_reads_as_enabled(client):
    r = client.get("/api/v1/staff/whatsapp-orders/share-toggle", headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": True}


def test_turning_it_off_is_read_back_off(client):
    off = client.post("/api/v1/staff/whatsapp-orders/share-toggle", json={"enabled": False},
                      headers=_auth("operations.record"))
    assert off.status_code == 200, off.text
    assert off.json()["enabled"] is False

    read_back = client.get("/api/v1/staff/whatsapp-orders/share-toggle",
                           headers=_auth("operations.record"))
    assert read_back.json() == {"enabled": False}


def test_turning_it_back_on_is_read_back_on(client):
    client.post("/api/v1/staff/whatsapp-orders/share-toggle", json={"enabled": False},
               headers=_auth("operations.record"))
    r = client.post("/api/v1/staff/whatsapp-orders/share-toggle", json={"enabled": True},
                   headers=_auth("operations.record"))
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is True
