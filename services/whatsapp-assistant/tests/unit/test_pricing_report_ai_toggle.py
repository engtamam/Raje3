"""core/pricing_report.py::report() — the AI_ASSISTANT_ENABLED gate.

A real behavioural proof, not just a response-shape one: `ai_enabled=False` must skip the
COST_LEDGER read ENTIRELY (never "read then hide the numbers"), so the store stub here raises if
`scan_all` is ever called while the switch is off.
"""
from __future__ import annotations

import time

import pytest

from app.core.pricing_report import report


class _ScanAllForbidden:
    async def scan_all(self, *args, **kwargs):
        raise AssertionError("scan_all must never be called while AI_ASSISTANT_ENABLED is False")


class _ScanAllSpy:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.calls = 0

    async def scan_all(self, *args, **kwargs):
        self.calls += 1
        return self._rows


@pytest.mark.anyio
async def test_ai_disabled_never_reads_the_ledger_and_every_field_is_none():
    now = int(time.time())
    rep = await report(_ScanAllForbidden(), days=30, now=now, ai_enabled=False)

    assert rep.ai_enabled is False
    assert rep.calls is None
    assert rep.conversations is None
    assert rep.input_tokens is None
    assert rep.output_tokens is None
    assert rep.truncated is False
    assert rep.avg_input_tokens_per_call is None
    assert rep.avg_output_tokens_per_call is None
    assert rep.avg_calls_per_conversation is None
    assert rep.as_dict() == {
        "days": 30, "ai_enabled": False, "calls": None, "conversations": None,
        "input_tokens": None, "output_tokens": None, "avg_input_tokens_per_call": None,
        "avg_output_tokens_per_call": None, "avg_calls_per_conversation": None,
        "truncated": False,
    }


@pytest.mark.anyio
async def test_ai_enabled_true_is_unchanged_from_before_the_gate_existed():
    now = int(time.time())
    rows = [
        {"tenant": "shop-a", "subject_ref": "s1", "at": now - 10,
         "input_tokens": 100, "output_tokens": 50},
        {"tenant": "shop-a", "subject_ref": "s2", "at": now - 5,
         "input_tokens": 20, "output_tokens": 10},
    ]
    store = _ScanAllSpy(rows)
    rep = await report(store, days=30, now=now, tenant="shop-a", ai_enabled=True)

    assert store.calls == 1
    assert rep.ai_enabled is True
    assert rep.calls == 2
    assert rep.conversations == 2
    assert rep.input_tokens == 120
    assert rep.output_tokens == 60
    assert rep.avg_input_tokens_per_call == 60.0
    assert rep.avg_calls_per_conversation == 1.0


@pytest.mark.anyio
async def test_ai_enabled_defaults_to_true_for_every_other_existing_caller():
    """`ai_enabled` defaults True so no caller written before this gate existed silently starts
    getting None back."""
    store = _ScanAllSpy([])
    rep = await report(store, days=30, now=int(time.time()))
    assert rep.ai_enabled is True
    assert rep.calls == 0
