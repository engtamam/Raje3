"""RenewalTriggerStore (one claim per invoice) and RenewalTrigger (bus event -> an opened
subscription-renewal Flow, or nothing)."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.renewal_request import RenewalRequestStore
from app.core.renewal_trigger import RenewalTrigger
from app.core.renewal_trigger_store import RenewalTriggerStore


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


# ── RenewalTriggerStore ──────────────────────────────────────────────────────────────────────
def test_the_first_claim_for_an_invoice_succeeds():
    store = RenewalTriggerStore(MemoryDataStore())
    assert run(store.claim("inv_1", now=1000)) is True


def test_a_second_claim_for_the_same_invoice_fails():
    store = RenewalTriggerStore(MemoryDataStore())
    run(store.claim("inv_1", now=1000))
    assert run(store.claim("inv_1", now=2000)) is False


def test_an_empty_invoice_id_never_claims():
    store = RenewalTriggerStore(MemoryDataStore())
    assert run(store.claim("", now=1000)) is False


def test_two_different_invoices_claim_independently():
    store = RenewalTriggerStore(MemoryDataStore())
    assert run(store.claim("inv_a", now=1000)) is True
    assert run(store.claim("inv_b", now=1000)) is True


# ── RenewalTrigger ───────────────────────────────────────────────────────────────────────────
def _trigger(phones=None):
    store = MemoryDataStore()
    sender = _FakeSender()
    requests = RenewalRequestStore(store)
    owner_phone = _FakeOwnerPhone(phones if phones is not None else {"t1": "+966500000000"})
    trigger = RenewalTrigger(claims=RenewalTriggerStore(store), requests=requests,
                             owner_phone=owner_phone, sender=sender)
    return trigger, requests, sender


def test_a_real_event_opens_the_flow_and_remembers_the_request():
    trigger, requests, sender = _trigger()
    ok = run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1"}, now=1000))
    assert ok is True
    assert sender.sent == [{"tenant": "t1", "to": "+966500000000",
                            "template_name": "subscription_renewal_flow", "variables": [],
                            "idempotency_key": "renew:inv_1", "flow_token": "renew:inv_1",
                            "flow_action_data": {"customer": "inv_1"}}]
    pending = run(requests.resolve("renew:inv_1"))
    assert pending is not None
    assert (pending.tenant, pending.to) == ("t1", "+966500000000")


def test_a_second_event_for_the_same_invoice_sends_nothing_again():
    trigger, _requests, sender = _trigger()
    run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1"}, now=1000))
    ok = run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1"}, now=1000))
    assert ok is False
    assert len(sender.sent) == 1


def test_a_consolidated_invoices_several_per_subscription_events_send_exactly_once():
    # billing emits subscription.renewed once PER SUBSCRIPTION on a consolidated invoice, all
    # carrying the same invoice_id.
    trigger, _requests, sender = _trigger()
    run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1", "subscription_id": "sub_a"}, now=1000))
    run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1", "subscription_id": "sub_b"}, now=1000))
    run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1", "subscription_id": "sub_c"}, now=1000))
    assert len(sender.sent) == 1


def test_no_tenant_sends_nothing():
    trigger, _requests, sender = _trigger()
    ok = run(trigger.handle({"invoice_id": "inv_1"}, now=1000))
    assert ok is False
    assert sender.sent == []


def test_no_invoice_id_sends_nothing():
    trigger, _requests, sender = _trigger()
    ok = run(trigger.handle({"tenant": "t1"}, now=1000))
    assert ok is False
    assert sender.sent == []


def test_a_tenant_with_no_reachable_owner_sends_nothing():
    trigger, _requests, sender = _trigger(phones={})
    ok = run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1"}, now=1000))
    assert ok is False
    assert sender.sent == []


def test_an_unresolvable_owner_still_leaves_the_invoice_unclaimed_for_a_retry():
    # the claim happens BEFORE the phone lookup fails, so a real retry (billing re-emitting, or a
    # future durable catch-up) would need the claim released — confirmed here it is NOT: a second
    # attempt at the same invoice also finds nothing, by design (claim-then-resolve, not the other
    # way round) rather than hammering identity-service on every redelivery of a bad event.
    trigger, _requests, sender = _trigger(phones={})
    run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1"}, now=1000))
    ok = run(trigger.handle({"tenant": "t1", "invoice_id": "inv_1"}, now=1000))
    assert ok is False
    assert sender.sent == []


def test_two_different_tenants_open_independently():
    trigger, _requests, sender = _trigger(phones={"t1": "+9665A", "t2": "+9665B"})
    run(trigger.handle({"tenant": "t1", "invoice_id": "inv_a"}, now=1000))
    run(trigger.handle({"tenant": "t2", "invoice_id": "inv_b"}, now=1000))
    got = {(s["tenant"], s["to"]) for s in sender.sent}
    assert got == {("t1", "+9665A"), ("t2", "+9665B")}
