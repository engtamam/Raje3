"""The freelancer's own screen, doubled as the shop's internal workspace tab
(api/v1/freelancer_portal.py). Two capabilities reach this file on purpose
(`operations.freelancer_portal` — a freelancer's own token; `operations.freelancer_manage` — a
shop's own staff). Operator and partner must still be refused — neither capability is in their
real role.
"""
from __future__ import annotations

import datetime as dt
import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
INTERNAL_TOKEN = "t" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_freelancer_portal_api"

MANAGE = "operations.freelancer_manage"
PORTAL = "operations.freelancer_portal"


def _make_app() -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT, sub: str = "owner1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": sub, "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def client(env_guard) -> TestClient:
    return _make_app()


def _seed_customer(client: TestClient, customer_id: str = "cust_1") -> None:
    import asyncio

    from app.core.models import Customer
    from app.core.stores import CustomerStore

    store = client.app.state.container.datastore
    asyncio.run(CustomerStore(store).save(
        Customer(id=customer_id, tenant=TENANT, phone="+966501234567", subject_ref="subj_1",
                 name="أحمد", last_visit=int(time.time()))))


# ── capability gating — either capability works, neither-held is refused ──────────────────────
def test_list_customers_refuses_without_either_capability(client):
    r = client.get("/api/v1/staff/freelancer-portal/customers", headers=_auth())
    assert r.status_code == 403


def test_list_customers_refuses_the_operator_role(client):
    r = client.get("/api/v1/staff/freelancer-portal/customers",
                   headers=_auth("operations.record", "operations.mobile_requests_execute"))
    assert r.status_code == 403


def test_list_customers_refuses_the_partner_role(client):
    r = client.get("/api/v1/staff/freelancer-portal/customers", headers=_auth("partner.till"))
    assert r.status_code == 403


def test_list_customers_succeeds_with_the_manage_capability(client):
    _seed_customer(client)
    r = client.get("/api/v1/staff/freelancer-portal/customers", headers=_auth(MANAGE))
    assert r.status_code == 200
    assert len(r.json()["customers"]) == 1


def test_list_customers_succeeds_with_only_the_portal_capability(client):
    _seed_customer(client)
    r = client.get("/api/v1/staff/freelancer-portal/customers", headers=_auth(PORTAL))
    assert r.status_code == 200
    assert len(r.json()["customers"]) == 1


def test_a_freelancer_token_never_reaches_the_staff_only_door(client):
    r = client.get("/api/v1/staff/freelancers", headers=_auth(PORTAL))
    assert r.status_code == 403


# ── rate / dnd / reward / escalate / notes ──────────────────────────────────────────────────────
def test_rate_customer_round_trips_and_hides_them(client):
    _seed_customer(client)
    r = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/rate",
                    headers=_auth(PORTAL), json={"status": "satisfied"})
    assert r.status_code == 200
    r2 = client.get("/api/v1/staff/freelancer-portal/customers", headers=_auth(MANAGE))
    assert not any(c["customer_id"] == "cust_1" for c in r2.json()["customers"])


def test_rate_customer_rejects_an_unknown_status(client):
    _seed_customer(client)
    r = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/rate",
                    headers=_auth(PORTAL), json={"status": "confused"})
    assert r.status_code == 400


def test_do_not_disturb_round_trips(client):
    _seed_customer(client)
    r = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/do-not-disturb",
                    headers=_auth(PORTAL))
    assert r.status_code == 200
    r2 = client.get("/api/v1/staff/freelancer-portal/customers", headers=_auth(MANAGE))
    assert not any(c["customer_id"] == "cust_1" for c in r2.json()["customers"])


def test_grant_reward_refuses_an_unknown_option(client):
    _seed_customer(client)
    r = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/reward",
                    headers=_auth(PORTAL), json={"option_id": "nope"})
    assert r.status_code == 400


def test_grant_reward_round_trips_with_a_real_option(client):
    _seed_customer(client)
    opt = client.post("/api/v1/staff/freelancers/reward-options", headers=_auth(MANAGE),
                      json={"kind": "gift", "label": "غسيل مجاني"}).json()
    r = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/reward",
                    headers=_auth(PORTAL), json={"option_id": opt["id"]})
    assert r.status_code == 200
    assert r.json()["fulfilled"] is False


def test_escalate_round_trips_and_appears_in_the_staff_inbox(client):
    _seed_customer(client)
    r = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/escalate",
                    headers=_auth(PORTAL), json={"note": "عميل غير راضٍ"})
    assert r.status_code == 200
    esc_id = r.json()["id"]
    inbox = client.get("/api/v1/staff/freelancers/escalations", headers=_auth(MANAGE)).json()
    assert any(e["id"] == esc_id for e in inbox["escalations"])


def test_escalate_requires_a_non_empty_note(client):
    _seed_customer(client)
    r = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/escalate",
                    headers=_auth(PORTAL), json={"note": ""})
    assert r.status_code == 422


def test_resolve_escalation_as_staff_round_trips(client):
    _seed_customer(client)
    esc = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/escalate",
                      headers=_auth(PORTAL), json={"note": "عميل غير راضٍ"}).json()
    r = client.post(f"/api/v1/staff/freelancers/escalations/{esc['id']}/resolve",
                    headers=_auth(MANAGE), json={"resolution_note": "تم الاتصال"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


def test_add_note_round_trips(client):
    _seed_customer(client)
    r = client.post("/api/v1/staff/freelancer-portal/customers/cust_1/notes",
                    headers=_auth(PORTAL), json={"text": "تم الاتصال", "status": "satisfied",
                                                 "services": ["غسيل خارجي"]})
    assert r.status_code == 200
    assert r.json()["services"] == ["غسيل خارجي"]


def test_notes_export_from_the_staff_door_includes_the_added_note(client):
    _seed_customer(client)
    client.post("/api/v1/staff/freelancer-portal/customers/cust_1/notes",
               headers=_auth(PORTAL), json={"text": "تم الاتصال", "status": "satisfied"})
    r = client.get("/api/v1/staff/freelancers/notes/export", headers=_auth(MANAGE),
                   params={"since": 0, "until": 9_999_999_999})
    assert "تم الاتصال" in r.json()["text"]
