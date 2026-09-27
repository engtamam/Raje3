"""When the month lapses the shop keeps its data and stops adding to it.

THE OWNER'S DECISION, IN THEIR OWN WORDS: «لما يشترك وينتهي اشتراكه يقفل النظام. القراءة تبقى والكتابة تقف.
واللي يفعله يشتغل معاه.» — and the second sentence is as load-bearing as the first: PER APP, NOT
PER ACCOUNT. الأساس (the old bundle) is retired entirely (2026-09-10) — every app now answers for
itself alone, through `core/feature_licence.py`'s one shared implementation, so a shop whose
visit-registration app lapsed keeps its still-paid loyalty app working.

THE THREE ANSWERS, AND THE THIRD IS WHY THIS IS NOT A BOOLEAN. Billing says yes, says no, or
cannot be reached. A shop that never subscribed and a shop we could not ask about are two
different problems and get two different sentences — telling a paying shop it has not paid is the
worse of the two mistakes, so it is never phrased as the first.
"""
from __future__ import annotations

import pytest

from app.core.feature_licence import NullFeatureLicence


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_a_live_subscription_answers_true():
    assert _run(NullFeatureLicence("feature.visit", True).allowed("t1")) is True


def test_a_lapsed_app_answers_false():
    assert _run(NullFeatureLicence("feature.visit", False).allowed("t1")) is False


def test_an_unreachable_billing_answers_none():
    # NOT False — a shop we could not ask about is a different problem from one that never
    # subscribed, and `subscribed_write_or`'s own gate (below) turns each into a different sentence.
    assert _run(NullFeatureLicence("feature.visit", None).allowed("t1")) is None


def test_each_app_carries_its_own_key():
    from app.core import licence

    # PER APP, NOT PER ACCOUNT. If these two keys ever converge, a lapsed visit app would take the
    # programmatic link down with it — and «واللي يفعله يشتغل معاه» would stop being true.
    assert NullFeatureLicence("feature.visit").key == "feature.visit"
    assert licence.KEY == "feature.api"


# ── The chain, not the mechanism ────────────────────────────────────────────────────────────────
#
# THE TESTS ABOVE PROVE THE LICENCE ANSWERS. These prove it is ASKED — which is the half a unit
# test of a helper can never see.

def test_the_refusal_reaches_the_caller_as_402_with_a_sentence():
    """Dependency → OR of licences → HTTP. 402, never 403: he is not forbidden, he is unsubscribed."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write

    app = FastAPI()

    class _Container:
        visit_licence = NullFeatureLicence("feature.visit", False)
        bookings_licence = NullFeatureLicence("feature.bookings", False)
        contacts_licence = NullFeatureLicence("feature.contacts", False)
        whatsapp_licence = NullFeatureLicence("feature.whatsapp", False)
        campaigns_licence = NullFeatureLicence("feature.campaigns", False)
        loyalty_licence = NullFeatureLicence("feature.loyalty", False)
        rating_licence = NullFeatureLicence("feature.rating", False)
        insights_engine_licence = NullFeatureLicence("feature.insights.engine", False)
        partner_loyalty_licence = NullFeatureLicence("feature.partner_loyalty", False)
        mobile_requests_licence = NullFeatureLicence("feature.mobile_requests", False)
        mutual_benefit_licence = NullFeatureLicence("feature.mutual_benefit", False)
        mobile_ai_assistant_licence = NullFeatureLicence("feature.mobile_ai_assistant", False)
        coworking_licence = NullFeatureLicence("feature.coworking", False)

    app.state.container = _Container()

    @app.post("/visits", dependencies=[Depends(subscribed_write)])
    async def _record() -> dict:
        return {"ok": True}

    # The door's own identity check is not what is under test here, so the principal is supplied
    # directly — the question is what the SUBSCRIPTION dependency does once it has one.
    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"operations.record"}))

    resp = TestClient(app).post("/visits")
    assert resp.status_code == 402, "a shop holding no paid app at all was allowed to write"
    assert resp.json()["detail"]


def test_owning_any_one_app_is_enough_for_the_generic_gate():
    """`subscribed_write` no longer answers for one bundle — it is an OR across every standalone
    app, exactly like `subscribed_write_or_visit`/`_or_whatsapp` below, just wider."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write

    app = FastAPI()

    class _Container:
        visit_licence = NullFeatureLicence("feature.visit", False)
        bookings_licence = NullFeatureLicence("feature.bookings", True)   # the one that's live
        contacts_licence = NullFeatureLicence("feature.contacts", False)
        whatsapp_licence = NullFeatureLicence("feature.whatsapp", False)
        campaigns_licence = NullFeatureLicence("feature.campaigns", False)
        loyalty_licence = NullFeatureLicence("feature.loyalty", False)
        rating_licence = NullFeatureLicence("feature.rating", False)
        insights_engine_licence = NullFeatureLicence("feature.insights.engine", False)
        partner_loyalty_licence = NullFeatureLicence("feature.partner_loyalty", False)
        mobile_requests_licence = NullFeatureLicence("feature.mobile_requests", False)

    app.state.container = _Container()

    @app.post("/staff/mode", dependencies=[Depends(subscribed_write)])
    async def _write() -> dict:
        return {"ok": True}

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"operations.manage"}))

    resp = TestClient(app).post("/staff/mode")
    assert resp.status_code == 200, resp.text


def test_a_shop_holding_only_coupons_is_not_wrongly_refused_the_generic_gate():
    """`_ANY_APP` used to be a hand-typed tuple of container attribute names that stopped tracking
    `core/apps.py::APPS` the day a new standalone app shipped without also being copied in here —
    `feature.partner_loyalty`, `feature.insights.engine` and `feature.mobile_requests` are each a real,
    separately-priced app with no other app required underneath it, yet none of their attribute
    names were in the old tuple. A shop holding ONLY one of them (nothing else) would fail this
    generic "do you own any app at all" gate on an ordinary write — staff, branches, an offer
    redeemed — despite genuinely paying for a real app every month.

    `subscribed_write`'s OR is now BUILT FROM `core/apps.py::KEYS`, the same list that decides what
    the console renders and what `ci/check_listed_apps_are_wired.py` checks against the price
    list — so a shop holding only `feature.partner_loyalty` reaches this test the same way a shop holding
    only `feature.bookings` always has.
    """
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write

    app = FastAPI()

    class _Container:
        visit_licence = NullFeatureLicence("feature.visit", False)
        bookings_licence = NullFeatureLicence("feature.bookings", False)
        contacts_licence = NullFeatureLicence("feature.contacts", False)
        whatsapp_licence = NullFeatureLicence("feature.whatsapp", False)
        campaigns_licence = NullFeatureLicence("feature.campaigns", False)
        loyalty_licence = NullFeatureLicence("feature.loyalty", False)
        rating_licence = NullFeatureLicence("feature.rating", False)
        insights_engine_licence = NullFeatureLicence("feature.insights.engine", False)
        mobile_requests_licence = NullFeatureLicence("feature.mobile_requests", False)
        partner_loyalty_licence = NullFeatureLicence("feature.partner_loyalty", True)   # the one that's live

    app.state.container = _Container()

    @app.post("/staff/mode", dependencies=[Depends(subscribed_write)])
    async def _write() -> dict:
        return {"ok": True}

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"operations.manage"}))

    resp = TestClient(app).post("/staff/mode")
    assert resp.status_code == 200, resp.text


# ── the WhatsApp connect routes, which serve TWO different buyers ────────────────────────────
#
# "واتساب الذكي" is its own standalone app — the connect routes ask `whatsapp_licence` alone
# (`subscribed_write_or_whatsapp`, a one-member OR kept for its clearer name at the call site).
def test_a_whatsapp_subscriber_may_connect():
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write_or_whatsapp

    app = FastAPI()

    class _Container:
        whatsapp_licence = NullFeatureLicence("feature.whatsapp", True)

    app.state.container = _Container()

    @app.post("/whatsapp/connect", dependencies=[Depends(subscribed_write_or_whatsapp)])
    async def _connect() -> dict:
        return {"ok": True}

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"billing.self"}))

    resp = TestClient(app).post("/whatsapp/connect")
    assert resp.status_code == 200, resp.text


def test_a_shop_holding_no_whatsapp_plan_is_refused_connecting():
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write_or_whatsapp

    app = FastAPI()

    class _Container:
        whatsapp_licence = NullFeatureLicence("feature.whatsapp", False)

    app.state.container = _Container()

    @app.post("/whatsapp/connect", dependencies=[Depends(subscribed_write_or_whatsapp)])
    async def _connect() -> dict:
        return {"ok": True}

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"billing.self"}))

    resp = TestClient(app).post("/whatsapp/connect")
    assert resp.status_code == 402


def test_connect_routes_need_no_subscription_at_all():
    """CORRECTED 2026-09-20: connecting a WhatsApp number is not gated on any subscription —
    this file's own header docstring says so, and `subscribed_write_or_whatsapp` on these routes
    was a real bug (a shop with zero subscriptions could not connect). Meta provisioning itself
    stays scoped to `feature.whatsapp` via an explicit in-body check — see connect.py."""
    from app.api.subscribed import no_subscription_needed
    from app.api.v1.connect import router

    def _deps(path: str, method: str) -> set:
        for route in router.routes:
            if route.path == path and method in route.methods:
                return {d.call for d in route.dependant.dependencies}
        raise AssertionError(f"{method} {path} is not on the router any more")

    assert no_subscription_needed in _deps("/whatsapp/connect", "POST")
    assert no_subscription_needed in _deps("/whatsapp/connect/register", "POST")


def test_recording_a_visit_asks_the_subscription_and_erasing_a_customer_does_not():
    """THE TWO SIDES OF THE LINE, read off the real routes rather than from a description of them.

    Recording a visit grows the shop's data and needs the month paid. Erasing a customer is the
    CUSTOMER's right under PDPL, and a late invoice does not suspend the law.
    """
    from app.api.subscribed import no_subscription_needed, subscribed_write_or_visit
    from app.api.v1.field import router

    def _deps(path: str, method: str) -> set:
        for route in router.routes:
            if route.path == path and method in route.methods:
                return {d.call for d in route.dependant.dependencies}
        raise AssertionError(f"{method} {path} is not on the router any more")

    assert subscribed_write_or_visit in _deps("/field/visits", "POST")
    assert no_subscription_needed in _deps("/field/customers/{customer_id}/erase", "POST")
