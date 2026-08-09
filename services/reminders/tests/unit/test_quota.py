"""The message quota — the counter money depends on.

Every test here is a way of getting this wrong that leaves the product looking healthy: messages
go out, graphs are green, and the only evidence is a WhatsApp bill or a balance that drains faster
than the ledger explains.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core import quota as Q

T = "shop"


def run(c):
    return asyncio.run(c)


class FakeBilling:
    """billing-service's two enforcing calls, with real idempotency.

    Idempotency is modelled rather than stubbed, because "the retry consumed a second unit" is the
    defect these tests exist to catch, and a fake that ignores the key cannot show it.
    """

    def __init__(self, limit: int = 3, *, entitled: bool = True) -> None:
        self.limit = limit
        self.used = 0
        self.entitled = entitled
        self.seen: dict[str, int] = {}
        self.unreachable = False

    def post(self, url: str, body: dict):
        if self.unreachable:
            raise Q.QuotaError("unreachable: connection refused")
        key = body.get("idempotency_key") or ""
        amount = int(body.get("amount", 1))
        if url.endswith("consume"):
            if not self.entitled:
                return 200, {"allowed": False, "error": "NOT_ENTITLED"}
            if key in self.seen:
                # ALREADY COUNTED. The peer replays the original answer rather than charging again.
                return 200, {"allowed": True, "current": self.used, "replayed": True}
            if self.used + amount > self.limit:
                return 200, {"allowed": False, "error": "LIMIT_REACHED",
                             "current": self.used, "limit": self.limit}
            self.used += amount
            self.seen[key] = amount
            return 200, {"allowed": True, "current": self.used, "limit": self.limit}
        if url.endswith("release"):
            if key in self.seen:
                self.used -= self.seen.pop(key)
            return 200, {"released": True}
        raise AssertionError(f"unexpected call to {url}")


def quota(fake: FakeBilling) -> Q.HttpQuota:
    q = Q.HttpQuota(billing_url="http://billing", consume_path="/internal/billing/usage/consume",
                    release_path="/internal/billing/usage/release",
                    check_path="/internal/billing/entitlements/check", token="t")
    q._post = fake.post          # noqa: SLF001 — the seam under test is what we send, not urllib
    return q


# ── the unit is spent, once ────────────────────────────────────────────────────────────────────
def test_a_send_spends_one_message():
    f = FakeBilling(limit=3)
    run(quota(f).consume(tenant=T, idempotency_key="rem_1"))
    assert f.used == 1


def test_a_retry_with_the_same_key_spends_nothing_more():
    """THE EXPENSIVE ONE. The bus is at-least-once and the tick retries; a fresh key per attempt
    would burn a unit of somebody's quota per redelivery, with no duplicate message to show for it
    because the sender de-duplicates. The balance drains and the ledger cannot explain it."""
    f = FakeBilling(limit=3)
    q = quota(f)
    run(q.consume(tenant=T, idempotency_key="rem_1"))
    run(q.consume(tenant=T, idempotency_key="rem_1"))
    run(q.consume(tenant=T, idempotency_key="rem_1"))
    assert f.used == 1


def test_two_different_sends_spend_two():
    f = FakeBilling(limit=3)
    q = quota(f)
    run(q.consume(tenant=T, idempotency_key="rem_1"))
    run(q.consume(tenant=T, idempotency_key="rem_2"))
    assert f.used == 2


# ── the limit is a wall, not a suggestion ──────────────────────────────────────────────────────
def test_the_send_is_refused_when_the_month_is_exhausted():
    f = FakeBilling(limit=2)
    q = quota(f)
    run(q.consume(tenant=T, idempotency_key="a"))
    run(q.consume(tenant=T, idempotency_key="b"))
    with pytest.raises(Q.QuotaError):
        run(q.consume(tenant=T, idempotency_key="c"))
    assert f.used == 2


def test_being_out_says_something_different_from_never_having_any():
    """Telling an owner he has used this month's messages when his plan never included any is how
    a support call starts — and the plans carry the key with a 0 precisely so the two are
    distinguishable."""
    out = FakeBilling(limit=0)
    never = FakeBilling(entitled=False)
    with pytest.raises(Q.QuotaError) as e1:
        run(quota(out).consume(tenant=T, idempotency_key="a"))
    with pytest.raises(Q.QuotaError) as e2:
        run(quota(never).consume(tenant=T, idempotency_key="a"))
    assert str(e1.value) != str(e2.value)
    assert "باقتك" in str(e2.value)


# ── failure gives it back ──────────────────────────────────────────────────────────────────────
def test_a_release_returns_the_unit():
    """The consume must come first to be atomic, so a send that then fails leaves a unit spent.
    Without the release an establishment pays for every template still in Meta's review — which,
    for a shop that connected this morning, is the whole library."""
    f = FakeBilling(limit=3)
    q = quota(f)
    run(q.consume(tenant=T, idempotency_key="rem_1"))
    run(q.release(tenant=T, idempotency_key="rem_1"))
    assert f.used == 0


def test_a_released_unit_can_be_spent_again():
    f = FakeBilling(limit=1)
    q = quota(f)
    run(q.consume(tenant=T, idempotency_key="rem_1"))
    run(q.release(tenant=T, idempotency_key="rem_1"))
    run(q.consume(tenant=T, idempotency_key="rem_2"))
    assert f.used == 1


def test_a_release_that_itself_fails_does_not_raise():
    """The send has already failed and is being rescheduled. Failing a second time over an
    accounting call would turn one lost unit into a lost reminder."""
    f = FakeBilling(limit=3)
    q = quota(f)
    run(q.consume(tenant=T, idempotency_key="rem_1"))
    f.unreachable = True
    run(q.release(tenant=T, idempotency_key="rem_1"))     # must not raise


# ── unreachable ────────────────────────────────────────────────────────────────────────────────
def test_an_unreachable_billing_refuses_the_send():
    """FAILS CLOSED, and this is the uncomfortable one. Sending anyway is the generous choice: an
    unreachable peer lasts hours, WhatsApp messages cost money each, and 'we could not check so we
    sent everything' has no bottom. The tick retries; nothing is lost."""
    f = FakeBilling(limit=100)
    f.unreachable = True
    with pytest.raises(Q.QuotaError):
        run(quota(f).consume(tenant=T, idempotency_key="a"))


def test_the_refusal_is_in_arabic_and_says_what_to_do():
    f = FakeBilling(limit=0)
    with pytest.raises(Q.QuotaError) as e:
        run(quota(f).consume(tenant=T, idempotency_key="a"))
    assert "رصيد" in str(e.value) and "باقة" in str(e.value)


def test_the_key_is_one_name_defined_once():
    """A typo would create a second counter nobody has a limit for, which resolves deny-by-default
    and looks exactly like an exhausted quota."""
    assert Q.KEY == "messages.monthly"
