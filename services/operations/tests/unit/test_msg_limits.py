"""The per-shop customer-message word limit — an owner's own tightened/loosened ceiling, or the
default if he never touched it. See app/core/msg_limits.py's own docstring for why this exists."""
from __future__ import annotations

import asyncio

import pytest

from app.core import msg_limits as ML


def run(coro):
    return asyncio.run(coro)


class _Store:
    def __init__(self, rows=None):
        self.rows = dict(rows or {})

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row


class _Unreadable(_Store):
    async def get(self, collection, key):
        raise RuntimeError("the datastore is down")


# ── sanitise() ────────────────────────────────────────────────────────────────
def test_a_value_within_bounds_is_accepted_unchanged():
    assert ML.sanitise(150) == 150


def test_the_min_and_max_bounds_themselves_are_accepted():
    assert ML.sanitise(ML.MIN_MSG_WORD_LIMIT) == ML.MIN_MSG_WORD_LIMIT
    assert ML.sanitise(ML.MAX_MSG_WORD_LIMIT) == ML.MAX_MSG_WORD_LIMIT


def test_below_the_minimum_is_refused():
    with pytest.raises(ML.MsgWordLimitError):
        ML.sanitise(ML.MIN_MSG_WORD_LIMIT - 1)


def test_above_the_maximum_is_refused():
    with pytest.raises(ML.MsgWordLimitError):
        ML.sanitise(ML.MAX_MSG_WORD_LIMIT + 1)


def test_a_non_integer_is_refused():
    with pytest.raises(ML.MsgWordLimitError):
        ML.sanitise("100")                                  # type: ignore[arg-type]


def test_a_bool_is_refused_despite_being_an_int_subclass():
    with pytest.raises(ML.MsgWordLimitError):
        ML.sanitise(True)                                    # type: ignore[arg-type]


# ── MsgWordLimitStore ──────────────────────────────────────────────────────────
def test_a_shop_that_never_set_anything_reads_back_the_default():
    assert run(ML.MsgWordLimitStore(_Store()).get("t1")) == ML.DEFAULT_MSG_WORD_LIMIT


def test_writing_then_reading_round_trips():
    store = _Store()
    run(ML.MsgWordLimitStore(store).set("t1", 60))
    assert run(ML.MsgWordLimitStore(store).get("t1")) == 60


def test_one_shops_limit_is_not_anothers():
    store = _Store()
    run(ML.MsgWordLimitStore(store).set("t1", 60))
    assert run(ML.MsgWordLimitStore(store).get("t2")) == ML.DEFAULT_MSG_WORD_LIMIT


def test_an_unreadable_row_reads_back_the_default_rather_than_failing_the_screen():
    assert run(ML.MsgWordLimitStore(_Unreadable()).get("t1")) == ML.DEFAULT_MSG_WORD_LIMIT


def test_a_missing_tenant_reads_back_the_default():
    assert run(ML.MsgWordLimitStore(_Store()).get("")) == ML.DEFAULT_MSG_WORD_LIMIT
