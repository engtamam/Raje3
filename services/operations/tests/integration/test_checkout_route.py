"""POST /api/v1/subscription/checkout — buy several apps together, one invoice, one charge.

The whole reason this route exists: `may_add`'s own `plan.requires_any` gate only ever checked
`held` — what a shop already owns from an earlier, SEPARATE purchase — so a dependency and the
app that needs it could never be bought in one action. This route validates a whole cart together
(`may_add_bundle`, plus the same per-item `may_subscribe` gate a single purchase uses), then
executes the cart in ONE atomic call to billing-service's own multi-plan checkout
(`HttpPlans.checkout` -> `POST /internal/billing/subscriptions/checkout`, base-services v0.25.25):
one invoice, one charge, all-or-nothing. There is no partial cart and no "at most one paid item"
restriction any more — both existed only because this route used to loop billing's single-plan
`subscribe` route itself; see git history for that earlier shape.
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
        self.checkout_calls: list[dict] = []
        # billing-service itself refuses the WHOLE cart on checkout() when any of these plan_ids
        # is present — the atomic route's own all-or-nothing contract, unlike the old per-item
        # `refuse_plan_ids` that let earlier lines charge before a later one failed.
        self.refuse_plan_ids: set[str] = set()

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

    async def checkout(self, *, tenant: str, items: list[dict], payment_token: str = "",
                       idempotency_key: str = ""):
        self.tokens.append(payment_token)
        self.checkout_calls.append({
            "tenant": tenant, "items": list(items),
            "payment_token": payment_token, "idempotency_key": idempotency_key,
        })
        if any(i["plan_id"] in self.refuse_plan_ids for i in items):
            # ATOMIC MEANS NOTHING CHARGES — unlike the old per-item loop, a refused cart leaves
            # no trace in `self.subscribed` at all, whichever line billing refused.
            return 402, {"error": "CARD_DECLINED", "message": "بطاقة مرفوضة"}
        for i in items:
            self.subscribed.append((tenant, i["plan_id"], i["interval"]))
        total = sum(int(self.catalog.get(i["plan_id"], {}).get("amount") or 0) for i in items)
        return 201, {
            "tenant": tenant, "invoice_id": "inv_1", "paid": bool(payment_token),
            "currency": "SAR", "total_minor": total,
            "items": [{"plan_id": i["plan_id"], "subscription_id": f"sub_{i['plan_id']}",
                      "status": "active", "interval": i["interval"]} for i in items],
        }


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
    because both travel in the same cart, in ONE atomic invoice."""
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)  # free
    plans.add("plan_loyalty", limits=LOYALTY, amount=9900)  # paid

    r = _post(client, _items("plan_visit", "plan_loyalty"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert [i["plan_id"] for i in body["items"]] == ["plan_visit", "plan_loyalty"]
    assert body["invoice_id"] == "inv_1"
    assert plans.subscribed == [
        ("t_cart", "plan_visit", "once"),  # free, subscribed once not monthly
        ("t_cart", "plan_loyalty", "month"),
    ]
    # ONE CALL, THE WHOLE CART — not one call per item.
    assert len(plans.checkout_calls) == 1
    assert plans.checkout_calls[0]["payment_token"] == "tok_1"


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
    assert plans.checkout_calls == [], "billing must never even be called on a refused bundle"


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


# ── the atomic invoice: several paid items together, all-or-nothing ─────────────────────────
def test_two_real_paid_items_check_out_together_in_one_invoice(client):
    """The old per-item loop refused this outright (a single-use token could not safely cover two
    charge attempts). The atomic route makes only ONE charge attempt for the whole cart, so this
    is now simply allowed."""
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=9900)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_visit", "plan_pro"))
    assert r.status_code == 200, r.text
    assert len(plans.checkout_calls) == 1
    assert plans.checkout_calls[0]["items"] == [
        {"plan_id": "plan_visit", "interval": "month"},
        {"plan_id": "plan_pro", "interval": "month"},
    ]
    assert plans.subscribed == [
        ("t_cart", "plan_visit", "month"),
        ("t_cart", "plan_pro", "month"),
    ]


def test_one_paid_item_with_several_free_items_is_allowed(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_bookings", limits={"feature.bookings": {"limit": 1}}, amount=0)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_visit", "plan_bookings", "plan_pro"))
    assert r.status_code == 200, r.text
    assert len(plans.subscribed) == 3


def test_all_free_items_need_no_payment_token_at_all(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_bookings", limits={"feature.bookings": {"limit": 1}}, amount=0)

    r = _post(client, _items("plan_visit", "plan_bookings"), payment_token="")
    assert r.status_code == 200, r.text
    assert plans.tokens == [""]


def test_billing_refusing_the_atomic_checkout_leaves_nothing_subscribed(client):
    """The atomic contract: billing-service refuses (or fails to charge) the WHOLE cart as one
    unit, so unlike the old per-item loop there is no first item left charged while a later one
    fails — either the whole invoice goes through or nothing does."""
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_pro", limits=PRO, amount=9900)
    plans.refuse_plan_ids.add("plan_pro")

    r = _post(client, _items("plan_visit", "plan_pro"))
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "CHECKOUT_FAILED"
    assert plans.subscribed == [], "an atomic refusal must leave no line charged"
    assert len(plans.checkout_calls) == 1, "still exactly one attempt, not one per item"


def test_checkout_forwards_the_idempotency_key_to_billing(client):
    """A double-tap or a resent network request must replay the same invoice — the key is
    forwarded verbatim, never invented or dropped on this side."""
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = client.post("/api/v1/subscription/checkout",
                    json={"items": _items("plan_pro"), "payment_token": "tok_1",
                          "idempotency_key": "idem_abc123"},
                    headers=_auth())
    assert r.status_code == 200, r.text
    assert plans.checkout_calls[0]["idempotency_key"] == "idem_abc123"


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
    assert plans.checkout_calls == []


def test_a_paid_item_with_no_token_refuses_before_any_charge(client):
    plans = _wire(client, connected=True)
    plans.add("plan_visit", limits=VISIT, amount=0)
    plans.add("plan_pro", limits=PRO, amount=9900)

    r = _post(client, _items("plan_visit", "plan_pro"), payment_token="")
    assert r.status_code == 402, r.text
    assert r.json()["error"] == "PAYMENT_REQUIRED"
    assert plans.subscribed == []
    assert plans.checkout_calls == []


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


def test_a_billing_outage_on_the_atomic_call_itself_is_reported_as_a_gateway_failure(client):
    """`HttpPlans.checkout` returns 503 when billing-service is simply unreachable — never a 409,
    which would read as "the cart was refused" rather than "we could not even ask"."""
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=9900)

    async def _unreachable(self, *, tenant, items, payment_token="", idempotency_key=""):
        return 503, {"error": "BILLING_UNREACHABLE"}

    plans.checkout = _unreachable.__get__(plans, FakePlans)
    r = _post(client, _items("plan_pro"))
    assert r.status_code == 502, r.text
    assert r.json()["error"] == "CHECKOUT_FAILED"


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


def test_two_different_tenants_never_cross_over_in_the_same_checkout_calls(client):
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


# ── the read-only price preview: never creates, never charges ────────────────────────────────
def _post_preview(client, items, tenant="t_cart"):
    return client.post("/api/v1/subscription/checkout/preview",
                       json={"items": items}, headers=_auth(tenant))


def test_preview_returns_billings_own_totals_untouched(client):
    plans = _wire(client, connected=True)
    plans.add("plan_pro", limits=PRO, amount=9900)

    async def _preview(self, *, tenant, items):
        return 200, {"currency": "SAR", "subtotal_minor": 9900, "discount_minor": 0,
                    "tax_minor": 0, "total_minor": 9900,
                    "items": [{"plan_id": "plan_pro", "interval": "month", "charged_now": True,
                              "on_trial": False, "subtotal_minor": 9900, "discount_minor": 0,
                              "tax_minor": 0, "total_minor": 9900, "prorated": False}]}

    plans.checkout_preview = _preview.__get__(plans, FakePlans)
    r = _post_preview(client, _items("plan_pro"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_minor"] == 9900
    assert body["items"][0]["plan_id"] == "plan_pro"
    # NEVER CHARGES OR SUBSCRIBES ANYTHING — the whole point of a preview.
    assert plans.subscribed == []
    assert plans.checkout_calls == []


def test_preview_does_not_require_a_purchasable_bundle(client):
    """No `may_add_bundle` check on preview -- a live total must keep updating even before the
    cart is a legally checkout-able set (see the route's own docstring)."""
    plans = _wire(client, connected=True)
    plans.add("plan_loyalty", limits=LOYALTY, amount=9900)  # its dependency is NOT in this cart

    async def _preview(self, *, tenant, items):
        return 200, {"currency": "SAR", "subtotal_minor": 9900, "discount_minor": 0,
                    "tax_minor": 0, "total_minor": 9900, "items": []}

    plans.checkout_preview = _preview.__get__(plans, FakePlans)
    r = _post_preview(client, _items("plan_loyalty"))
    assert r.status_code == 200, r.text


def test_preview_propagates_billings_own_refusal(client):
    plans = _wire(client, connected=True)

    async def _preview(self, *, tenant, items):
        return 422, {"error": "PLAN_NOT_FOUND"}

    plans.checkout_preview = _preview.__get__(plans, FakePlans)
    r = _post_preview(client, _items("plan_ghost"))
    assert r.status_code == 422, r.text
    assert r.json()["error"] == "PREVIEW_UNAVAILABLE"


def test_preview_reports_an_outage_as_a_gateway_failure(client):
    plans = _wire(client, connected=True)

    async def _preview(self, *, tenant, items):
        return 503, {"error": "BILLING_UNREACHABLE"}

    plans.checkout_preview = _preview.__get__(plans, FakePlans)
    r = _post_preview(client, _items("plan_pro"))
    assert r.status_code == 502, r.text


def test_preview_requires_billing_self_same_as_checkout(client):
    _wire(client, connected=True)
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["operations.recent"],
                      "tenant": "t_cart", "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    r = client.post("/api/v1/subscription/checkout/preview", json={"items": _items("plan_x")},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_preview_with_no_tenant_is_refused(client):
    _wire(client, connected=True)
    r = client.post("/api/v1/subscription/checkout/preview", json={"items": _items("plan_x")},
                    headers=_auth(tenant=""))
    assert r.status_code == 403


def test_preview_with_an_empty_cart_is_rejected_at_the_request_shape(client):
    _wire(client, connected=True)
    r = _post_preview(client, [])
    assert r.status_code == 422
