"""RenewalRequestStore (one row per sent renewal Flow, resolved once) and RenewalConsumer (bus
event -> a delivered pay-link template send, or nothing)."""
from __future__ import annotations

import asyncio
import json

from app.adapters.datastore.memory import MemoryDataStore
from app.core.renewal_consumer import RenewalConsumer
from app.core.renewal_request import RenewalRequestStore


def run(c):
    return asyncio.run(c)


def _msg(flow_token: str, pay_url: str = "https://pay.raje3.sa/x") -> dict:
    payload = {"flow_token": flow_token, "reward_ref": pay_url}
    return {"type": "interactive",
            "interactive": {"type": "nfm_reply",
                            "nfm_reply": {"response_json": json.dumps(payload)}}}


class _FakeSender:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_template(self, **kwargs):
        self.sent.append(kwargs)
        return "dlv_1"


# ── RenewalRequestStore ──────────────────────────────────────────────────────────────────────
def test_a_remembered_request_resolves_with_everything_it_was_given():
    store = RenewalRequestStore(MemoryDataStore())
    run(store.remember(flow_token="tok_1", tenant="t1", to="966500000000", now=1000))
    got = run(store.resolve("tok_1"))
    assert got is not None
    assert (got.tenant, got.to, got.sent_at) == ("t1", "966500000000", 1000)


def test_resolving_consumes_the_row_a_second_resolve_finds_nothing():
    store = RenewalRequestStore(MemoryDataStore())
    run(store.remember(flow_token="tok_1", tenant="t1", to="966500000000", now=1000))
    run(store.resolve("tok_1"))
    assert run(store.resolve("tok_1")) is None


def test_an_unknown_token_resolves_to_none():
    assert run(RenewalRequestStore(MemoryDataStore()).resolve("never-sent")) is None


def test_an_empty_token_resolves_to_none():
    assert run(RenewalRequestStore(MemoryDataStore()).resolve("")) is None


# ── RenewalConsumer ───────────────────────────────────────────────────────────────────────────
def _consumer():
    store = MemoryDataStore()
    sender = _FakeSender()
    requests = RenewalRequestStore(store)
    return RenewalConsumer(requests=requests, sender=sender), requests, sender


def test_a_matched_reply_sends_the_template_with_the_pay_url_and_returns_true():
    consumer, requests, sender = _consumer()
    run(requests.remember(flow_token="tok_1", tenant="t1", to="966500000000", now=1000))
    ok = run(consumer.handle(_msg("tok_1", "https://pay.raje3.sa/x")))
    assert ok is True
    # tenant is ALWAYS "_platform" — same conversation, same sending identity the trigger used.
    assert sender.sent == [{"tenant": "_platform", "to": "966500000000",
                            "template_name": "subscription_renewal_link",
                            "variables": ["https://pay.raje3.sa/x"],
                            "idempotency_key": "renewal_link:tok_1"}]


def test_an_unmatched_token_sends_nothing_and_returns_false():
    consumer, _requests, sender = _consumer()
    ok = run(consumer.handle(_msg("no-such-token")))
    assert ok is False
    assert sender.sent == []


def test_a_non_renewal_message_sends_nothing():
    consumer, _requests, sender = _consumer()
    ok = run(consumer.handle({"type": "text", "text": {"body": "hi"}}))
    assert ok is False
    assert sender.sent == []


def test_a_second_delivery_of_the_same_reply_is_a_no_op_the_second_time():
    consumer, requests, sender = _consumer()
    run(requests.remember(flow_token="tok_1", tenant="t1", to="966500000000", now=1000))
    first = run(consumer.handle(_msg("tok_1")))
    second = run(consumer.handle(_msg("tok_1")))
    assert (first, second) == (True, False)
    assert len(sender.sent) == 1


def test_an_empty_message_does_not_raise():
    consumer, _requests, sender = _consumer()
    assert run(consumer.handle({})) is False
    assert sender.sent == []


def test_two_different_shops_renewals_processed_in_sequence_both_land():
    consumer, requests, sender = _consumer()
    run(requests.remember(flow_token="tok_a", tenant="t1", to="9665A", now=1000))
    run(requests.remember(flow_token="tok_b", tenant="t2", to="9665B", now=1000))
    run(consumer.handle(_msg("tok_a", "https://pay.raje3.sa/a")))
    run(consumer.handle(_msg("tok_b", "https://pay.raje3.sa/b")))
    # both go out under "_platform" — the real tenant (t1/t2) only distinguished the recipient.
    got = {(s["tenant"], s["to"], s["variables"][0]) for s in sender.sent}
    assert got == {("_platform", "9665A", "https://pay.raje3.sa/a"),
                   ("_platform", "9665B", "https://pay.raje3.sa/b")}
