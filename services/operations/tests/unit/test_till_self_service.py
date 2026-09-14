"""The till's own self-service doors (2026-09-14, both till-integration audits' own
recommendation): `GET /till/branches`, `GET /till/status`, `POST /till/operators/verify-pin`,
and the verified-approver path on `/till/redeem`.

WRITTEN AGAINST A REAL DATASTORE (MemoryDataStore) rather than fully mocked containers, because
the PIN hash/ticket mechanism is exactly the kind of thing a mock could accidentally always agree
with itself — the same reasoning `test_loyalty_desk_body.py`/`test_bookings_desk_till_gap.py`
apply one layer down.
"""
from __future__ import annotations

import asyncio
import types

from app.adapters.datastore.memory import MemoryDataStore
from app.api.v1 import till as till_routes
from app.core import operator_ticket as OT
from app.core.models import Branch, Operator
from app.core.stores import BranchStore, OperatorStore

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


# ── POST /till/operators/verify-pin ──────────────────────────────────────────────────────────

def _seed_operator(store, *, active=True, pin="1234") -> Operator:
    op = Operator(id="opr_1", tenant=TENANT, name="خالد", role="manager", active=active,
                 pin_hash=OT.pin_hash(SALT, TENANT, "opr_1", pin))
    run(OperatorStore(store).save(op))
    return op


def test_verify_pin_with_the_right_pin_issues_a_real_ticket():
    store = MemoryDataStore()
    _seed_operator(store)
    req = _request(store)
    body = till_routes.TillPinVerifyIn(operator_id="opr_1", pin="1234")
    out = run(till_routes.verify_pin_at_the_counter(req, body, principal=_Principal()))
    assert out["ok"] is True
    assert out["operator"] == {"id": "opr_1", "name": "خالد"}
    assert OT.verifies(SALT, TENANT, "opr_1", out["ticket"])


def test_verify_pin_with_the_wrong_pin_is_refused_and_audited():
    store = MemoryDataStore()
    _seed_operator(store)
    req = _request(store)
    body = till_routes.TillPinVerifyIn(operator_id="opr_1", pin="9999")
    out = run(till_routes.verify_pin_at_the_counter(req, body, principal=_Principal()))
    assert out["ok"] is False
    assert "ticket" not in out
    assert req.app.state.auditor.calls[0][0] == "operator.pin_rejected"


def test_verify_pin_for_an_inactive_operator_is_refused():
    store = MemoryDataStore()
    _seed_operator(store, active=False)
    req = _request(store)
    body = till_routes.TillPinVerifyIn(operator_id="opr_1", pin="1234")
    out = run(till_routes.verify_pin_at_the_counter(req, body, principal=_Principal()))
    assert out["ok"] is False


def test_verify_pin_for_an_unknown_operator_answers_the_same_refusal():
    """Same sentence for 'no such operator' and 'wrong PIN' — CWE-203/208, an enumeration
    discipline the field screen's own verify-pin already follows."""
    store = MemoryDataStore()
    req = _request(store)
    body = till_routes.TillPinVerifyIn(operator_id="opr_ghost", pin="1234")
    out = run(till_routes.verify_pin_at_the_counter(req, body, principal=_Principal()))
    assert out == {"ok": False, "message": "رمز خاطئ أو موظف غير نشط."}


# ── the verified-approver path on /till/redeem ───────────────────────────────────────────────

class _Desk:
    configured = True

    def __init__(self, redeem=None):
        self._redeem = redeem
        self.seen: dict = {}

    async def redeem(self, **kw):
        self.seen = kw
        return self._redeem


def _redeem_request(store, *, ops=None):
    class _Auditor:
        def __init__(self):
            self.calls = []

        async def record(self, action, **kw):
            self.calls.append((action, kw))

    container = types.SimpleNamespace(
        operations=ops or _Ops(customer=_Customer()), loyalty_desk=_Desk({"transaction_ref": "x"}),
        datastore=store, bookings_desk=None, reminders_desk=None)
    state = types.SimpleNamespace(container=container, container_settings=_Settings(),
                                  auditor=_Auditor())
    return types.SimpleNamespace(app=types.SimpleNamespace(state=state), client=None)


def test_redeem_with_a_valid_ticket_uses_the_real_operators_own_name():
    store = MemoryDataStore()
    _seed_operator(store)
    req = _redeem_request(store)
    ticket = OT.issue(SALT, TENANT, "opr_1")
    body = till_routes.TillRedeemIn(
        phone="0500000000", reward_id="r1", branch_id="brn-main", idempotency_key="k",
        approved_by="اسم مزيّف لا علاقة له", approver_operator_id="opr_1",
        approver_ticket=ticket)
    out = run(till_routes.redeem_at_the_counter(req, body, principal=_Principal()))
    assert out["ok"] is True
    desk = req.app.state.container.loyalty_desk
    assert desk.seen["approved_by"] == "خالد"      # the REAL operator's name, not the free text


def test_redeem_with_an_invalid_ticket_is_refused_before_touching_loyalty():
    store = MemoryDataStore()
    _seed_operator(store)
    req = _redeem_request(store)
    body = till_routes.TillRedeemIn(
        phone="0500000000", reward_id="r1", branch_id="brn-main", idempotency_key="k",
        approver_operator_id="opr_1", approver_ticket="garbage.not.a.ticket")
    out = run(till_routes.redeem_at_the_counter(req, body, principal=_Principal()))
    assert out["ok"] is False and out["reason"] == "REFUSED"
    assert req.app.state.container.loyalty_desk.seen == {}


def test_redeem_with_a_ticket_for_an_inactive_operator_is_refused():
    store = MemoryDataStore()
    _seed_operator(store, active=False)
    req = _redeem_request(store)
    ticket = OT.issue(SALT, TENANT, "opr_1")
    body = till_routes.TillRedeemIn(
        phone="0500000000", reward_id="r1", branch_id="brn-main", idempotency_key="k",
        approver_operator_id="opr_1", approver_ticket=ticket)
    out = run(till_routes.redeem_at_the_counter(req, body, principal=_Principal()))
    assert out["ok"] is False


def test_redeem_with_no_ticket_still_uses_the_legacy_free_text_unchanged():
    """Backward compatibility — an existing integration that never adopted the ticket keeps
    working exactly as before."""
    store = MemoryDataStore()
    req = _redeem_request(store)
    body = till_routes.TillRedeemIn(
        phone="0500000000", reward_id="r1", branch_id="brn-main", idempotency_key="k",
        approved_by="سالم")
    out = run(till_routes.redeem_at_the_counter(req, body, principal=_Principal()))
    assert out["ok"] is True
    assert req.app.state.container.loyalty_desk.seen["approved_by"] == "سالم"


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
