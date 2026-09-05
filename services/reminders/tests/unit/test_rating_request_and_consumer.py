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
                               "feedback_text": "جيد", "subject_ref": "sub_a",
                               "rating_points": 0}]


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


# ── more RatingRequestStore edge cases ─────────────────────────────────────────────────────────
def test_remembering_the_same_token_twice_before_resolve_keeps_the_latest_row(requests_store):
    # A caller retry before any reply arrives — the second remember() should win, not raise.
    run(requests_store.remember(flow_token="t1", tenant="t1", subject_ref="sub_old",
                                visit_id="vis_old", now=1000))
    run(requests_store.remember(flow_token="t1", tenant="t1", subject_ref="sub_new",
                                visit_id="vis_new", now=2000))
    got = run(requests_store.resolve("t1"))
    assert got.visit_id == "vis_new"


def test_a_zero_sent_at_is_held_as_a_real_zero_not_a_missing_value(requests_store):
    run(requests_store.remember(flow_token="t1", tenant="t1", subject_ref="sub_a",
                                visit_id="vis_1", now=0))
    got = run(requests_store.resolve("t1"))
    assert got.sent_at == 0


def test_tenant_and_subject_ref_survive_the_round_trip_exactly(requests_store):
    run(requests_store.remember(flow_token="t1", tenant="tenant-with-dashes_1",
                                subject_ref="sub_" + "z" * 24, visit_id="vis_1", now=1000))
    got = run(requests_store.resolve("t1"))
    assert got.tenant == "tenant-with-dashes_1"
    assert got.subject_ref == "sub_" + "z" * 24


def test_resolving_a_token_that_was_never_remembered_does_not_raise(requests_store):
    assert run(requests_store.resolve("rate:vis_never_sent")) is None


# ── more RatingConsumer edge cases ─────────────────────────────────────────────────────────────
def test_a_writer_that_fails_returns_false_from_the_consumer():
    from app.core.rating_request import RatingRequestStore
    from app.adapters.datastore.memory import MemoryDataStore

    class _FailingWriter:
        async def write(self, **kwargs):
            return False

    requests = RatingRequestStore(MemoryDataStore())
    run(requests.remember(flow_token="t1", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_1", now=1000))
    consumer = RatingConsumer(requests=requests, writer=_FailingWriter())
    assert run(consumer.handle(_msg("t1", stars="5"))) is False


def test_the_token_is_consumed_even_when_the_writer_fails():
    """The reply was real and matched a real pending request — resolving it and then failing to
    write must not leave the token resolvable again (Meta will not resend this reply)."""
    from app.core.rating_request import RatingRequestStore
    from app.adapters.datastore.memory import MemoryDataStore

    class _FailingWriter:
        async def write(self, **kwargs):
            return False

    requests = RatingRequestStore(MemoryDataStore())
    run(requests.remember(flow_token="t1", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_1", now=1000))
    consumer = RatingConsumer(requests=requests, writer=_FailingWriter())
    run(consumer.handle(_msg("t1", stars="5")))
    assert run(requests.resolve("t1")) is None


def test_two_different_customers_ratings_processed_in_sequence_both_land():
    consumer, requests, writer = _consumer()
    run(requests.remember(flow_token="t_a", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_a", now=1000))
    run(requests.remember(flow_token="t_b", tenant="t1", subject_ref="sub_b",
                          visit_id="vis_b", now=1000))
    run(consumer.handle(_msg("t_a", stars="5")))
    run(consumer.handle(_msg("t_b", stars="2")))
    assert {(w["visit_id"], w["rating"]) for w in writer.written} == {("vis_a", 5), ("vis_b", 2)}


def test_a_status_shaped_bus_payload_with_no_rating_content_is_a_no_op():
    consumer, _requests, writer = _consumer()
    # a delivery-receipt-shaped message, not a customer reply at all
    ok = run(consumer.handle({"type": "unknown_event"}))
    assert ok is False
    assert writer.written == []


def test_the_writer_receives_exactly_the_comment_the_customer_sent_including_empty():
    consumer, requests, writer = _consumer()
    run(requests.remember(flow_token="t1", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_1", now=1000))
    run(consumer.handle(_msg("t1", stars="4")))       # no comment
    assert writer.written[0]["feedback_text"] == ""


# ── loyalty bonus wiring (Phase 4) ──────────────────────────────────────────────────────────────
def test_no_bonus_points_callback_credits_nothing_by_default():
    # a consumer built without `bonus_points` (e.g. an older wiring) never invents points.
    consumer, requests, writer = _consumer()
    run(requests.remember(flow_token="t1", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_1", now=1000))
    run(consumer.handle(_msg("t1", stars="5")))
    assert writer.written[0]["rating_points"] == 0
    assert writer.written[0]["subject_ref"] == "sub_a"


def test_bonus_points_callback_result_rides_through_to_the_writer():
    store = MemoryDataStore()
    writer = NullRatingWriter()
    requests = RatingRequestStore(store)

    async def _points(tenant: str) -> int:
        assert tenant == "t1"
        return 25

    consumer = RatingConsumer(requests=requests, writer=writer, bonus_points=_points)
    run(requests.remember(flow_token="t1", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_1", now=1000))
    run(consumer.handle(_msg("t1", stars="5")))
    assert writer.written[0]["rating_points"] == 25
    assert writer.written[0]["subject_ref"] == "sub_a"


def test_bonus_points_callback_returning_zero_credits_nothing():
    store = MemoryDataStore()
    writer = NullRatingWriter()
    requests = RatingRequestStore(store)

    async def _points(tenant: str) -> int:
        return 0    # disabled, unentitled, or points=0 — the callback's own decision

    consumer = RatingConsumer(requests=requests, writer=writer, bonus_points=_points)
    run(requests.remember(flow_token="t1", tenant="t1", subject_ref="sub_a",
                          visit_id="vis_1", now=1000))
    run(consumer.handle(_msg("t1", stars="5")))
    assert writer.written[0]["rating_points"] == 0


def test_bonus_points_callback_is_never_called_for_an_unmatched_token():
    calls = []

    async def _points(tenant: str) -> int:
        calls.append(tenant)
        return 10

    store = MemoryDataStore()
    writer = NullRatingWriter()
    requests = RatingRequestStore(store)
    consumer = RatingConsumer(requests=requests, writer=writer, bonus_points=_points)
    ok = run(consumer.handle(_msg("no-such-token", stars="5")))
    assert ok is False
    assert calls == []
