"""`AssignmentSettingsStore` (app/core/stores.py) — the shop's own auto-assign algorithm choice.
Phase 1 of the assignment-mode redesign: this store is written and read here, not yet consumed by
`assignment.py` itself (phase 2 teaches the algorithms; this is the setting they will read)."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.stores import AssignmentSettingsStore, DEFAULT_ASSIGNMENT_ALGORITHM


def _run(coro):
    return asyncio.run(coro)


def test_a_tenant_who_never_touched_this_gets_the_easy_default():
    """No row at all — the common case — must answer with the friction-free default, never an
    error and never an empty/undefined algorithm a caller has to guess a fallback for."""
    store = AssignmentSettingsStore(MemoryDataStore())
    got = _run(store.get('tnt_new'))
    assert got == {"algorithm": DEFAULT_ASSIGNMENT_ALGORITHM, "manual_order": []}


def test_an_empty_tenant_is_the_same_safe_default_not_a_crash():
    store = AssignmentSettingsStore(MemoryDataStore())
    assert _run(store.get('')) == {"algorithm": DEFAULT_ASSIGNMENT_ALGORITHM, "manual_order": []}


def test_save_then_get_round_trips_exactly():
    store = AssignmentSettingsStore(MemoryDataStore())
    _run(store.save('tnt_a', algorithm='least_loaded', manual_order=[]))
    assert _run(store.get('tnt_a')) == {"algorithm": "least_loaded", "manual_order": []}


def test_manual_order_round_trips_too():
    store = AssignmentSettingsStore(MemoryDataStore())
    _run(store.save('tnt_a', algorithm='manual_order', manual_order=['op_2', 'op_1', 'op_3']))
    assert _run(store.get('tnt_a')) == {
        "algorithm": "manual_order", "manual_order": ['op_2', 'op_1', 'op_3']}


def test_an_unrecognised_stored_algorithm_falls_back_to_the_default_not_a_crash():
    """A row written by a future version this one does not know yet, or corrupted by hand —
    never trusted blindly, same "unknown means safe default" discipline the rest of this product
    holds for a stale/foreign value."""
    ds = MemoryDataStore()
    store = AssignmentSettingsStore(ds)
    _run(ds.put(store.collection, 'tnt_a', {"algorithm": "some_future_thing", "manual_order": []}))
    assert _run(store.get('tnt_a'))["algorithm"] == DEFAULT_ASSIGNMENT_ALGORITHM


def test_save_refuses_an_unknown_algorithm():
    store = AssignmentSettingsStore(MemoryDataStore())
    with pytest.raises(ValueError):
        _run(store.save('tnt_a', algorithm='best_reviewed', manual_order=[]))


def test_tenants_are_isolated_from_each_other():
    store = AssignmentSettingsStore(MemoryDataStore())
    _run(store.save('tnt_a', algorithm='manual_order', manual_order=['op_1']))
    assert _run(store.get('tnt_b')) == {"algorithm": DEFAULT_ASSIGNMENT_ALGORITHM, "manual_order": []}
