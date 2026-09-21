"""GET /field/customers/by-phone now carries the customer's current points balance alongside the
existing fields — a plain, read-only number from `loyalty` (same `LoyaltyDesk.balance` call
`till.py`'s own customer-lookup route already makes), never folded into the single-use
`EntitlementGateway` (points are a running balance, not a single-grant/single-redeem thing).

THE FAILURE POSTURE IS DELIBERATELY MORE LENIENT THAN `apply_offer`'s — this is advisory
information, not a spend: a `loyalty` outage must omit the field, never break the whole lookup
(the operator still needs to see the customer's name, phone and visit count to do his job)."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_points_lookup"
PHONE = "0501111111"


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers() -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": ["operations.read"],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _make_customer(client: TestClient) -> None:
    from app.core.models import Customer
    from app.core.operations import _normalise_phone
    from app.core.stores import CustomerStore

    store = client.app.state.container.datastore
    # STORED THE SAME NORMALISED WAY `record_visit` ALWAYS WRITES IT — `by_phone`'s own lookup is
    # an exact match against `_normalise_phone(query)`, so a raw, un-normalised phone on the row
    # would simply never be found (this is not what the test is about; poking a customer in with
    # the wrong shape would silently fail before ever reaching the code under test).
    asyncio.run(CustomerStore(store).save(Customer(
        id="cus_1", tenant=TENANT, phone=_normalise_phone(PHONE), name="عميل",
        subject_ref="sub_" + "a" * 20)))


class _FakeDesk:
    def __init__(self, answer) -> None:
        self._answer = answer
        self.configured = True
        self.calls = 0

    async def balance(self, *, tenant, subject_ref):
        self.calls += 1
        if self._answer is Exception:
            raise RuntimeError("loyalty down")
        return self._answer


def test_a_customer_with_a_real_balance_carries_it_in_the_lookup(client: TestClient):
    _make_customer(client)
    client.app.state.container.loyalty_desk = _FakeDesk(
        {"has_programme": True, "points": 340, "to_next_reward": 60, "rewards": []})
    resp = client.get("/api/v1/field/customers/by-phone", params={"phone": PHONE},
                      headers=_headers())
    assert resp.status_code == 200, resp.text
    assert resp.json()["customer"]["points_balance"] == 340


def test_a_shop_with_no_loyalty_programme_gets_no_field_not_a_zero(client: TestClient):
    _make_customer(client)
    client.app.state.container.loyalty_desk = _FakeDesk({"has_programme": False})
    resp = client.get("/api/v1/field/customers/by-phone", params={"phone": PHONE},
                      headers=_headers())
    assert resp.status_code == 200, resp.text
    assert "points_balance" not in resp.json()["customer"]


def test_a_loyalty_outage_omits_the_field_and_never_breaks_the_lookup(client: TestClient):
    _make_customer(client)
    client.app.state.container.loyalty_desk = _FakeDesk(None)     # unreachable peer -> None
    resp = client.get("/api/v1/field/customers/by-phone", params={"phone": PHONE},
                      headers=_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()["customer"]
    assert body["name"] == "عميل"                                # the lookup itself still works
    assert "points_balance" not in body


def test_a_loyalty_call_that_raises_still_never_breaks_the_lookup(client: TestClient):
    """The peer itself throwing (not just answering unreachable) must not become a 500 on a route
    whose whole job is showing who is standing at the counter."""
    _make_customer(client)
    client.app.state.container.loyalty_desk = _FakeDesk(Exception)
    resp = client.get("/api/v1/field/customers/by-phone", params={"phone": PHONE},
                      headers=_headers())
    assert resp.status_code == 200, resp.text
    assert "points_balance" not in resp.json()["customer"]
