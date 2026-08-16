"""The message meter — what we record about sends we do not sell.

We stopped selling messages: Meta bills the establishment directly (spec §16.7). So these tests
changed shape with the product. What they guard now is the MEASUREMENT — that a retry does not
inflate it, that a failed send does not count, and that losing it never costs a customer his
message — plus the one refusal that survives, which is a subscription decision rather than a
ceiling.
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


# ── there is no wall of ours any more ──────────────────────────────────────────────────────────
def test_a_send_is_never_refused_for_a_ceiling_of_ours():
    """The plans stopped selling messages: Meta bills the establishment directly. Every plan
    carries the key at -1, and unlimited still increments — so this measures and never blocks."""
    f = FakeBilling(limit=0)          # the peer would refuse if we still asked it to enforce
    q = quota(f)
    run(q.consume(tenant=T, idempotency_key="a"))     # must not raise
    run(q.consume(tenant=T, idempotency_key="b"))


def test_but_an_establishment_with_no_subscription_is_still_stopped():
    """NOT_ENTITLED is a SUBSCRIPTION decision, not a message allowance — the unsubscribed
    establishment (spec §16.4.2), whose sending stops because it is not paying for the service."""
    f = FakeBilling(entitled=False)
    with pytest.raises(Q.QuotaError) as e:
        run(quota(f).consume(tenant=T, idempotency_key="a"))
    assert "اشتراك" in str(e.value)


def test_the_refusal_says_what_to_do_about_it():
    f = FakeBilling(entitled=False)
    with pytest.raises(Q.QuotaError) as e:
        run(quota(f).consume(tenant=T, idempotency_key="a"))
    assert "فعّل" in str(e.value)


def test_no_message_mentions_a_balance_or_a_package():
    """A support line answering for a limit that does not exist is worse than no message. The old
    refusals said 'this month's message balance has run out' and 'your plan does not include
    sending'; neither has been true since we stopped selling messages."""
    f = FakeBilling(entitled=False)
    with pytest.raises(Q.QuotaError) as e:
        run(quota(f).consume(tenant=T, idempotency_key="a"))
    for word in ("رصيد", "باقة رسائل", "انتهى"):
        assert word not in str(e.value)


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
def test_an_unreachable_billing_does_not_stop_the_shop():
    """FAILS OPEN, and this is the reversal. While it metered a paid allowance it had to refuse —
    sending unmetered gave away messages we were paying for. We are not paying for them. Now the
    cost of an unmeasured send is a gap in a report, and the cost of a blocked one is a customer
    who never heard from his shop."""
    f = FakeBilling(limit=100)
    f.unreachable = True
    run(quota(f).consume(tenant=T, idempotency_key="a"))     # must not raise


def test_an_unreachable_billing_loses_the_measurement_and_says_nothing_else():
    f = FakeBilling(limit=100)
    f.unreachable = True
    run(quota(f).consume(tenant=T, idempotency_key="a"))
    assert f.used == 0


# ── the verdict is in the BODY, and it used to be thrown away (ز-3) ─────────────────────────────
def test_a_refusal_that_arrives_with_a_status_still_stops_the_send():
    """NOT_ENTITLED IS THE UNSUBSCRIBED ESTABLISHMENT WHATEVER CARRIES IT.

    billing answers it 200 today. A gateway in front of it, or a later route, can carry the same
    body under a 402 or a 403 — and the status check used to come first and `return`, so the
    verdict was never read. A shop whose subscription lapsed went on sending on its own WhatsApp
    account and on our reputation, which is the whole of ز-3.
    """
    f = FakeBilling()
    f.post = lambda url, body: (402, {"allowed": False, "error": "NOT_ENTITLED"})
    with pytest.raises(Q.QuotaError):
        run(quota(f).consume(tenant=T, idempotency_key="a"))


def test_an_http_fault_with_no_verdict_in_it_loses_the_measurement_not_the_message():
    """A rotated internal token, a wrong path, a 500. None of them is billing saying «no», so none
    of them is a subscription decision — the same case as unreachable, and the same doctrine."""
    f = FakeBilling()
    f.post = lambda url, body: (500, {})
    run(quota(f).consume(tenant=T, idempotency_key="a"))          # must not raise


def test_a_broken_billing_is_not_told_to_the_owner_as_his_own_limit():
    """`take` DOES refuse on a fault — a submission we cannot verify is one we do not hand Meta —
    but the sentence has to be true. A 500 carries no verdict, and «you used up your custom texts
    this month» is a number about his own plan that we cannot defend and that sends him looking
    for a fault in himself."""
    f = FakeBilling()
    f.post = lambda url, body: (500, {})
    with pytest.raises(Q.QuotaError) as exc:
        run(quota(f).take(tenant=T, key=Q.CUSTOM_TEMPLATE_KEY, idempotency_key="a"))
    assert "تعذّر التحقق" in str(exc.value)


def test_a_real_exhausted_plan_still_says_so():
    """The other half: narrowing the sentence above must not blunt the true one."""
    f = FakeBilling()
    f.post = lambda url, body: (200, {"allowed": False, "error": "LIMIT_REACHED"})
    with pytest.raises(Q.QuotaError) as exc:
        run(quota(f).take(tenant=T, key=Q.CUSTOM_TEMPLATE_KEY, idempotency_key="a"))
    assert "بلغت حدّ باقتك" in str(exc.value)


def test_the_body_of_a_4xx_is_read_rather_than_discarded():
    """THE LINE UNDER ALL FOUR ABOVE. `_post` returned `(code, {})` for every HTTPError, so the
    verdict never reached the caller at all and no amount of care in `consume` could have found
    it. Exercised through the real `_post`, because the fake used everywhere else replaces it."""
    import io
    import json
    import urllib.error
    import urllib.request

    q = Q.HttpQuota(billing_url="http://billing", consume_path="/c", release_path="/r",
                    check_path="/k", token="t")
    body = json.dumps({"allowed": False, "error": "NOT_ENTITLED"}).encode()

    def boom(req, timeout=0):
        raise urllib.error.HTTPError("http://billing/c", 402, "Payment Required", {},
                                     io.BytesIO(body))

    original, urllib.request.urlopen = urllib.request.urlopen, boom
    try:
        status, out = q._post("http://billing/c", {})            # noqa: SLF001
    finally:
        urllib.request.urlopen = original
    assert status == 402 and out["error"] == "NOT_ENTITLED"


def test_the_key_is_one_name_defined_once():
    """A typo would create a second counter nobody has a limit for, which resolves deny-by-default
    and looks exactly like an exhausted quota."""
    assert Q.KEY == "messages.monthly"
