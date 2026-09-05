"""RatingRequestStore (one row per sent Flow, resolved once) and RatingConsumer (bus event ->
written rating, or nothing)."""
from __future__ import annotations

import asyncio
import json

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.rating_consumer import RatingConsumer
from app.core.rating_request import RatingRequestStore
from app.core.rating_writer import NullRatingWriter


def run(c):
    return asyncio.run(c)


def _msg(flow_token: str, stars: str = "5", comment: str = ""):
    payload = {"flow_token": flow_token, "stars": stars}
    if comment:
        payload["comment"] = comment
    return {"type": "interactive",
            "interactive": {"type": "nfm_reply",
                            "nfm_reply": {"response_json": json.dumps(payload)}}}


@pytest.fixture()
def requests_store():
    return RatingRequestStore(MemoryDataStore())


# ── RatingRequestStore ────────────────────────────────────────────────────────────────────────
def test_a_remembered_request_resolves_with_everything_it_was_given(requests_store):
    run(requests_store.remember(flow_token="rate:vis_1", tenant="t1", subject_ref="sub_a",
                                visit_id="vis_1", now=1000))
    got = run(requests_store.resolve("rate:vis_1"))
    assert got is not None
    assert (got.tenant, got.subject_ref, got.visit_id, got.sent_at) == ("t1", "sub_a", "vis_1", 1000)


def test_resolving_consumes_the_row_a_second_resolve_finds_nothing(requests_store):
    run(requests_store.remember(flow_token="rate:vis_1", tenant="t1", subject_ref="sub_a",
                                visit_id="vis_1", now=1000))
    run(requests_store.resolve("rate:vis_1"))
    assert run(requests_store.resolve("rate:vis_1")) is None


def test_an_unknown_token_resolves_to_none(requests_store):
    assert run(requests_store.resolve("never-sent")) is None


def test_an_empty_token_resolves_to_none_without_touching_the_store(requests_store):
    assert run(requests_store.resolve("")) is None


def test_two_different_visits_remembered_at_once_resolve_independently(requests_store):
    run(requests_store.remember(flow_token="t_a", tenant="t1", subject_ref="sub_a",
                                visit_id="vis_a", now=1000))
    run(requests_store.remember(flow_token="t_b", tenant="t1", subject_ref="sub_b",
                                visit_id="vis_b", now=1000))
    a = run(requests_store.resolve("t_a"))
    b = run(requests_store.resolve("t_b"))
    assert (a.visit_id, b.visit_id) == ("vis_a", "vis_b")
    # and resolving one leaves the other still there before ITS resolve
    run(requests_store.remember(flow_token="t_c", tenant="t1", subject_ref="sub_c",
                                visit_id="vis_c", now=1000))
    assert run(requests_store.resolve("t_c")) is not None


# ── RatingConsumer ────────────────────────────────────────────────────────────────────────────
def _consumer():
    store = MemoryDataStore()
    writer = NullRatingWriter()
    requests = RatingRequestStore(store)
    return RatingConsumer(requests=requests, writer=writer), requests, writer


def test_a_matched_reply_writes_the_rating_and_returns_true():
    consumer, requests, writer = _consumer()
    run(requests.remember(flow_token="rate:vis_1", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_1", now=1000))
    ok = run(consumer.handle(_msg("rate:vis_1", stars="4", comment="جيد")))
    assert ok is True
    assert writer.written == [{"tenant": "t1", "visit_id": "vis_1", "rating": 4,
                               "feedback_text": "جيد"}]


def test_an_unmatched_token_writes_nothing_and_returns_false():
    consumer, _requests, writer = _consumer()
    ok = run(consumer.handle(_msg("no-such-token", stars="5")))
    assert ok is False
    assert writer.written == []


def test_a_non_rating_message_writes_nothing():
    consumer, _requests, writer = _consumer()
    ok = run(consumer.handle({"type": "text", "text": {"body": "hi"}}))
    assert ok is False
    assert writer.written == []


def test_a_second_delivery_of_the_same_reply_is_a_no_op_the_second_time():
    # Meta's own webhook retry, or a duplicate bus delivery — the token was already consumed.
    consumer, requests, writer = _consumer()
    run(requests.remember(flow_token="rate:vis_1", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_1", now=1000))
    first = run(consumer.handle(_msg("rate:vis_1", stars="5")))
    second = run(consumer.handle(_msg("rate:vis_1", stars="1")))
    assert (first, second) == (True, False)
    assert len(writer.written) == 1
    assert writer.written[0]["rating"] == 5              # the retry never overwrote it


def test_an_empty_message_does_not_raise():
    consumer, _requests, writer = _consumer()
    assert run(consumer.handle({})) is False
