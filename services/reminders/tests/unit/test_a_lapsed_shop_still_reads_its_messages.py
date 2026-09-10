"""A lapsed month stops the owner editing his messages and never stops his customer leaving.

MESSAGING IS A FEATURE OF THE EVENT-RECORDING APP, NOT ITS OWN PRODUCT (2026-09-10, retiring
الأساس) — so the owner may edit his schedules and wordings the moment he owns EITHER `feature.visit`
or `feature.bookings`, and stops the moment he owns neither. «القراءة تبقى والكتابة تقف» either way:
when both lapse the owner can still open «رسائلي» and read every schedule, every rule and every
wording, and can change none of them until he renews one of the two.

AND ONE LINE THAT IS NOT OURS TO SUSPEND. `prefs.py` is the customer's own switch, reached from a
link at the end of a message he did not ask for. If a lapsed subscription refused it, a person
trying to stop our messages would be told, in effect, to go and ask the shop to pay its bill
first. That is the law's line, not a courtesy, and it is why the exemption is declared on the
route rather than remembered.
"""
from __future__ import annotations

from app.core.feature_licence import NullFeatureLicence


def _client(container_cls):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.state.container = container_cls()

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"reminders.manage"}))
    return app, TestClient(app)


def test_owning_either_app_lets_the_owner_edit():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write

    class _Container:
        visit_licence = NullFeatureLicence("feature.visit", True)
        bookings_licence = NullFeatureLicence("feature.bookings", False)

    app, client = _client(_Container)

    @app.post("/x", dependencies=[Depends(subscribed_write)])
    async def _x() -> dict:
        return {"ok": True}

    assert client.post("/x").status_code == 200


def test_owning_neither_refuses_and_an_outage_refuses_differently():
    from fastapi import Depends

    from app.api.subscribed import CANNOT_ASK, subscribed_write

    class _Refused:
        visit_licence = NullFeatureLicence("feature.visit", False)
        bookings_licence = NullFeatureLicence("feature.bookings", False)

    class _Outage:
        visit_licence = NullFeatureLicence("feature.visit", None)
        bookings_licence = NullFeatureLicence("feature.bookings", None)

    for container_cls, expect in ((_Refused, "refusal"), (_Outage, CANNOT_ASK)):
        app, client = _client(container_cls)

        @app.post("/x", dependencies=[Depends(subscribed_write)])
        async def _x() -> dict:
            return {"ok": True}

        resp = client.post("/x")
        assert resp.status_code == 402
        if expect == CANNOT_ASK:
            assert resp.json()["detail"] == CANNOT_ASK
        else:
            assert resp.json()["detail"], "the refusal must carry a sentence an owner can act on"


def test_editing_a_wording_asks_the_subscription_and_a_customer_opting_out_never_does():
    """READ OFF THE REAL ROUTERS. The two sides of the line, as the code states them."""
    from app.api.subscribed import no_subscription_needed, subscribed_write
    from app.api.v1.owner import router as owner
    from app.api.v1.prefs import router as prefs

    def _deps(router, path: str, method: str) -> set:
        for route in router.routes:
            if route.path == path and method in route.methods:
                return {d.call for d in route.dependant.dependencies}
        raise AssertionError(f"{method} {path} is not on the router any more")

    assert subscribed_write in _deps(owner, "/reminders/templates", "POST")
    # THE CUSTOMER'S SWITCH. Never gated, and the assertion is the strong one — not «it is not
    # required» but «it is declared exempt», so removing the declaration fails here too.
    assert no_subscription_needed in _deps(prefs, "/prefs/{ref}", "PUT")
    assert subscribed_write not in _deps(prefs, "/prefs/{ref}", "PUT")
