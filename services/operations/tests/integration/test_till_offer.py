"""Honouring an offer at an integrated till — the door that did not exist.

THE GAP. An exclusive offer is the reason a customer came back, and the counter is where it is
honoured. The till API could read his points and his rewards, and had no way to see or apply the
one thing the message promised him. So a shop on a cashier integration ran offers it could not
redeem: the customer arrives holding it, the cashier has no button, and the shop either gives the
discount off the books or refuses a customer it invited.

The file that serves the till says so itself, at the top: «not the offer he is holding — at the one
moment in the whole product…». The sentence was there; the route was not.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/till/offer/apply"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_till_offer"


@pytest.fixture(scope="module")
def client():
    """Its own app with HS256 auth: the till is an AUTHENTICATED machine, and the shared fixture
    verifies no token."""
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
        # A real salt: the pseudonym is derived from it, and an empty one is refused by design.
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
    """`operations.record` — the capability the till routes are gated on."""
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "till1", "iss": ISS, "aud": AUD, "caps": ["operations.record"],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"headers": {"Authorization": f"Bearer {tok}"}, "tenant": TENANT}


class Chooser:
    """Stands in for reminders, which alone knows what was sent and with what scope."""

    def __init__(self, offer=None, boom=None):
        self._offer, self._boom = offer, boom
        self.asked: list[dict] = []

    async def __call__(self, *, tenant, subject_ref, service_ids):
        self.asked.append({"tenant": tenant, "subject_ref": subject_ref})
        if self._boom:
            raise self._boom
        return self._offer


def _seed_visit(client, tenant: str, phone: str) -> tuple[str, str]:
    """A customer and a recorded visit — the till's own flow, in order."""
    import asyncio

    from app.core.models import Service
    from app.core.stores import ServiceStore

    ops = client.app.state.container.operations
    ds = client.app.state.container.datastore

    async def go():
        # A real service in this shop's catalogue: recording a visit against an unknown one is
        # refused by design, and a fixture that leans on that refusal tests the wrong thing.
        await ServiceStore(ds).save(Service(id="svc_a", tenant=tenant, name="غسيل"))
        v = await ops.record_visit(tenant=tenant, phone=phone, service_ids=["svc_a"])
        return v.visit.id, v.customer.subject_ref

    return asyncio.run(go())


def test_the_till_can_apply_the_offer_the_customer_is_holding(till_headers, client):
    """THE DEFECT ITSELF: there was no route at all."""
    tenant = till_headers["tenant"]
    visit_id, _ = _seed_visit(client, tenant, "0501110001")
    client.app.state.container.operations.with_offer_chooser(
        Chooser({"ref": "off_1", "text": "خصم 20%"}))

    r = client.post(PATH, json={"visit_id": visit_id, "phone": "0501110001", "actor": "cashier"},
                    headers=till_headers["headers"])

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True
    assert body["offer"]["ref"] == "off_1"


def test_a_second_tap_spends_nothing_more(till_headers, client):
    """A double tap at a counter is one intention, not two discounts on one invoice."""
    tenant = till_headers["tenant"]
    visit_id, _ = _seed_visit(client, tenant, "0501110002")
    client.app.state.container.operations.with_offer_chooser(
        Chooser({"ref": "off_2", "text": "خصم"}))

    first = client.post(PATH, json={"visit_id": visit_id, "phone": "0501110002"},
                        headers=till_headers["headers"]).json()
    second = client.post(PATH, json={"visit_id": visit_id, "phone": "0501110002"},
                         headers=till_headers["headers"]).json()

    assert first["offer"]["ref"] == second["offer"]["ref"] == "off_2"


def test_an_unreachable_judge_refuses_in_words_the_cashier_can_read(till_headers, client):
    """«لا يوجد عرض» and «تعذّر السؤال» are different sentences for the customer in front of you."""
    from app.adapters.offer_choice import OfferPeerUnavailable

    tenant = till_headers["tenant"]
    visit_id, _ = _seed_visit(client, tenant, "0501110003")
    client.app.state.container.operations.with_offer_chooser(
        Chooser(boom=OfferPeerUnavailable("reminders is restarting")))

    body = client.post(PATH, json={"visit_id": visit_id, "phone": "0501110003"},
                       headers=till_headers["headers"]).json()

    assert body["applied"] is False
    assert "تعذّر" in body["reason"], "an unreadable peer must not read as «he has no offer»"


def test_an_unknown_customer_is_named_as_such(till_headers, client):
    body = client.post(PATH, json={"visit_id": "vis_nope", "phone": "0509999999"},
                       headers=till_headers["headers"]).json()

    assert body["applied"] is False
    assert "لا يوجد عميل" in body["reason"]


def test_the_pseudonym_never_leaves(till_headers, client):
    """It is our join key between services and a till has no use for it — handing it out would put
    a durable cross-service identifier into a third party's database for nothing."""
    tenant = till_headers["tenant"]
    visit_id, subject = _seed_visit(client, tenant, "0501110004")
    client.app.state.container.operations.with_offer_chooser(
        Chooser({"ref": "off_4", "text": "خصم"}))

    raw = client.post(PATH, json={"visit_id": visit_id, "phone": "0501110004"},
                      headers=till_headers["headers"]).text

    assert subject not in raw
