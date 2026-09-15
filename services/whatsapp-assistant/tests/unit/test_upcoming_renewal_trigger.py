"""UpcomingRenewalTriggerStore (one claim per subscription+period_end) and UpcomingRenewalTrigger
(one "renews soon" row -> the SAME subscription-renewal Flow, seeded 2 days early, or nothing)."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.upcoming_renewal_trigger import UpcomingRenewalTrigger
from app.core.upcoming_renewal_trigger_store import UpcomingRenewalTriggerStore


def run(c):
    return asyncio.run(c)


class _FakeOwnerPhone:
    def __init__(self, phones: dict[str, str]) -> None:
        self._phones = phones

    async def resolve(self, tenant: str) -> str:
        return self._phones.get(tenant, "")


class _FakeSender:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_template(self, **kwargs):
        self.sent.append(kwargs)
        return "dlv_1"


# ── UpcomingRenewalTriggerStore ──────────────────────────────────────────────────────────────────
def test_the_first_claim_for_a_subscription_and_period_end_succeeds():
    store = UpcomingRenewalTriggerStore(MemoryDataStore())
    assert run(store.claim("sub_1", 5000, now=1000)) is True


def test_a_second_claim_for_the_same_period_end_fails():
    store = UpcomingRenewalTriggerStore(MemoryDataStore())
    run(store.claim("sub_1", 5000, now=1000))
    assert run(store.claim("sub_1", 5000, now=2000)) is False


def test_a_new_cycles_period_end_claims_independently_of_the_last_one():
    """The whole reason this is keyed on (sub, period_end) and not on sub alone: a daily scan
    finding the SAME subscription tomorrow, on its NEXT cycle, must open a fresh heads-up rather
    than staying stuck on a claim from the cycle before."""
    store = UpcomingRenewalTriggerStore(MemoryDataStore())
    run(store.claim("sub_1", 5000, now=1000))
    assert run(store.claim("sub_1", 8000, now=2000)) is True


def test_an_empty_subscription_id_or_zero_period_end_never_claims():
    store = UpcomingRenewalTriggerStore(MemoryDataStore())
    assert run(store.claim("", 5000, now=1000)) is False
    assert run(store.claim("sub_1", 0, now=1000)) is False


# ── UpcomingRenewalTrigger ───────────────────────────────────────────────────────────────────────
def _trigger(phones=None):
    store = MemoryDataStore()
    sender = _FakeSender()
    owner_phone = _FakeOwnerPhone(phones if phones is not None else {"t1": "+966500000000"})
    trigger = UpcomingRenewalTrigger(
        claims=UpcomingRenewalTriggerStore(store), owner_phone=owner_phone, sender=sender)
    return trigger, sender


def test_a_real_row_opens_the_flow_seeded_with_the_early_customer_form():
    trigger, sender = _trigger()
    ok = run(trigger.handle(tenant="t1", subscription_id="sub_1", period_end=5000, now=1000))
    assert ok is True
    # SAME send shape as the real, invoice-driven trigger — "_platform" identity, the real tenant
    # riding inside flow_action_data.customer — but with "sub" marking it as the early seeding.
    assert sender.sent == [{"tenant": "_platform", "to": "+966500000000",
                            "template_name": "subscription_renewal_flow", "variables": [],
                            "idempotency_key": "renew_soon:sub_1:5000",
                            "flow_token": "renew_soon:sub_1:5000",
                            "flow_action_data": {"customer": "t1:sub:sub_1"}}]


def test_a_second_call_for_the_same_cycle_sends_nothing_again():
    trigger, sender = _trigger()
    run(trigger.handle(tenant="t1", subscription_id="sub_1", period_end=5000, now=1000))
    ok = run(trigger.handle(tenant="t1", subscription_id="sub_1", period_end=5000, now=1000))
    assert ok is False
    assert len(sender.sent) == 1


def test_the_next_cycles_period_end_opens_a_fresh_heads_up():
    trigger, sender = _trigger()
    run(trigger.handle(tenant="t1", subscription_id="sub_1", period_end=5000, now=1000))
    ok = run(trigger.handle(tenant="t1", subscription_id="sub_1", period_end=8000, now=9000))
    assert ok is True
    assert len(sender.sent) == 2


def test_no_tenant_sends_nothing():
    trigger, sender = _trigger()
    ok = run(trigger.handle(tenant="", subscription_id="sub_1", period_end=5000, now=1000))
    assert ok is False
    assert sender.sent == []


def test_no_subscription_id_sends_nothing():
    trigger, sender = _trigger()
    ok = run(trigger.handle(tenant="t1", subscription_id="", period_end=5000, now=1000))
    assert ok is False
    assert sender.sent == []


def test_a_tenant_with_no_reachable_owner_sends_nothing():
    trigger, sender = _trigger(phones={})
    ok = run(trigger.handle(tenant="t1", subscription_id="sub_1", period_end=5000, now=1000))
    assert ok is False
    assert sender.sent == []


def test_two_different_tenants_open_independently_but_both_send_from_the_platform():
    trigger, sender = _trigger(phones={"t1": "+9665A", "t2": "+9665B"})
    run(trigger.handle(tenant="t1", subscription_id="sub_a", period_end=5000, now=1000))
    run(trigger.handle(tenant="t2", subscription_id="sub_b", period_end=5000, now=1000))
    got = {(s["tenant"], s["to"], s["flow_action_data"]["customer"]) for s in sender.sent}
    assert got == {("_platform", "+9665A", "t1:sub:sub_a"), ("_platform", "+9665B", "t2:sub:sub_b")}
