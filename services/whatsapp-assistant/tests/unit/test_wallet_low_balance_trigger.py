"""WalletLowBalanceTrigger — one `wallet.balance_low` bus event -> an owner-facing top-up notice,
event-driven, no sweep (see app/core/wallet_low_balance_trigger.py's own docstring)."""
from __future__ import annotations

import asyncio

from app.core.wallet_low_balance_trigger import WalletLowBalanceTrigger


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


def _trigger(phones=None, base_url="https://ra-je3.com"):
    sender = _FakeSender()
    owner_phone = _FakeOwnerPhone(phones if phones is not None else {"t1": "+966500000000"})
    trigger = WalletLowBalanceTrigger(owner_phone=owner_phone, sender=sender,
                                      public_base_url=base_url)
    return trigger, sender


def test_a_real_event_sends_the_notice_from_the_platform_number():
    trigger, sender = _trigger()
    ok = run(trigger.handle({"tenant": "t1", "balance": 400, "threshold": 1000}))
    assert ok is True
    assert sender.sent == [{"tenant": "_platform", "to": "+966500000000",
                            "template_name": "ai_wallet_low_balance",
                            "variables": ["https://ra-je3.com"],
                            "idempotency_key": "walletlow:t1:1000"}]


def test_no_tenant_sends_nothing():
    trigger, sender = _trigger()
    ok = run(trigger.handle({"balance": 400, "threshold": 1000}))
    assert ok is False
    assert sender.sent == []


def test_a_tenant_with_no_reachable_owner_sends_nothing():
    trigger, sender = _trigger(phones={})
    ok = run(trigger.handle({"tenant": "t1", "threshold": 1000}))
    assert ok is False
    assert sender.sent == []


def test_a_trailing_slash_on_the_base_url_is_stripped():
    trigger, sender = _trigger(base_url="https://ra-je3.com/")
    run(trigger.handle({"tenant": "t1", "threshold": 1000}))
    assert sender.sent[0]["variables"] == ["https://ra-je3.com"]


def test_two_different_tenants_are_independent():
    trigger, sender = _trigger(phones={"t1": "+9665A", "t2": "+9665B"})
    run(trigger.handle({"tenant": "t1", "threshold": 1000}))
    run(trigger.handle({"tenant": "t2", "threshold": 500}))
    got = {(s["to"], s["idempotency_key"]) for s in sender.sent}
    assert got == {("+9665A", "walletlow:t1:1000"), ("+9665B", "walletlow:t2:500")}


def test_the_idempotency_key_reflects_the_crossed_threshold_not_a_guess():
    # a threshold change re-arms server-side (wallet-service's own crossing-dedup) and fires a NEW
    # event — the key here follows that same crossing identity, never a random or time-based one.
    trigger, sender = _trigger()
    run(trigger.handle({"tenant": "t1", "threshold": 1000}))
    run(trigger.handle({"tenant": "t1", "threshold": 500}))
    assert [s["idempotency_key"] for s in sender.sent] == ["walletlow:t1:1000", "walletlow:t1:500"]
