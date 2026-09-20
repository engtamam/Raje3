"""POST /api/v1/subscription/checkout — buy several apps together, one confirmation.

The whole reason this route exists: `may_add`'s own `plan.requires_any` gate only ever checked
`held` — what a shop already owns from an earlier, SEPARATE purchase — so a dependency and the
app that needs it could never be bought in one action. This route validates a whole cart together
(`may_add_bundle`), then executes each item against billing-service's existing single-plan
subscribe route, one at a time, stopping at the first failure — see the route's own docstring for
why a real merged invoice needs a platform-side change this service does not own.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"


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
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(tenant: str = "t_cart") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      **({"tenant": tenant} if tenant else {}),
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class FakePlans:
    """Keyed by plan_id, unlike test_operator_api.py's own FakePlans (which only ever needed one
    plan per test) — a cart checkout is the one caller that reads several plan_ids in one call."""

    def __init__(self):
        self.catalog: dict[str, dict] = {}
        self.held: list[dict] | None = []
        self.subscribed: list[tuple[str, str, str]] = []
        self.tokens: list[str] = []
        self.refuse_plan_ids: set[str] = set()  # billing itself refuses these on subscribe()

    def add(self, plan_id: str, *, limits: dict | None = None, trial: int = 0,
           amount: int | None = 9900) -> None:
        self.catalog[plan_id] = {"limits": limits or {}, "trial": trial, "amount": amount}

    async def trial_days(self, plan_id: str) -> int:
        return self.catalog.get(plan_id, {}).get("trial", 0)

    async def limits(self, plan_id: str):
        entry = self.catalog.get(plan_id)
        return None if entry is None else dict(entry["limits"])

    async def amount_minor(self, plan_id: str):
        entry = self.catalog.get(plan_id)
        return None if entry is None else entry["amount"]

    async def subscriptions(self, tenant: str):
        return self.held

    async def subscribe(self, *, tenant: str, plan_id: str, interval: str = "month",
                        payment_token: str = ""):
        self.tokens.append(payment_token)
        if plan_id in self.refuse_plan_ids:
            return 402, {"error": "CARD_DECLINED"}
        self.subscribed.append((tenant, plan_id, interval))
        return 201, {"id": f"sub_{plan_id}", "tenant": tenant, "plan_id": plan_id}


class FakeConnections:
    def __init__(self, connected: bool):
        self._c = connected

    async def connected(self, tenant: str) -> bool:
        return self._c


def _wire(client, *, connected: bool) -> FakePlans:
    plans = FakePlans()
    client.app.state.container.billing_plans = plans
    client.app.state.container.connections = FakeConnections(connected)
    return plans


VISIT = {"feature.visit": {"limit": 1}}
LOYALTY = {"feature.loyalty": {"limit": 1},
          "plan.requires_any": {"kind": "list", "list": ["feature.visit", "feature.bookings"]}}
PRO = {"feature.pro": {"limit": 1}}


def _post(client, items, payment_token="tok_1", tenant="t_cart"):
    return client.post("/api/v1/subscription/checkout",
                       json={"items": items, "payment_token": payment_token},
                       headers=_auth(tenant))


def _items(*plan_ids: str, interval: str = "month") -> list[dict]:
    return [{"plan_id": pid, "interval": interval} for pid in plan_ids]


# ── the whole reason this route exists ────────────────────────────────────────────────────────
def test_a_dependency_and_its_app_check_out_together(client):
    """نقاطي + تسجيل زيارة, neither held before — refused by `may_add` alone, allowed here
    because both travel in the same cart. Only one of the two is genuinely priced; the other is
    free, so this also proves the "at most one real charge" rule does not over-refuse a cart that
    only has one thing to actually pay for."""
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)  # free
    plans.add("plan_loyalty", limits=LOYALTY, amount=9900)  # the one real charge

    r = _post(client, _items("plan_visit", "plan_loyalty"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert [i["ok"] for i in body["items"]] == [True, True]
    assert plans.subscribed == [
        ("t_cart", "plan_visit", "once"),  # free, subscribed once not monthly
        ("t_cart", "plan_loyalty", "month"),
    ]


def test_order_in_the_cart_does_not_matter_for_the_dependency(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_loyalty", limits=LOYALTY, amount=9900)

    r = _post(client, _items("plan_loyalty", "plan_visit"))
    assert r.status_code == 200, r.text


def test_the_dependency_still_refuses_when_nothing_in_the_cart_satisfies_it(client):
    """The cart alone does not waive the rule — it only widens what may satisfy it."""
    plans = _wire(client, connected=True)
    plans.add("plan_loyalty", limits=LOYALTY, amount=9900)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_loyalty", "plan_pro"))
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["error"] == "CHECKOUT_REFUSED"
    assert "تسجيل زيارة" in body["message"]
    assert body["plan_id"] == "plan_loyalty"
    assert plans.subscribed == [], "nothing may charge once the bundle itself is refused"


def test_a_dependency_already_held_from_an_earlier_purchase_still_works_in_a_cart(client):
    plans = _wire(client, connected=True)
    plans.held = [{"limits_snapshot": {"feature.visit": {"limit": 1}}}]
    plans.add("plan_loyalty", limits=LOYALTY, amount=9900)

    r = _post(client, _items("plan_loyalty"))
    assert r.status_code == 200, r.text
    assert plans.subscribed == [("t_cart", "plan_loyalty", "month")]


def test_the_same_plan_id_twice_is_refused_before_anything_charges(client):
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=0)

    r = _post(client, _items("plan_pro", "plan_pro"))
    assert r.status_code == 409, r.text
    assert plans.subscribed == []


def test_an_already_held_app_refuses_the_whole_cart(client):
    plans = _wire(client, connected=True)
    plans.held = [{"limits_snapshot": {"feature.pro": {"limit": 1}}}]
    plans.add("plan_pro", limits=PRO, amount=9900)
    plans.add("plan_visit", limits=VISIT, amount=0)

    r = _post(client, _items("plan_pro", "plan_visit"))
    assert r.status_code == 409, r.text
    assert r.json()["plan_id"] == "plan_pro"
    assert plans.subscribed == []


# ── at most one genuinely-paid item ───────────────────────────────────────────────────────────
def test_two_real_paid_items_are_refused_outright(client):
    """The single-use-token limit — see the route's own docstring. Neither is free or on a
    trial, so charging both with the same token is exactly the shape this refuses."""
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=9900)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_visit", "plan_pro"))
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "MULTI_CHARGE_UNSUPPORTED"
    assert plans.subscribed == [], "neither item may charge once the cart itself is refused"


def test_one_paid_item_with_several_free_items_is_allowed(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_bookings", limits={"feature.bookings": {"limit": 1}}, amount=0)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_visit", "plan_bookings", "plan_pro"))
    assert r.status_code == 200, r.text
    assert len(plans.subscribed) == 3


def test_one_paid_item_with_a_trial_item_is_allowed(client):
    """A trial needs no charge either — `trial_days > 0` counts the same as free for the
    at-most-one-charge rule."""
    plans = _wire(client, connected=True)
    plans.add("plan_trial", limits=VISIT, amount=9900, trial=14)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_trial", "plan_pro"))
    assert r.status_code == 200, r.text


def test_all_free_items_need_no_payment_token_at_all(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_bookings", limits={"feature.bookings": {"limit": 1}}, amount=0)

    r = _post(client, _items("plan_visit", "plan_bookings"), payment_token="")
    assert r.status_code == 200, r.text
    assert plans.tokens == ["", ""]


# ── per-item may_subscribe still applies, checked before any charge ──────────────────────────
def test_a_whatsapp_only_app_refuses_the_whole_cart_unconnected(client):
    plans = _wire(client, connected=False)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_rating", limits={"feature.rating": {"limit": 1}}, amount=9900)

    r = _post(client, _items("plan_visit", "plan_rating"))
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["error"] == "WHATSAPP_CONNECTION_REQUIRED"
    assert body["plan_id"] == "plan_rating"
    assert plans.subscribed == [], "the connected item must not go through before the refusal"


def test_a_paid_item_with_no_token_refuses_before_any_charge(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_visit", "plan_pro"), payment_token="")
    assert r.status_code == 402, r.text
    assert r.json()["error"] == "PAYMENT_REQUIRED"
    assert plans.subscribed == []


def test_an_unconnected_paying_cart_still_goes_through_with_a_notice(client):
    """Paying is allowed unconnected (core/subscribe.py's own reversal) — the cart carries the
    same one-sentence notice a single purchase would, not one copy per line."""
    plans = _wire(client, connected=False)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_visit", "plan_pro"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "ربط" in body["notice"]


def test_a_connected_cart_carries_no_notice(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_visit", "plan_pro"))
    assert r.status_code == 200, r.text
    assert "notice" not in r.json()


def test_a_bad_interval_refuses_before_any_charge(client):
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=0)

    r = _post(client, [{"plan_id": "plan_pro", "interval": "forever"}], payment_token="")
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BAD_INTERVAL"
    assert plans.subscribed == []


# ── partial execution failure: no rollback, honest per-item reporting ────────────────────────
def test_a_mid_cart_billing_failure_stops_execution_and_reports_both_lines(client):
    """billing-service itself refuses the SECOND item after the first already succeeded — this
    route cannot undo the first (no refund, no cancel), so it reports exactly what happened."""
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_pro", limits=PRO, amount=9900)
    plans.refuse_plan_ids.add("plan_pro")

    r = _post(client, _items("plan_visit", "plan_pro"))
    assert r.status_code == 207, r.text
    body = r.json()
    assert body["items"][0] == {"plan_id": "plan_visit", "ok": True, "status": 201, "detail": None}
    assert body["items"][1]["plan_id"] == "plan_pro"
    assert body["items"][1]["ok"] is False
    assert body["items"][1]["status"] == 402
    # THE FIRST ITEM DID CHARGE/CREATE — this is exactly why there is no automatic rollback here.
    assert plans.subscribed == [("t_cart", "plan_visit", "once")]


def test_execution_stops_at_the_first_failure_never_attempts_the_rest(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_bookings", limits={"feature.bookings": {"limit": 1}}, amount=0)
    plans.refuse_plan_ids.add("plan_visit")

    r = _post(client, _items("plan_visit", "plan_bookings"))
    assert r.status_code == 207, r.text
    body = r.json()
    assert len(body["items"]) == 1, "the second item must never even be attempted"
    assert plans.subscribed == []


# ── outages fail closed, never charge blind ───────────────────────────────────────────────────
def test_an_unreadable_subscriptions_list_refuses_the_whole_checkout(client):
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=9900)
    plans.held = None  # "could not read", never "holds nothing"

    r = _post(client, _items("plan_pro"))
    assert r.status_code == 503, r.text
    assert r.json()["error"] == "SUBSCRIPTION_UNAVAILABLE"
    assert plans.subscribed == []


def test_an_unreadable_plan_refuses_the_whole_checkout_not_just_that_line(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    # "plan_missing" was never added to the catalog — limits() returns None for it.

    r = _post(client, _items("plan_visit", "plan_missing"))
    assert r.status_code == 503, r.text
    assert plans.subscribed == []


# ── request shape ──────────────────────────────────────────────────────────────────────────────
def test_no_tenant_cannot_check_out_anything(client):
    _wire(client, connected=True)
    r = client.post("/api/v1/subscription/checkout",
                    json={"items": _items("plan_x"), "payment_token": "tok_1"},
                    headers=_auth(tenant=""))
    assert r.status_code == 403


def test_an_empty_cart_is_rejected_at_the_request_shape_before_any_logic(client):
    _wire(client, connected=True)
    r = _post(client, [])
    assert r.status_code == 422


def test_a_cart_over_the_sanity_cap_is_rejected(client):
    _wire(client, connected=True)
    r = _post(client, _items(*[f"plan_{i}" for i in range(21)]))
    assert r.status_code == 422


def test_the_cap_boundary_itself_is_accepted(client):
    """20 is the cap, not 19 -- a boundary this precise is worth pinning exactly, not just
    'somewhere below 21'."""
    plans = _wire(client, connected=True)
    for i in range(20):
        plans.add(f"plan_{i}", limits={f"feature.f{i}": {"limit": 1}}, amount=0)
    r = _post(client, _items(*[f"plan_{i}" for i in range(20)]))
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 20


def test_a_plan_id_over_the_field_length_cap_is_rejected(client):
    _wire(client, connected=True)
    r = _post(client, [{"plan_id": "p" * 65, "interval": "month"}])
    assert r.status_code == 422


def test_an_interval_over_the_field_length_cap_is_rejected(client):
    _wire(client, connected=True)
    r = _post(client, [{"plan_id": "plan_x", "interval": "m" * 17}])
    assert r.status_code == 422


def test_a_non_string_plan_id_is_rejected_by_the_schema(client):
    _wire(client, connected=True)
    r = _post(client, [{"plan_id": 12345, "interval": "month"}])
    assert r.status_code == 422


def test_a_missing_items_field_entirely_is_rejected(client):
    _wire(client, connected=True)
    r = client.post("/api/v1/subscription/checkout", json={"payment_token": "tok_1"},
                    headers=_auth())
    assert r.status_code == 422


def test_extra_unknown_fields_in_the_payload_do_not_break_the_route(client):
    """Pydantic's default ignore-extra posture -- a client sending a forward-looking field (or a
    probe for one) must not crash the route."""
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=0)
    r = client.post(
        "/api/v1/subscription/checkout",
        json={"items": [{"plan_id": "plan_pro", "interval": "month", "quantity": 999}],
              "payment_token": "tok_1", "tenant": "someone_elses_tenant", "discount": "100%"},
        headers=_auth())
    assert r.status_code == 200, r.text
    # THE BODY'S OWN "tenant" FIELD (not a real field on the model at all) MUST HAVE NO EFFECT --
    # there is no `tenant` on CheckoutIn; the only tenant that can ever matter is the JWT's own.
    assert plans.subscribed == [("t_cart", "plan_pro", "once")]


def test_a_suspicious_plan_id_string_is_just_an_unreadable_plan_not_a_crash(client):
    """No plan_id ever reaches a query string or a shell -- billing-service's own `/plans` read is
    unconditional and this plan_id simply will not be found in it, same as any other unknown id."""
    _wire(client, connected=True)
    r = _post(client, [{"plan_id": "plan_x'; DROP TABLE subscriptions;--", "interval": "month"}])
    assert r.status_code == 503  # "unreadable plan", exactly like test_an_unreadable_plan_...


def test_the_same_plan_id_twice_with_different_intervals_is_still_a_duplicate(client):
    """The duplicate-cart-line rule is keyed on plan_id alone -- a client cannot dodge it by
    varying the interval field between the two copies."""
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=0)
    r = _post(client, [{"plan_id": "plan_pro", "interval": "month"},
                       {"plan_id": "plan_pro", "interval": "once"}])
    assert r.status_code == 409, r.text
    assert plans.subscribed == []


# ── security: auth/capability/tenant isolation ────────────────────────────────────────────────
def test_refuses_without_any_token(client):
    _wire(client, connected=True)
    r = client.post("/api/v1/subscription/checkout",
                    json={"items": _items("plan_x"), "payment_token": "tok_1"})
    assert r.status_code in (401, 403)


def test_a_malformed_bearer_token_is_refused(client):
    _wire(client, connected=True)
    r = client.post("/api/v1/subscription/checkout",
                    json={"items": _items("plan_x"), "payment_token": "tok_1"},
                    headers={"Authorization": "Bearer not.a.real.jwt"})
    assert r.status_code in (401, 403)


def test_a_capability_that_is_not_billing_self_cannot_check_out(client):
    """`_OWNER = require_capability('billing.self')` -- a token holding some OTHER real
    capability (never billing.self) must not reach the route at all."""
    _wire(client, connected=True)
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["operations.recent"],
                      "tenant": "t_cart", "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    r = client.post("/api/v1/subscription/checkout",
                    json={"items": _items("plan_x"), "payment_token": "tok_1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_an_expired_token_is_refused(client):
    _wire(client, connected=True)
    then = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": "t_cart", "exp": then, "iat": then - dt.timedelta(minutes=5)},
                     SECRET, algorithm="HS256")
    r = client.post("/api/v1/subscription/checkout",
                    json={"items": _items("plan_x"), "payment_token": "tok_1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code in (401, 403)


def test_a_token_signed_with_the_wrong_secret_is_refused(client):
    _wire(client, connected=True)
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": "t_cart", "exp": now + dt.timedelta(minutes=5), "iat": now},
                     "wrong-secret-wrong-secret-wrong-secret!", algorithm="HS256")
    r = client.post("/api/v1/subscription/checkout",
                    json={"items": _items("plan_x"), "payment_token": "tok_1"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code in (401, 403)


def test_two_different_tenants_never_cross_over_in_the_same_subscribe_calls(client):
    """There is no `tenant` field anywhere on CheckoutIn -- the tenant charged is ALWAYS the
    JWT's own claim. Two carts from two different tenants must produce subscriptions each
    stamped with its own tenant, never the other's."""
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=0)

    r1 = _post(client, _items("plan_pro"), tenant="tenant_alpha")
    assert r1.status_code == 200, r1.text
    r2 = _post(client, _items("plan_pro"), tenant="tenant_beta")
    assert r2.status_code == 200, r2.text

    assert plans.subscribed == [
        ("tenant_alpha", "plan_pro", "once"),
        ("tenant_beta", "plan_pro", "once"),
    ]
