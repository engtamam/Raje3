"""The one sentence that moves an owner to verify — and every case where we say nothing."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.ceiling_notice import Notice, NoticeStore, should_notify

T = "shop"


def run(c):
    return asyncio.run(c)


# ── when to speak ──────────────────────────────────────────────────────────────────────────────
def test_nothing_is_said_until_the_ceiling_actually_costs_him_something():
    """Approaching is not losing. A notice about a limit he has never touched is furniture, and
    the thing that makes this message land is that customers were missed TODAY."""
    assert should_notify(missed=0, ceiling=250, already_told=False) is False


def test_it_speaks_when_customers_were_missed():
    assert should_notify(missed=12, ceiling=50, already_told=False) is True


def test_it_speaks_once_ever_not_once_a_day():
    """A shop at its ceiling is at its ceiling every day until it verifies. A daily notice about
    the same fact is noise — which he silences, and then misses the next thing."""
    assert should_notify(missed=12, ceiling=50, already_told=True) is False


def test_an_unknown_ceiling_says_nothing():
    """There is no ceiling to have hit, so there is nothing true to say."""
    assert should_notify(missed=12, ceiling=0, already_told=False) is False


def test_an_unlimited_ceiling_says_nothing():
    assert should_notify(missed=5, ceiling=-1, already_told=False) is False


# ── what it does NOT do ────────────────────────────────────────────────────────────────────────
def test_it_sends_no_message():
    """A notice to the owner is itself a business-initiated message: same ceiling, same bill. It
    would be spent from the allowance it reports on, at exactly the moment there is none left —
    refused by Meta every day the condition lasted. The fact is recorded; nothing is sent."""
    import app.core.ceiling_notice as CN

    assert not hasattr(CN, "text"), "the sentence was dropped with the send"
    assert not hasattr(CN, "TEMPLATE"), "no template is needed for a thing that is not sent"


# ── the record ─────────────────────────────────────────────────────────────────────────────────
def test_a_shop_not_yet_told_is_not_marked():
    assert run(NoticeStore(MemoryDataStore()).told(T)) is False


def test_recording_stops_it_recurring():
    s = NoticeStore(MemoryDataStore())
    run(s.record(Notice(tenant=T, reached=35, ceiling=50, missed=12)))
    assert run(s.told(T)) is True
    assert should_notify(missed=99, ceiling=50, already_told=True) is False


def test_the_record_keeps_the_numbers_it_was_sent_about():
    """The day he asks why he got it, the answer must not need a log."""
    s = NoticeStore(MemoryDataStore())
    run(s.record(Notice(tenant=T, reached=35, ceiling=50, missed=12)))
    row = run(s.last(T))
    assert row["missed"] == 12 and row["ceiling"] == 50


def test_one_shop_is_not_another():
    s = NoticeStore(MemoryDataStore())
    run(s.record(Notice(tenant="a", missed=1, ceiling=50)))
    assert run(s.told("b")) is False
