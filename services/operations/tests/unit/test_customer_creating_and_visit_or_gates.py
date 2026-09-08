"""Customer registration must be possible "من أي تطبيق" — the owner's own decision — and recording
a visit must accept the new standalone "تسجيل زيارة" app alongside الأساس. Both doors are built on
`api.subscribed.subscribed_write_or`, the generalisation of what used to be a WhatsApp-only
`subscribed_write_or_whatsapp`; these tests exercise the generic factory itself, and the two
concrete gates it builds, through a real dependency chain — same shape as this module's WhatsApp
sibling in `test_a_lapsed_shop_reads_and_cannot_write.py`.
"""
from __future__ import annotations

import pytest

from app.core.base_licence import CANNOT_ASK, NullBaseLicence
from app.core.feature_licence import NullFeatureLicence


def _client(container_cls):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.state.container = container_cls()

    from app.api.auth import Principal, require_user

    app.dependency_overrides[require_user] = lambda: Principal(
        subject="usr_1", tenant="t1", caps=frozenset({"operations.record"}))
    return app, TestClient(app)


# ── the generic factory, on its own gate ──────────────────────────────────────────────────────

def test_subscribed_write_or_passes_when_any_named_licence_is_true():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or

    gate = subscribed_write_or("a_licence", "b_licence", refusal="لا يوجد اشتراك")

    class _Container:
        a_licence = NullBaseLicence(False)
        b_licence = NullFeatureLicence("feature.x", True)

    app, client = _client(_Container)

    @app.post("/x", dependencies=[Depends(gate)])
    async def _x() -> dict:
        return {"ok": True}

    assert client.post("/x").status_code == 200


def test_subscribed_write_or_refuses_when_every_named_licence_is_false():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or

    refusal = "لا يوجد اشتراك"
    gate = subscribed_write_or("a_licence", "b_licence", refusal=refusal)

    class _Container:
        a_licence = NullBaseLicence(False)
        b_licence = NullFeatureLicence("feature.x", False)

    app, client = _client(_Container)

    @app.post("/x", dependencies=[Depends(gate)])
    async def _x() -> dict:
        return {"ok": True}

    resp = client.post("/x")
    assert resp.status_code == 402
    assert resp.json()["detail"] == refusal


def test_subscribed_write_or_fails_closed_with_cannot_ask_when_every_answer_is_unreachable():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or

    gate = subscribed_write_or("a_licence", "b_licence", refusal="لا يوجد اشتراك")

    class _Container:
        a_licence = NullBaseLicence(None)
        b_licence = NullFeatureLicence("feature.x", None)

    app, client = _client(_Container)

    @app.post("/x", dependencies=[Depends(gate)])
    async def _x() -> dict:
        return {"ok": True}

    resp = client.post("/x")
    assert resp.status_code == 402
    assert resp.json()["detail"] == CANNOT_ASK


# ── /field/customers/ensure — the customer-creating OR ────────────────────────────────────────

def test_a_shop_holding_only_feature_contacts_may_ensure_a_customer():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or_customer_creating_app

    class _Container:
        base_licence = NullBaseLicence(False)
        contacts_licence = NullFeatureLicence("feature.contacts", True)
        bookings_licence = NullFeatureLicence("feature.bookings", False)

    app, client = _client(_Container)

    @app.post("/field/customers/ensure",
             dependencies=[Depends(subscribed_write_or_customer_creating_app)])
    async def _ensure() -> dict:
        return {"ok": True}

    assert client.post("/field/customers/ensure").status_code == 200


def test_a_shop_holding_only_feature_bookings_may_ensure_a_customer():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or_customer_creating_app

    class _Container:
        base_licence = NullBaseLicence(False)
        contacts_licence = NullFeatureLicence("feature.contacts", False)
        bookings_licence = NullFeatureLicence("feature.bookings", True)

    app, client = _client(_Container)

    @app.post("/field/customers/ensure",
             dependencies=[Depends(subscribed_write_or_customer_creating_app)])
    async def _ensure() -> dict:
        return {"ok": True}

    assert client.post("/field/customers/ensure").status_code == 200


def test_a_legacy_base_subscriber_may_still_ensure_a_customer_with_neither_new_app():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or_customer_creating_app

    class _Container:
        base_licence = NullBaseLicence(True)
        contacts_licence = NullFeatureLicence("feature.contacts", False)
        bookings_licence = NullFeatureLicence("feature.bookings", False)

    app, client = _client(_Container)

    @app.post("/field/customers/ensure",
             dependencies=[Depends(subscribed_write_or_customer_creating_app)])
    async def _ensure() -> dict:
        return {"ok": True}

    assert client.post("/field/customers/ensure").status_code == 200


def test_a_shop_holding_none_of_the_three_is_refused_ensuring_a_customer():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or_customer_creating_app

    class _Container:
        base_licence = NullBaseLicence(False)
        contacts_licence = NullFeatureLicence("feature.contacts", False)
        bookings_licence = NullFeatureLicence("feature.bookings", False)

    app, client = _client(_Container)

    @app.post("/field/customers/ensure",
             dependencies=[Depends(subscribed_write_or_customer_creating_app)])
    async def _ensure() -> dict:
        return {"ok": True}

    resp = client.post("/field/customers/ensure")
    assert resp.status_code == 402
    assert resp.json()["detail"], "the refusal must carry a sentence an owner can act on"


# ── /field/visits — the visit-recording OR ─────────────────────────────────────────────────────

def test_a_shop_holding_only_feature_visit_may_record_a_visit():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or_visit

    class _Container:
        base_licence = NullBaseLicence(False)
        visit_licence = NullFeatureLicence("feature.visit", True)

    app, client = _client(_Container)

    @app.post("/field/visits", dependencies=[Depends(subscribed_write_or_visit)])
    async def _visit() -> dict:
        return {"ok": True}

    assert client.post("/field/visits").status_code == 200


def test_a_legacy_base_subscriber_may_still_record_a_visit_with_no_visit_app():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or_visit

    class _Container:
        base_licence = NullBaseLicence(True)
        visit_licence = NullFeatureLicence("feature.visit", False)

    app, client = _client(_Container)

    @app.post("/field/visits", dependencies=[Depends(subscribed_write_or_visit)])
    async def _visit() -> dict:
        return {"ok": True}

    assert client.post("/field/visits").status_code == 200


def test_a_shop_holding_neither_base_nor_visit_is_refused_recording_a_visit():
    from fastapi import Depends

    from app.api.subscribed import subscribed_write_or_visit

    class _Container:
        base_licence = NullBaseLicence(False)
        visit_licence = NullFeatureLicence("feature.visit", False)

    app, client = _client(_Container)

    @app.post("/field/visits", dependencies=[Depends(subscribed_write_or_visit)])
    async def _visit() -> dict:
        return {"ok": True}

    resp = client.post("/field/visits")
    assert resp.status_code == 402
    assert resp.json()["detail"], "the refusal must carry a sentence an owner can act on"


# ── the real routers actually use the widened gates, not the base-only one ────────────────────

def test_field_router_uses_the_or_gates_not_base_alone():
    from app.api.subscribed import (subscribed_write_or_customer_creating_app,
                                    subscribed_write_or_visit)
    from app.api.v1.field import router

    def _deps(path: str, method: str) -> set:
        for route in router.routes:
            if route.path == path and method in route.methods:
                return {d.call for d in route.dependant.dependencies}
        raise AssertionError(f"{method} {path} is not on the router any more")

    assert subscribed_write_or_visit in _deps("/field/visits", "POST")
    assert subscribed_write_or_visit in _deps("/field/visits/{visit_id}/offer", "POST")
    assert subscribed_write_or_customer_creating_app in _deps("/field/customers/ensure", "POST")


def test_till_router_uses_the_visit_or_gate():
    from app.api.subscribed import subscribed_write_or_visit
    from app.api.v1.till import router

    def _deps(path: str, method: str) -> set:
        for route in router.routes:
            if route.path == path and method in route.methods:
                return {d.call for d in route.dependant.dependencies}
        raise AssertionError(f"{method} {path} is not on the router any more")

    assert subscribed_write_or_visit in _deps("/till/visits", "POST")
