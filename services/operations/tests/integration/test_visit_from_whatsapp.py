"""`/internal/operations/visits/from-whatsapp` — the visit-registration Flow's own hand-off (a
SECOND channel alongside the console, resolved by an already-verified WhatsApp sender phone
instead of a console PIN ticket). Resolves by phone (never a customer_id — whatsapp-assistant
holds none), hands off to the SAME `record_visit()` every other path uses — this file proves the
hand-off, not `record_visit()`'s own rules (covered by its own tests) or `internal_visit_from_
customer`'s (covered by test_visit_from_customer.py).
"""
from __future__ import annotations

import asyncio

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/visits/from-whatsapp"
TENANT = "tnt_from_whatsapp"


def _seed(client, *, phone: str = ""):
    from app.core.models import Customer, Operator, Service
    from app.core.stores import CustomerStore, OperatorStore, ServiceStore

    op = Operator(id="op_ww1", tenant=TENANT, name="فهد", role="operator", active=True,
                 created=1786860000)
    svc = Service(id="svc_ww1", tenant=TENANT, name="غسلة", duration_minutes=30, active=True)
    c = client.app.state.container
    asyncio.run(OperatorStore(c.datastore).save(op))
    asyncio.run(ServiceStore(c.datastore).save(svc))
    if phone:
        # PRE-SEEDED, NOT COMPUTED — a brand-new phone would need `record_visit`'s own
        # `_resolve_customer` to mint a fresh `subject_ref`, which refuses without a real
        # PII_SALT (core/pii.py). Same "known customer already exists" shape
        # test_visit_from_customer.py's own `_seed` uses, for the same reason.
        cust = Customer(id=f"cus_ww_{phone[-4:]}", tenant=TENANT, phone=phone, name="",
                        subject_ref="sub_" + phone[-4:].rjust(24, "0"), created=1786860000)
        asyncio.run(CustomerStore(c.datastore).save(cust))
    return op.id, svc.id


def test_a_visit_is_recorded_by_phone_with_no_ticket_required(client):
    op_id, svc_id = _seed(client, phone="966500000002")
    r = client.post(PATH, json={"tenant": TENANT, "phone": "966500000002",
                                "service_ids": [svc_id], "operator_id": op_id,
                                "idempotency_key": "wa_1"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recorded"] is True
    assert body["duplicate"] is False
    assert body["visit_id"]


def test_a_retry_returns_the_same_visit_not_a_second_one(client):
    _op_id, svc_id = _seed(client, phone="966500000003")
    body = {"tenant": TENANT, "phone": "966500000003", "service_ids": [svc_id],
           "idempotency_key": "wa_retry"}
    first = client.post(PATH, json=body, headers=INTERNAL).json()
    second = client.post(PATH, json=body, headers=INTERNAL).json()
    assert first["visit_id"] == second["visit_id"]
    assert second["duplicate"] is True


def test_an_empty_operator_id_still_records_the_visit(client):
    _op_id, svc_id = _seed(client, phone="966500000004")
    r = client.post(PATH, json={"tenant": TENANT, "phone": "966500000004",
                                "service_ids": [svc_id], "idempotency_key": "wa_2"},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] is True


def test_an_unknown_service_id_is_stored_as_is_same_as_the_console_route(client):
    """`allow_unknown_services` stays at its default (False) here, same as field.py's own console
    route and internal_visit_from_customer — this route validates nothing extra beyond what
    record_visit() already does for every other channel, on purpose (see operations.py's own
    docstring: refusing an unknown service loses the whole visit, not just its label)."""
    _op_id, _svc_id = _seed(client, phone="966500000005")
    r = client.post(PATH, json={"tenant": TENANT, "phone": "966500000005",
                                "service_ids": ["svc_missing"], "idempotency_key": "wa_3"},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] is True


def test_no_token_is_refused(client):
    r = client.post(PATH, json={"tenant": TENANT, "phone": "966500000006",
                                "service_ids": ["svc_x"], "idempotency_key": "wa_4"})
    assert r.status_code == 401
