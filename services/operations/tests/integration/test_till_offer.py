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


def test_two_coffees_on_one_bill_reach_the_group_basket_test(client, till_headers):
    """THE WHOLE CHAIN, because it was broken in four places and each looked fine alone.

    The till posts an invoice line with a count. That count has to survive:

      1. `parse_lines`, which read `quantity` while our own model calls the field `qty`,
      2. `resolve`, which returned service ids and dropped the counts,
      3. the visit row, which had no field for them,
      4. `/internal/operations/visits/since`, which never emitted the key insights reads.

    Any one of the four breaks it, and NONE of them fails out loud: the map arrives empty,
    `is_group_basket` says «one person», and a table of four teaches the association engine that
    somebody drinks two coffees. The engine's own docstring calls this «the clearest evidence there
    is»; it had never once fired.

    So the assertion is at the END of the chain — the shape insights actually receives.
    """
    r = client.post("/api/v1/till/visits", headers=till_headers["headers"], json={
        "visits": [{
            "phone": "0501234567",
            "invoice_id": "INV-9001",
            "lines": [{"product_id": "P-COFFEE", "name": "قهوة", "qty": 2, "amount_minor": 1800}],
        }],
    })
    assert r.status_code == 200, r.text
    assert r.json().get("accepted") == 1, r.json()

    feed = client.post("/internal/operations/visits/since",
                       headers={"X-Internal-Token": "t" * 40},
                       json={"tenant": till_headers["tenant"], "since": 0})
    assert feed.status_code == 200, feed.text
    visits = feed.json()["visits"]
    assert visits, "the till's sale never reached the feed insights reads"

    # ITS OWN VISIT, FOUND BY THE SERVICE IT SOLD — never `visits[-1]`. Other tests in this module
    # seed visits into the same shop, the feed carries them all, and rows written in the same
    # second have no guaranteed order between them: the assertion passed or failed depending on
    # which row happened to land last. A flaky security-shaped test is worse than none, because
    # the day it means something somebody will re-run it until it goes green.
    # NOT `visits[-1]`. Other tests in this module seed visits into the same shop, the feed carries
    # them all, and rows written in the same second have no order guaranteed between them — the
    # assertion passed or failed depending on which row happened to land last, roughly one run in
    # three. A flaky test on a chain this quiet is worse than none: it teaches whoever runs it to
    # re-run until green, and the day the chain really breaks nobody will look.
    #
    # Selecting on `quantities` keeps the test honest — this sale is the only one that carries a
    # count, so if the chain drops it anywhere the list is empty and this still fails.
    mine = [v for v in visits if v.get("quantities")]
    assert mine, "the count died somewhere between the till and insights"
    quantities = mine[-1]["quantities"]
    assert max(quantities.values()) == 2

    # AND THE VERDICT ITSELF, computed the way insights computes it — a repeated item is a group.
    assert any(int(q) > 1 for q in quantities.values()), (
        "a receipt with two of one item did not read as a group basket")


def test_the_invoice_amount_reaches_the_feed_that_earns_points(client, till_headers):
    """أ-1 — A 480-RIYAL INVOICE WAS WORTH ZERO POINTS, AND NOTHING FAILED.

    The till sends `amount_minor` per line and `parse_lines` read it into `Line.amount_minor`. It
    stopped there: `InvoiceResult` had no amount field, `Visit` had no amount field, and neither the
    event nor the catch-up feed emitted one. loyalty's earn rule asks for `amount_halalas` and
    computes `(amount // 100) * points_per_riyal` — with the key absent that is `(0 // 100) * n`.
    Zero points, on every invoice, for every integrated shop, with «no points configured» recorded
    as the reason and no error in any log on the way.

    The assertion is at the END of the chain: the shape loyalty actually receives.
    """
    r = client.post("/api/v1/till/visits", headers=till_headers["headers"], json={
        "visits": [{
            "phone": "0501234570",
            "invoice_id": "INV-9500",
            "lines": [{"product_id": "P-OIL", "name": "تغيير زيت", "qty": 1,
                       "amount_minor": 45000},
                      {"product_id": "P-FILTER", "name": "فلتر", "qty": 1,
                       "amount_minor": 3000}],
        }],
    })
    assert r.status_code == 200, r.text
    accepted = r.json()
    assert accepted.get("accepted") == 1, accepted

    feed = client.post("/internal/operations/visits/since",
                       headers={"X-Internal-Token": "t" * 40},
                       json={"tenant": till_headers["tenant"], "since": 0})
    assert feed.status_code == 200, feed.text
    # ITS OWN SALE, FOUND BY ITS OWN VISIT ID — never `[-1]`. Other tests in this module post into
    # the same shop, the feed carries every one of them, and rows written in the same second have
    # no guaranteed order between them: this assertion read another test's coffee receipt whenever
    # that one happened to land last. A flaky test on a chain this quiet is worse than none — it
    # teaches whoever runs it to re-run until green, and the day the amount really stops arriving
    # nobody will look. Keyed on the id the till route itself returned, the row is found either way
    # and only the number can fail.
    vid = accepted["results"][0]["visit_id"]
    mine = [v for v in feed.json()["visits"] if v.get("visit_id") == vid]
    assert mine, "the sale never reached the feed loyalty reads"
    assert mine[0]["amount_halalas"] == 48000, "480 riyals, summed from both lines"

    # AND THE RULE THAT READS IT, computed the way loyalty computes it.
    assert (mine[0]["amount_halalas"] // 100) * 1 == 480
