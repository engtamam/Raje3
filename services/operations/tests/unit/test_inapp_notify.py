"""What `InAppNotifier` actually puts on the wire — same "capture instead of mock the whole class"
discipline as `test_loyalty_desk_body.py` beside this file: a route test that stands in for
`container.inapp_notifier` proves nothing about the JSON the real adapter builds.
"""
from __future__ import annotations

import asyncio

from app.adapters.inapp_notify import InAppNotifier


class _Captured(Exception):
    def __init__(self, body: dict):
        self.body = body
        super().__init__("captured")


def _body_of(**kw) -> dict:
    desk = InAppNotifier(base_url="http://notification-service.invalid", token="t" * 40)

    def _fake(body):
        raise _Captured(body)

    desk._call = _fake                                   # noqa: SLF001 — the seam under test
    try:
        asyncio.run(desk.send(**kw))
    except _Captured as got:
        return got.body
    raise AssertionError("the notifier did not send a request")


def test_the_channel_is_always_inapp():
    body = _body_of(tenant="t1", user_id="usr_1", template_key="operations.staff_rating_dropped")
    assert body["channel"] == "inapp"


def test_recipient_and_user_id_are_the_same_person():
    """`notify()`'s own delivery path keys the stored feed item on `user_id or recipient` — sending
    both, and both equal to the same subject, is what makes a later `feed(subject)` read find it."""
    body = _body_of(tenant="t1", user_id="usr_1", template_key="operations.staff_rating_dropped")
    assert body["recipient"] == "usr_1"
    assert body["user_id"] == "usr_1"


def test_a_distinct_idempotency_key_reaches_the_wire_per_call():
    """Regression: notification-service dedupes by (tenant, idempotency_key) alone, never by
    recipient — reusing one key across two different managers of the same tenant would deliver to
    the first and silently skip the second as "already sent". Each call must carry whatever key
    the caller gave it, verbatim."""
    body_a = _body_of(tenant="t1", user_id="mgr_a", template_key="x", idempotency_key="evt:mgr_a")
    body_b = _body_of(tenant="t1", user_id="mgr_b", template_key="x", idempotency_key="evt:mgr_b")
    assert body_a["idempotency_key"] == "evt:mgr_a"
    assert body_b["idempotency_key"] == "evt:mgr_b"
    assert body_a["idempotency_key"] != body_b["idempotency_key"]


def test_variables_and_locale_pass_through_untouched():
    body = _body_of(tenant="t1", user_id="usr_1", template_key="operations.staff_rating_dropped",
                    variables={"name": "سارة", "rating": "2.3"}, locale="en")
    assert body["variables"] == {"name": "سارة", "rating": "2.3"}
    assert body["locale"] == "en"


def test_an_unconfigured_notifier_sends_nothing_and_refuses_quietly():
    async def run():
        desk = InAppNotifier(base_url="", token="t" * 40)
        return await desk.send(tenant="t1", user_id="usr_1", template_key="x")
    assert asyncio.run(run()) is False
