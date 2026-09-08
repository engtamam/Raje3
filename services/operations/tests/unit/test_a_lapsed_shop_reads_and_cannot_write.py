"""When the month lapses the shop keeps its data and stops adding to it.

THE OWNER'S DECISION, IN THEIR OWN WORDS: «لما يشترك وينتهي اشتراكه يقفل النظام. القراءة تبقى والكتابة تقف.
واللي يفعله يشتغل معاه.» — and the second sentence is as load-bearing as the first: this answers
for `feature.base` alone, so an app he still pays for keeps working while the base is lapsed.

WHAT WAS TRUE BEFORE THIS FILE. Nothing anywhere asked. `feature.api`, `feature.campaigns`,
`feature.loyalty` and `feature.insights.engine` each had a licence; the 99-a-month product that
every shop actually buys — the visit register — had none, and the cluster held no `subscriptions`
row at all while every shop on it recorded visits.

THE THREE ANSWERS, AND THE THIRD IS WHY THIS IS NOT A BOOLEAN. Billing says yes, says no, or
cannot be reached. A shop that never subscribed and a shop we could not ask about are two
different problems and get two different sentences — telling a paying shop it has not paid is the
worse of the two mistakes, so it is never phrased as the first.
"""
from __future__ import annotations

import pytest

from app.core.base_licence import CANNOT_ASK, LAPSED, LicenceError, NullBaseLicence


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_a_live_subscription_lets_the_write_through():
    _run(NullBaseLicence(True).require_write("t1"))   # no raise is the assertion


def test_a_lapsed_month_refuses_the_write_and_says_the_data_is_safe():
    with pytest.raises(LicenceError) as caught:
        _run(NullBaseLicence(False).require_write("t1"))
    assert caught.value.message == LAPSED
    assert caught.value.reachable is True
    # THE SENTENCE NAMES WHAT STILL WORKS. A screen that only says «انتهى» leaves an owner
    # wondering whether his customers are gone with it, and that fear is what makes him call us
    # instead of pressing renew.
    assert "محفوظة" in LAPSED and "اشتراكي" in LAPSED


def test_an_unreachable_billing_refuses_with_a_different_sentence():
    with pytest.raises(LicenceError) as caught:
        _run(NullBaseLicence(None).require_write("t1"))
    assert caught.value.message == CANNOT_ASK
    assert caught.value.reachable is False
    # NOT THE LAPSED SENTENCE. Telling a paying shop it has not paid is a different wrong from
    # telling an unpaid one the truth, and the two must never share a string.
    assert CANNOT_ASK != LAPSED


def test_the_licence_answers_for_the_base_alone():
    from app.core import base_licence, licence

    # PER APP, NOT PER ACCOUNT. If these two keys ever converge, a lapsed base would take the
    # programmatic link down with it — and «واللي يفعله يشتغل معاه» would stop being true.
    assert base_licence.KEY == "feature.base"
    assert licence.KEY == "feature.api"
    assert base_licence.KEY != licence.KEY


# ── The chain, not the mechanism ────────────────────────────────────────────────────────────────
#
# THE TESTS ABOVE PROVE THE LICENCE ANSWERS. These prove it is ASKED — which is the half that was
# missing for the whole life of the product, and the half a unit test of a helper can never see.

def test_the_refusal_reaches_the_caller_as_402_with_the_owners_sentence():
    """Dependency → licence → HTTP. 402, never 403: he is not forbidden, he is unsubscribed."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write

    app = FastAPI()

    class _Container:
        base_licence = NullBaseLicence(False)

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
    assert resp.status_code == 402, "a lapsed shop was allowed to write"
    assert resp.json()["detail"] == LAPSED


# ── the WhatsApp connect routes, which serve TWO different buyers ────────────────────────────
#
# "واتساب الذكي (مستقل)" holds no base at all, by design — so the connect routes must accept
# EITHER licence, not base alone. These tests exercise `subscribed_write_or_whatsapp` the same
# way the tests above exercise `subscribed_write`: through a real dependency chain, not the
# licence object directly.
def test_a_standalone_whatsapp_subscriber_may_connect_with_no_base_at_all():
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write_or_whatsapp
    from app.core.whatsapp_licence import NullWhatsappLicence

    app = FastAPI()

    class _Container:
        base_licence = NullBaseLicence(False)          # no base at all
        whatsapp_licence = NullWhatsappLicence(True)    # holds the standalone plan

    app.state.container = _Container()

    @app.post("/whatsapp/connect", dependencies=[Depends(subscribed_write_or_whatsapp)])
    async def _connect() -> dict:
        return {"ok": True}

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"billing.self"}))

    resp = TestClient(app).post("/whatsapp/connect")
    assert resp.status_code == 200, resp.text


def test_a_shop_holding_neither_licence_is_still_refused():
    """This widens WHICH purchase counts — it does not exempt WhatsApp from needing one at all."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write_or_whatsapp
    from app.core.whatsapp_licence import NullWhatsappLicence

    app = FastAPI()

    class _Container:
        base_licence = NullBaseLicence(False)
        whatsapp_licence = NullWhatsappLicence(False)

    app.state.container = _Container()

    @app.post("/whatsapp/connect", dependencies=[Depends(subscribed_write_or_whatsapp)])
    async def _connect() -> dict:
        return {"ok": True}

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"billing.self"}))

    resp = TestClient(app).post("/whatsapp/connect")
    assert resp.status_code == 402


def test_an_ordinary_base_subscriber_may_still_connect_with_no_whatsapp_plan_at_all():
    """No regression: today's only real buyer (a base subscriber with no standalone plan) keeps
    working exactly as before."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.subscribed import subscribed_write_or_whatsapp
    from app.core.whatsapp_licence import NullWhatsappLicence

    app = FastAPI()

    class _Container:
        base_licence = NullBaseLicence(True)
        whatsapp_licence = NullWhatsappLicence(False)

    app.state.container = _Container()

    @app.post("/whatsapp/connect", dependencies=[Depends(subscribed_write_or_whatsapp)])
    async def _connect() -> dict:
        return {"ok": True}

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"billing.self"}))

    resp = TestClient(app).post("/whatsapp/connect")
    assert resp.status_code == 200, resp.text


def test_connect_routes_use_the_widened_dependency_not_the_base_only_one():
    from app.api.subscribed import subscribed_write_or_whatsapp
    from app.api.v1.connect import router

    def _deps(path: str, method: str) -> set:
        for route in router.routes:
            if route.path == path and method in route.methods:
                return {d.call for d in route.dependant.dependencies}
        raise AssertionError(f"{method} {path} is not on the router any more")

    assert subscribed_write_or_whatsapp in _deps("/whatsapp/connect", "POST")
    assert subscribed_write_or_whatsapp in _deps("/whatsapp/connect/register", "POST")


def test_recording_a_visit_asks_the_subscription_and_erasing_a_customer_does_not():
    """THE TWO SIDES OF THE LINE, read off the real routes rather than from a description of them.

    Recording a visit grows the shop's data and needs the month paid. Erasing a customer is the
    CUSTOMER's right under PDPL, and a late invoice does not suspend the law.
    """
    from app.api.subscribed import no_subscription_needed, subscribed_write
    from app.api.v1.field import router

    def _deps(path: str, method: str) -> set:
        for route in router.routes:
            if route.path == path and method in route.methods:
                return {d.call for d in route.dependant.dependencies}
        raise AssertionError(f"{method} {path} is not on the router any more")

    assert subscribed_write in _deps("/field/visits", "POST")
    assert no_subscription_needed in _deps("/field/customers/{customer_id}/erase", "POST")
