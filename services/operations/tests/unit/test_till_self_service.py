"""The till's own self-service doors (2026-09-14, both till-integration audits' own
recommendation): `GET /till/branches` and `GET /till/status`.
"""
from __future__ import annotations

import asyncio
import types

from app.adapters.datastore.memory import MemoryDataStore
from app.api.v1 import till as till_routes
from app.core.models import Branch
from app.core.stores import BranchStore

SALT = "s" * 32
TENANT = "t_1"


def run(c):
    return asyncio.run(c)


class _Principal:
    def __init__(self, tenant: str = TENANT, subject: str = "svc_pos") -> None:
        self.tenant = tenant
        self.subject = subject
        self.raw: dict = {}


class _Settings:
    PII_SALT = SALT


class _Ops:
    def __init__(self, *, customer=None) -> None:
        self._customer = customer

    async def customer_by_phone(self, tenant, phone):
        return self._customer

    async def customer_by_plate(self, tenant, plate):
        return self._customer

    async def known_branches(self, tenant):
        return {"brn-main"}


class _Customer:
    def __init__(self, subject_ref="sub_1"):
        self.id = "cus_1"
        self.subject_ref = subject_ref


class _Licence:
    def __init__(self, answer):
        self._answer = answer

    async def allowed(self, tenant):
        return self._answer


def _request(store, *, ops=None, api_licence=None, visit_licence=None) -> types.SimpleNamespace:
    class _Auditor:
        def __init__(self):
            self.calls = []

        async def record(self, action, **kw):
            self.calls.append((action, kw))

    container = types.SimpleNamespace(
        operations=ops or _Ops(), datastore=store, api_licence=api_licence,
        visit_licence=visit_licence, loyalty_desk=None, bookings_desk=None,
        reminders_desk=None)
    state = types.SimpleNamespace(container=container, container_settings=_Settings(),
                                  auditor=_Auditor())
    return types.SimpleNamespace(app=types.SimpleNamespace(state=state), client=None)


# ── GET /till/branches ────────────────────────────────────────────────────────────────────────

def test_branches_lists_only_active_ones():
    store = MemoryDataStore()
    bs = BranchStore(store)
    run(bs.save(Branch(id="brn-a", tenant=TENANT, name="فرع أ", active=True)))
    run(bs.save(Branch(id="brn-b", tenant=TENANT, name="فرع ب", active=False)))
    req = _request(store)
    out = run(till_routes.branches_at_the_counter(req, principal=_Principal()))
    ids = {b["id"] for b in out["branches"]}
    assert "brn-a" in ids and "brn-main" in ids   # ensure_main always exists
    assert "brn-b" not in ids


def test_branches_with_no_tenant_answers_an_empty_list():
    req = _request(MemoryDataStore())
    out = run(till_routes.branches_at_the_counter(req, principal=_Principal(tenant="")))
    assert out == {"branches": []}


# ── GET /till/status ──────────────────────────────────────────────────────────────────────────

def test_status_reports_active_entitlements_and_the_full_floor():
    from app.core.till_budget import FLOOR
    req = _request(MemoryDataStore(), api_licence=_Licence(True), visit_licence=_Licence(True))
    out = run(till_routes.status_at_the_counter(req, principal=_Principal()))
    assert out["feature_api"] == "active"
    assert out["feature_visit"] == "active"
    assert out["lookup_allowance_remaining_today"] == FLOOR


def test_status_reports_unknown_for_an_unreachable_licence_peer():
    req = _request(MemoryDataStore(), api_licence=_Licence(None), visit_licence=_Licence(None))
    out = run(till_routes.status_at_the_counter(req, principal=_Principal()))
    assert out["feature_api"] == "unknown"
    assert out["feature_visit"] == "unknown"


def test_status_reports_inactive_for_a_definite_no():
    req = _request(MemoryDataStore(), api_licence=_Licence(False), visit_licence=_Licence(True))
    out = run(till_routes.status_at_the_counter(req, principal=_Principal()))
    assert out["feature_api"] == "inactive"


# ── POST /till/rating-request ────────────────────────────────────────────────────────────────

class _RemindersDesk:
    configured = True

    def __init__(self, answer):
        self._answer = answer
        self.calls: list = []

    async def expedite_rating_request(self, tenant, subject_ref, *, asset_id=""):
        self.calls.append((tenant, subject_ref, asset_id))
        return self._answer


def _rating_request(store, *, ops=None, reminders_desk=None):
    container = types.SimpleNamespace(operations=ops or _Ops(customer=_Customer()),
                                      datastore=store, reminders_desk=reminders_desk)
    state = types.SimpleNamespace(container=container)
    return types.SimpleNamespace(app=types.SimpleNamespace(state=state), client=None)


def test_rating_request_expedites_via_the_real_subject_ref():
    desk = _RemindersDesk({"ok": True})
    req = _rating_request(MemoryDataStore(), ops=_Ops(customer=_Customer(subject_ref="sub_9")),
                          reminders_desk=desk)
    out = run(till_routes.rating_request_at_the_counter(
        req, till_routes.TillRatingRequestIn(phone="0500000000"), principal=_Principal()))
    assert out["ok"] is True
    assert desk.calls == [(TENANT, "sub_9", "")]


def test_rating_request_with_nothing_scheduled_is_refused_clearly():
    desk = _RemindersDesk({"ok": False, "reason": "لا يوجد طلب مجدول"})
    req = _rating_request(MemoryDataStore(), reminders_desk=desk)
    out = run(till_routes.rating_request_at_the_counter(
        req, till_routes.TillRatingRequestIn(phone="0500000000"), principal=_Principal()))
    assert out == {"ok": False, "message": "لا يوجد طلب مجدول"}


def test_rating_request_with_no_customer_never_calls_reminders():
    desk = _RemindersDesk({"ok": True})
    req = _rating_request(MemoryDataStore(), ops=_Ops(customer=None), reminders_desk=desk)
    out = run(till_routes.rating_request_at_the_counter(
        req, till_routes.TillRatingRequestIn(phone="0500000000"), principal=_Principal()))
    assert out["ok"] is False
    assert desk.calls == []


def test_rating_request_when_the_peer_is_unreachable_says_so():
    req = _rating_request(MemoryDataStore(), reminders_desk=None)
    out = run(till_routes.rating_request_at_the_counter(
        req, till_routes.TillRatingRequestIn(phone="0500000000"), principal=_Principal()))
    assert out["ok"] is False
