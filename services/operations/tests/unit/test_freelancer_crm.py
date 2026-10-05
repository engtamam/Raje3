"""Customer-service freelancer CRM engine (core/freelancer_crm.py) — business rules, cooldown
visibility, the daily reward cap, do-not-disturb permanence, and the escalation resolve flow. No
HTTP, no real network loyalty/notifier — fakes standing in for `LoyaltyDesk`/`InAppNotifier` so the
tests stay about this module's own logic.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.freelancer_crm import (DISCOUNT, GIFT, NEUTRAL, OPEN, POINTS, RESOLVED, SATISFIED,
                                     UNSATISFIED, FreelancerCrmError, FreelancerCrmService)
from app.core.models import Customer
from app.core.stores import CustomerStore

TENANT = "tnt_crm_1"


def run(c):
    return asyncio.run(c)


class _FakeLoyalty:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def award(self, **kwargs):
        self.calls.append(kwargs)
        return {"awarded": kwargs["points"]}


class _FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)


@pytest.fixture()
def crm():
    store = MemoryDataStore()
    customers = CustomerStore(store)
    loyalty = _FakeLoyalty()
    notifier = _FakeNotifier()
    svc = FreelancerCrmService(store=store, customers=customers, loyalty=loyalty,
                               notifier=notifier)
    return svc, store, customers, loyalty, notifier


async def _seed_customer(customers: CustomerStore, customer_id: str = "cust_1") -> Customer:
    c = Customer(id=customer_id, tenant=TENANT, phone="+966501234567",
                subject_ref="subj_1", name="أحمد", last_visit=int(time.time()))
    return await customers.save(c)


# ── business rules ──────────────────────────────────────────────────────────────────────────────
def test_default_rules_use_the_configured_daily_cap(crm):
    svc, *_ = crm
    rules = run(svc.get_rules(TENANT))
    assert rules.cooldown_days == 30
    assert rules.daily_cap == 5


def test_set_rules_rejects_negative_values(crm):
    svc, *_ = crm
    with pytest.raises(FreelancerCrmError):
        run(svc.set_rules(TENANT, cooldown_days=-1, daily_cap=5))


def test_set_rules_persists(crm):
    svc, *_ = crm
    run(svc.set_rules(TENANT, cooldown_days=7, daily_cap=2))
    rules = run(svc.get_rules(TENANT))
    assert rules.cooldown_days == 7
    assert rules.daily_cap == 2


# ── reward catalog ───────────────────────────────────────────────────────────────────────────────
def test_add_reward_option_requires_a_valid_discount_percent(crm):
    svc, *_ = crm
    with pytest.raises(FreelancerCrmError):
        run(svc.add_reward_option(TENANT, kind=DISCOUNT, label="خصم", percent=0))


def test_add_reward_option_requires_positive_points(crm):
    svc, *_ = crm
    with pytest.raises(FreelancerCrmError):
        run(svc.add_reward_option(TENANT, kind=POINTS, label="نقاط", points=0))


def test_add_reward_option_rejects_an_unknown_kind(crm):
    svc, *_ = crm
    with pytest.raises(FreelancerCrmError):
        run(svc.add_reward_option(TENANT, kind="cash", label="نقدي"))


def test_gift_option_needs_no_percent_or_points(crm):
    svc, *_ = crm
    opt = run(svc.add_reward_option(TENANT, kind=GIFT, label="غسيل مجاني"))
    assert opt.kind == GIFT


# ── cooldown visibility ─────────────────────────────────────────────────────────────────────────
def test_a_never_contacted_customer_is_visible(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    out = run(svc.filtered_customers(TENANT))
    assert any(c["customer_id"] == "cust_1" for c in out)


def test_rating_a_customer_hides_them_during_the_cooldown(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.set_rules(TENANT, cooldown_days=30, daily_cap=5))
    run(svc.rate(TENANT, "cust_1", status=SATISFIED, by="freelancer_1"))
    out = run(svc.filtered_customers(TENANT))
    assert not any(c["customer_id"] == "cust_1" for c in out)


def test_a_customer_returns_once_the_cooldown_elapses(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.set_rules(TENANT, cooldown_days=30, daily_cap=5))
    run(svc.rate(TENANT, "cust_1", status=SATISFIED, by="freelancer_1"))
    # backdate the contact past the cooldown window
    raw = run(store.get("customer_service_contacts", f"{TENANT}|cust_1"))
    raw["last_contacted_at"] = int(time.time()) - 31 * 86400
    run(store.put("customer_service_contacts", f"{TENANT}|cust_1", raw))
    out = run(svc.filtered_customers(TENANT))
    assert any(c["customer_id"] == "cust_1" for c in out)


def test_do_not_disturb_never_expires_on_its_own(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.set_do_not_disturb(TENANT, "cust_1"))
    raw = run(store.get("customer_service_contacts", f"{TENANT}|cust_1"))
    raw["last_contacted_at"] = int(time.time()) - 365 * 86400
    run(store.put("customer_service_contacts", f"{TENANT}|cust_1", raw))
    out = run(svc.filtered_customers(TENANT))
    assert not any(c["customer_id"] == "cust_1" for c in out)


def test_search_matches_the_name(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    out = run(svc.filtered_customers(TENANT, search="أحمد"))
    assert len(out) == 1
    out = run(svc.filtered_customers(TENANT, search="سارة"))
    assert out == []


def test_search_matches_the_phone(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    out = run(svc.filtered_customers(TENANT, search="501234567"))
    assert len(out) == 1


def test_search_is_case_insensitive_on_latin_characters(crm):
    svc, store, customers, *_ = crm
    c = Customer(id="cust_2", tenant=TENANT, phone="+966502222222", subject_ref="subj_2",
                name="Noor", last_visit=int(time.time()))
    run(customers.save(c))
    out = run(svc.filtered_customers(TENANT, search="NOOR"))
    assert len(out) == 1


def test_status_filter_new_excludes_an_already_contacted_customer(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.set_rules(TENANT, cooldown_days=0, daily_cap=5))
    out = run(svc.filtered_customers(TENANT, status_filter="new"))
    assert len(out) == 1
    run(svc.rate(TENANT, "cust_1", status=SATISFIED, by="freelancer_1"))
    out = run(svc.filtered_customers(TENANT, status_filter="new"))
    assert out == []


def test_status_filter_matches_the_last_rating(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.set_rules(TENANT, cooldown_days=0, daily_cap=5))
    run(svc.rate(TENANT, "cust_1", status=UNSATISFIED, by="freelancer_1"))
    out = run(svc.filtered_customers(TENANT, status_filter=UNSATISFIED))
    assert len(out) == 1
    out = run(svc.filtered_customers(TENANT, status_filter=SATISFIED))
    assert out == []


def test_filtered_customers_reports_the_last_status(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.set_rules(TENANT, cooldown_days=0, daily_cap=5))
    run(svc.rate(TENANT, "cust_1", status=NEUTRAL, by="freelancer_1"))
    out = run(svc.filtered_customers(TENANT))
    assert out[0]["last_status"] == NEUTRAL


def test_rate_rejects_an_unknown_status(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    with pytest.raises(FreelancerCrmError):
        run(svc.rate(TENANT, "cust_1", status="confused", by="freelancer_1"))


# ── rewards + daily cap ─────────────────────────────────────────────────────────────────────────
def test_points_reward_calls_the_real_loyalty_award(crm):
    svc, store, customers, loyalty, _notifier = crm
    run(_seed_customer(customers))
    opt = run(svc.add_reward_option(TENANT, kind=POINTS, label="50 نقطة", points=50))
    grant = run(svc.grant_reward(TENANT, "cust_1", option_id=opt.id, by="freelancer_1",
                                 subject_ref="subj_1"))
    assert grant["fulfilled"] is True
    assert loyalty.calls[0]["points"] == 50
    assert loyalty.calls[0]["reason"] == "freelancer_reward"


def test_discount_reward_is_recorded_as_pending_honour_not_fulfilled(crm):
    svc, store, customers, loyalty, _notifier = crm
    run(_seed_customer(customers))
    opt = run(svc.add_reward_option(TENANT, kind=DISCOUNT, label="خصم 10%", percent=10))
    grant = run(svc.grant_reward(TENANT, "cust_1", option_id=opt.id, by="freelancer_1"))
    assert grant["fulfilled"] is False
    assert loyalty.calls == []


def test_grant_reward_refuses_an_unknown_option(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    with pytest.raises(FreelancerCrmError):
        run(svc.grant_reward(TENANT, "cust_1", option_id="nope", by="freelancer_1"))


def test_daily_cap_blocks_the_same_freelancer_past_the_limit(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers, "cust_1"))
    run(_seed_customer(customers, "cust_2"))
    run(_seed_customer(customers, "cust_3"))
    run(svc.set_rules(TENANT, cooldown_days=30, daily_cap=2))
    opt = run(svc.add_reward_option(TENANT, kind=GIFT, label="غسيل مجاني"))
    run(svc.grant_reward(TENANT, "cust_1", option_id=opt.id, by="freelancer_1"))
    run(svc.grant_reward(TENANT, "cust_2", option_id=opt.id, by="freelancer_1"))
    with pytest.raises(FreelancerCrmError):
        run(svc.grant_reward(TENANT, "cust_3", option_id=opt.id, by="freelancer_1"))


def test_daily_cap_is_tracked_per_freelancer_not_per_shop(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers, "cust_1"))
    run(_seed_customer(customers, "cust_2"))
    run(svc.set_rules(TENANT, cooldown_days=30, daily_cap=1))
    opt = run(svc.add_reward_option(TENANT, kind=GIFT, label="غسيل مجاني"))
    run(svc.grant_reward(TENANT, "cust_1", option_id=opt.id, by="freelancer_1"))
    # a different freelancer has their own untouched cap
    grant = run(svc.grant_reward(TENANT, "cust_2", option_id=opt.id, by="freelancer_2"))
    assert grant["fulfilled"] is False


# ── escalations ──────────────────────────────────────────────────────────────────────────────────
def test_escalate_notifies_every_recipient(crm):
    svc, store, customers, _loyalty, notifier = crm
    run(_seed_customer(customers))
    esc = run(svc.escalate(TENANT, "cust_1", note="عميل غاضب", freelancer_phone="+966501111111",
                           recipients=["mgr_1", "mgr_2"]))
    assert esc.status == OPEN
    assert len(notifier.sent) == 2


def test_escalate_hides_the_customer_like_any_other_contact(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.set_rules(TENANT, cooldown_days=30, daily_cap=5))
    run(svc.escalate(TENANT, "cust_1", note="عميل غاضب", freelancer_phone="+966501111111",
                     recipients=[]))
    out = run(svc.filtered_customers(TENANT))
    assert not any(c["customer_id"] == "cust_1" for c in out)


def test_resolve_escalation_marks_it_resolved_and_is_idempotent(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    esc = run(svc.escalate(TENANT, "cust_1", note="عميل غاضب", freelancer_phone="+966501111111",
                           recipients=[]))
    resolved = run(svc.resolve_escalation(TENANT, esc.id, resolved_by="owner1",
                                          resolution_note="تم الاتصال", new_status=SATISFIED))
    assert resolved.status == RESOLVED
    again = run(svc.resolve_escalation(TENANT, esc.id, resolved_by="owner1"))
    assert again.status == RESOLVED


def test_resolve_escalation_refuses_an_unknown_id(crm):
    svc, *_ = crm
    with pytest.raises(FreelancerCrmError):
        run(svc.resolve_escalation(TENANT, "nope", resolved_by="owner1"))


def test_resolve_escalation_overrides_the_customers_last_known_status(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    esc = run(svc.escalate(TENANT, "cust_1", note="عميل غاضب", freelancer_phone="+966501111111",
                           recipients=[]))
    run(svc.resolve_escalation(TENANT, esc.id, resolved_by="owner1", new_status=UNSATISFIED))
    raw = run(store.get("customer_service_contacts", f"{TENANT}|cust_1"))
    assert raw["last_status"] == UNSATISFIED


# ── notes + export ───────────────────────────────────────────────────────────────────────────────
def test_export_notes_omits_pii_by_default(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.add_note(TENANT, "cust_1", text="تم الاتصال", author_phone="+966501111111",
                     status=SATISFIED, services=["غسيل خارجي"]))
    now = int(time.time())
    text = run(svc.export_notes(TENANT, since=now - 60, until=now + 60))
    assert "أحمد" not in text
    assert "+966501234567" not in text
    assert "غسيل خارجي" in text


def test_export_notes_includes_pii_only_when_explicitly_asked(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.add_note(TENANT, "cust_1", text="تم الاتصال", author_phone="+966501111111",
                     status=SATISFIED, services=["غسيل خارجي"]))
    now = int(time.time())
    text = run(svc.export_notes(TENANT, since=now - 60, until=now + 60, include_pii=True))
    assert "أحمد" in text
    assert "+966501234567" in text


def test_export_notes_respects_the_date_range(crm):
    svc, store, customers, *_ = crm
    run(_seed_customer(customers))
    run(svc.add_note(TENANT, "cust_1", text="ملاحظة قديمة", author_phone="+966501111111",
                     status=SATISFIED))
    now = int(time.time())
    text = run(svc.export_notes(TENANT, since=now + 100, until=now + 200))
    assert text == ""
