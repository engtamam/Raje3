"""«هل وصلت؟» — the question this service could not answer about its own work.

Every message ever sent was recorded as `sent` and nothing more, because the sender returned no
handle and no receipt could be matched to a row. These tests hold the wire end to end: the handle
comes back from the send, lands on the log row, and a receipt walks forward onto it.
"""
from __future__ import annotations

import asyncio

import pytest
from app.adapters.datastore.memory import MemoryDataStore
from app.core.receipts import CURSOR_KEY, RECEIPT_WATERMARKS, Receipts
from app.core.stores import SendLogStore

T = "t_receipts"


def run(c):
    return asyncio.run(c)


class Feed:
    """Pages of receipts, and the ability to be unreadable — which is a different answer."""
    configured = True

    def __init__(self, pages):
        self.pages = pages
        self.asked = []

    async def receipts(self, *, after: str = ""):
        self.asked.append(after)
        return self.pages.pop(0) if self.pages else {"receipts": [], "cursor": after}


@pytest.fixture()
def st():
    return MemoryDataStore()


@pytest.fixture()
def log(st):
    return SendLogStore(st)


def _sent(log, *, send_id: str, delivery_id: str):
    run(log.append(T, {"id": send_id, "tenant": T, "subject_ref": "ref_a", "cls": "service",
                       "at": 1000, "outcome": "sent", "delivery_id": delivery_id}))


def test_a_delivery_receipt_lands_on_the_row_it_belongs_to(st, log):
    _sent(log, send_id="snd_1", delivery_id="dlv_1")
    feed = Feed([{"receipts": [{"delivery_id": "dlv_1", "receipt_status": "delivered",
                                "receipt_ts": 1500}], "cursor": "c1"}])
    out = run(Receipts(store=st, log=log, feed=feed).run())
    assert out["matched"] == 1
    row = run(log.get(T, "snd_1"))
    assert row["delivered_at"] == 1500
    # DELIVERED IS NOT READ. A handset that received a message at 3am tells us nothing about the
    # person, and a product that collapsed the two would call him engaged.
    assert int(row.get("read_at") or 0) == 0


def test_read_and_delivered_are_recorded_separately(st, log):
    _sent(log, send_id="snd_2", delivery_id="dlv_2")
    feed = Feed([{"receipts": [
        {"delivery_id": "dlv_2", "receipt_status": "delivered", "receipt_ts": 1500},
        {"delivery_id": "dlv_2", "receipt_status": "read", "receipt_ts": 1600}], "cursor": "c1"}])
    run(Receipts(store=st, log=log, feed=feed).run())
    row = run(log.get(T, "snd_2"))
    assert row["delivered_at"] == 1500 and row["read_at"] == 1600


def test_an_out_of_order_receipt_never_walks_a_row_backwards(st, log):
    """Meta's callbacks are not ordered, and a page re-read after a crash replays them. Both must
    leave the row saying the furthest thing that actually happened."""
    _sent(log, send_id="snd_3", delivery_id="dlv_3")
    feed = Feed([{"receipts": [
        {"delivery_id": "dlv_3", "receipt_status": "read", "receipt_ts": 1600},
        {"delivery_id": "dlv_3", "receipt_status": "read", "receipt_ts": 1200}], "cursor": "c1"}])
    run(Receipts(store=st, log=log, feed=feed).run())
    assert run(log.get(T, "snd_3"))["read_at"] == 1600


def test_the_cursor_moves_only_after_the_writes_and_never_on_an_unreadable_peer(st, log):
    """THE AT-MOST-ONCE DOCTRINE. Advancing on receipt moves the watermark past the very rows the
    catch-up exists to collect, and a window skipped here is a message recorded as never delivered
    for ever."""
    _sent(log, send_id="snd_4", delivery_id="dlv_4")
    feed = Feed([{"receipts": [{"delivery_id": "dlv_4", "receipt_status": "read",
                                "receipt_ts": 1700}], "cursor": "c9"}])
    run(Receipts(store=st, log=log, feed=feed).run())
    assert run(st.get(RECEIPT_WATERMARKS, CURSOR_KEY))["cursor"] == "c9"

    class Unreadable(Feed):
        async def receipts(self, *, after: str = ""):
            self.asked.append(after)
            return {}

    dead = Unreadable([])
    out = run(Receipts(store=st, log=log, feed=dead).run())
    assert out.get("unreadable") is True
    # Held exactly where it was, and asked from there — not from the beginning, and not past it.
    assert run(st.get(RECEIPT_WATERMARKS, CURSOR_KEY))["cursor"] == "c9"
    assert dead.asked == ["c9"]


def test_a_receipt_for_a_send_we_did_not_make_is_not_invented(st, log):
    """The notification peer serves the whole fleet. A receipt naming a delivery this service never
    made belongs to somebody else — or to a row retention already trimmed."""
    feed = Feed([{"receipts": [{"delivery_id": "dlv_stranger", "receipt_status": "read",
                                "receipt_ts": 1500}], "cursor": "c1"}])
    out = run(Receipts(store=st, log=log, feed=feed).run())
    assert out["read"] == 1 and out["matched"] == 0


def test_an_unknown_status_is_ignored_rather_than_guessed_at(st, log):
    """A new WhatsApp state must not silently become a read receipt."""
    _sent(log, send_id="snd_5", delivery_id="dlv_5")
    feed = Feed([{"receipts": [{"delivery_id": "dlv_5", "receipt_status": "warning",
                                "receipt_ts": 1500}], "cursor": "c1"}])
    run(Receipts(store=st, log=log, feed=feed).run())
    row = run(log.get(T, "snd_5"))
    assert int(row.get("read_at") or 0) == 0 and int(row.get("delivered_at") or 0) == 0


def test_a_peer_that_is_not_configured_says_so_instead_of_reporting_zero(st, log):
    """A zero with no reason reads as «every message accounted for» — the silent-success shape this
    whole path answers."""
    out = run(Receipts(store=st, log=log, feed=None).run())
    assert out["configured"] is False and out["matched"] == 0


def test_the_send_log_row_carries_the_handle_the_receipt_will_name(st):
    """THE WIRE, END TO END, and the half that was missing. A reconciler that works perfectly
    against rows nobody stamps is the same defect wearing a different hat: `delivery_id` has to be
    on the row before any receipt can find it.

    Asserted against the fake sender rather than a hand-built dict, so the shape under test is the
    one the port actually returns."""
    from app.adapters.message_sender import NullSender

    sender = NullSender()
    handle = run(sender.send(tenant=T, subject_ref="ref_b", template_name="svc_service_reminder",
                             variables=["أحمد"], cls="service", idempotency_key="idem-77"))
    assert handle, "a send that returns no handle can never be matched to a receipt"

    log = SendLogStore(st)
    run(log.append(T, {"id": "snd_w", "tenant": T, "subject_ref": "ref_b", "cls": "service",
                       "at": 1000, "outcome": "sent", "delivery_id": handle}))
    feed = Feed([{"receipts": [{"delivery_id": handle, "receipt_status": "read",
                                "receipt_ts": 2000}], "cursor": "c1"}])
    assert run(Receipts(store=st, log=log, feed=feed).run())["matched"] == 1
    assert run(log.get(T, "snd_w"))["read_at"] == 2000
