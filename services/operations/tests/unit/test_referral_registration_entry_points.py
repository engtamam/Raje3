"""Every real "a new customer just showed up" door this service has, now able to register a
referral code (owner instruction, 2026-09-27: "احنا نحتاج نعالجها من الخلفية... تتسجل مع تسجيل
الزيارة"). Three doors, one shared engine call (`Operations._register_referral_if_new`):

  1. `record_visit()` — a walk-in visit with no prior booking/mobile-request at all.
  2. `MobileRequestService.create()`/`complete()` — the code is offered at request time, carried
     on the row, and only ever attempted once the request actually turns into a real visit.
  3. `ensure_customer()` — the REAL "new customer" moment for a booking (see its own docstring):
     a booking's own `attend()` always finds an already-existing customer, so this is the one
     place a booking-sourced referral is ever registered.

Fakes the engine (same technique `test_till_referral_register.py` already uses) so these tests
prove the WIRING — who gets called, with what, and when — not the engine's own validation logic,
which `test_referral_redemption.py` already owns.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.mobile_requests import MobileRequestService
from app.core.operations import Operations
from app.core.referral_redemption import ReferralRedemptionError

SALT = "s" * 32
CC = "966"
TENANT = "tnt_referral_wiring"


def run(coro):
    return asyncio.run(coro)


class FakeGrant:
    new_customer_reward_type = "discount_percent"
    new_customer_reward_params = {"percent": 10}


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.refuse_with: str | None = None

    async def register(self, tenant, *, code, beneficiary_phone, invoice_minor, actor):
        self.calls.append({"tenant": tenant, "code": code, "phone": beneficiary_phone,
                           "invoice_minor": invoice_minor, "actor": actor})
        if self.refuse_with:
            raise ReferralRedemptionError(self.refuse_with)
        return FakeGrant()


@pytest.fixture()
def ops_and_engine():
    store = MemoryDataStore()
    svc = Operations(store=store, pii_salt=SALT)
    engine = FakeEngine()
    svc.with_referral_redemption_engine(engine)
    return svc, engine


# ── 1. record_visit — the walk-in door ──────────────────────────────────────────────────────────
def test_a_new_customers_visit_with_a_code_registers_it(ops_and_engine):
    svc, engine = ops_and_engine
    res = run(svc.record_visit(tenant=TENANT, phone="0501234567", service_ids=["srv_1"],
                               referral_code="AB123", total_minor=5000))
    assert res.created_customer is True
    assert res.referral_registration == {"ok": True, "new_customer_reward_type": "discount_percent",
                                         "new_customer_reward_params": {"percent": 10}}
    assert engine.calls == [{"tenant": TENANT, "code": "AB123", "phone": "966501234567",
                             "invoice_minor": 5000, "actor": "field"}]


def test_a_visit_with_no_code_never_calls_the_engine(ops_and_engine):
    svc, engine = ops_and_engine
    res = run(svc.record_visit(tenant=TENANT, phone="0501234567", service_ids=["srv_1"]))
    assert res.referral_registration is None
    assert engine.calls == []


def test_a_returning_customers_visit_never_calls_the_engine_even_with_a_code(ops_and_engine):
    """The whole point of gating on `created_customer` — a returning customer typing in a code he
    found somewhere is never even asked about; the engine's own new-customer check would refuse
    it anyway, and every returning visit should not pay for a peer round trip that can only fail."""
    svc, engine = ops_and_engine
    run(svc.record_visit(tenant=TENANT, phone="0501234567", service_ids=["srv_1"],
                         idempotency_key="first"))
    res = run(svc.record_visit(tenant=TENANT, phone="0501234567", service_ids=["srv_1"],
                               idempotency_key="second", referral_code="AB123"))
    assert res.created_customer is False
    assert res.referral_registration is None
    assert engine.calls == []


def test_a_refused_code_never_undoes_the_visit_already_written(ops_and_engine):
    svc, engine = ops_and_engine
    engine.refuse_with = "كود الإحالة غير صالح"
    res = run(svc.record_visit(tenant=TENANT, phone="0501234567", service_ids=["srv_1"],
                               referral_code="ZZZZZ"))
    assert res.visit.id                              # the visit is real regardless
    assert res.referral_registration == {"ok": False, "message": "كود الإحالة غير صالح"}


def test_an_unexpected_engine_exception_is_swallowed_not_raised(ops_and_engine):
    svc, engine = ops_and_engine

    async def _boom(*a, **kw):
        raise RuntimeError("peer exploded")

    engine.register = _boom
    res = run(svc.record_visit(tenant=TENANT, phone="0501234567", service_ids=["srv_1"],
                               referral_code="AB123"))
    assert res.visit.id
    assert res.referral_registration == {"ok": False, "message": "تعذّر تسجيل كود الإحالة الآن"}


def test_no_engine_wired_is_a_silent_none_never_a_crash():
    store = MemoryDataStore()
    svc = Operations(store=store, pii_salt=SALT)             # no with_referral_redemption_engine
    res = run(svc.record_visit(tenant=TENANT, phone="0501234567", service_ids=["srv_1"],
                               referral_code="AB123"))
    assert res.visit.id
    assert res.referral_registration is None


def test_the_invoice_minor_the_engine_sees_is_the_visits_own_computed_total(ops_and_engine):
    """No till, no explicit total_minor — computed from the catalogue (0 here, unpriced), and
    that same computed number is what the engine is asked about, never a stale/guessed one."""
    svc, engine = ops_and_engine
    run(svc.record_visit(tenant=TENANT, phone="0501234567", service_ids=["srv_1"],
                         referral_code="AB123"))
    assert engine.calls[0]["invoice_minor"] == 0


# ── 2. mobile-service requests — offered at request time, spent at completion ───────────────────
@pytest.fixture()
def mobile_svc_and_engine():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt=SALT)
    engine = FakeEngine()
    ops.with_referral_redemption_engine(engine)
    return MobileRequestService(store=store, operations=ops, default_cc=CC), engine


def test_a_request_carries_its_offered_code_on_the_row(mobile_svc_and_engine):
    s, _engine = mobile_svc_and_engine
    req = run(s.create(tenant=TENANT, phone="0501234567", customer_name="أحمد",
                       service_ids=["srv_1"], requested_time=1_800_000_000,
                       lat=24.7, lng=46.6, referral_code="AB123"))
    assert req.referral_code == "AB123"


def test_completing_a_request_registers_the_codes_it_carried(mobile_svc_and_engine):
    s, engine = mobile_svc_and_engine
    req = run(s.create(tenant=TENANT, phone="0501234567", customer_name="أحمد",
                       service_ids=["srv_1"], requested_time=1_800_000_000,
                       lat=24.7, lng=46.6, referral_code="AB123"))
    run(s.accept(TENANT, req.id, actor="owner1"))
    run(s.complete(TENANT, req.id))
    assert len(engine.calls) == 1
    assert engine.calls[0]["code"] == "AB123"
    assert engine.calls[0]["phone"] == "966501234567"


def test_a_request_with_no_code_never_touches_the_engine_on_completion(mobile_svc_and_engine):
    s, engine = mobile_svc_and_engine
    req = run(s.create(tenant=TENANT, phone="0501234567", customer_name="أحمد",
                       service_ids=["srv_1"], requested_time=1_800_000_000,
                       lat=24.7, lng=46.6))
    run(s.accept(TENANT, req.id, actor="owner1"))
    run(s.complete(TENANT, req.id))
    assert engine.calls == []


def test_a_second_request_from_the_same_now_returning_phone_never_registers(mobile_svc_and_engine):
    """The customer this beneficiary phone belongs to was already created by the FIRST completed
    request; a second request (even with a code attached) belongs to a returning customer by the
    time it is completed."""
    s, engine = mobile_svc_and_engine
    first = run(s.create(tenant=TENANT, phone="0501234567", customer_name="أحمد",
                         service_ids=["srv_1"], requested_time=1_800_000_000,
                         lat=24.7, lng=46.6, referral_code="AB123"))
    run(s.accept(TENANT, first.id, actor="owner1"))
    run(s.complete(TENANT, first.id))
    assert len(engine.calls) == 1

    second = run(s.create(tenant=TENANT, phone="0501234567", customer_name="أحمد",
                          service_ids=["srv_1"], requested_time=1_800_000_100,
                          lat=24.7, lng=46.6, referral_code="ZZZZZ"))
    run(s.accept(TENANT, second.id, actor="owner1"))
    run(s.complete(TENANT, second.id))
    assert len(engine.calls) == 1              # unchanged — the second attempt never fired


# ── 3. ensure_customer — the real "new customer" moment for a booking ───────────────────────────
def test_ensure_customer_with_a_code_on_a_brand_new_phone_registers_it(ops_and_engine):
    svc, engine = ops_and_engine
    customer, referral_registration = run(svc.ensure_customer(
        TENANT, "0501234567", referral_code="AB123", actor="console"))
    assert customer.phone == "966501234567"
    assert referral_registration == {"ok": True, "new_customer_reward_type": "discount_percent",
                                     "new_customer_reward_params": {"percent": 10}}
    assert engine.calls == [{"tenant": TENANT, "code": "AB123", "phone": "966501234567",
                             "invoice_minor": 0, "actor": "console"}]


def test_ensure_customer_called_twice_only_registers_on_the_first(ops_and_engine):
    svc, engine = ops_and_engine
    first, first_reg = run(svc.ensure_customer(TENANT, "0501234567", referral_code="AB123"))
    second, second_reg = run(svc.ensure_customer(TENANT, "0501234567", referral_code="ZZZZZ"))
    assert second.id == first.id
    assert first_reg is not None
    assert second_reg is None                  # the second call found an EXISTING customer
    assert len(engine.calls) == 1


def test_ensure_customer_with_no_code_returns_none_and_never_calls_the_engine(ops_and_engine):
    svc, engine = ops_and_engine
    _customer, referral_registration = run(svc.ensure_customer(TENANT, "0501234567"))
    assert referral_registration is None
    assert engine.calls == []
