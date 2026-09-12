"""insights-r2-007 (QA audit, 2026-09-12): EraseIn/TickIn accepted unbounded tenant/subject/since
values, so a request could push arbitrarily large strings straight into a pseudonym key and a
store lookup before any handler code ran. Field caps match the max_length=128 convention already
used for tenant/subject elsewhere in this service (api/v1/insights.py, api/v1/operator.py)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.internal import EraseIn, TickIn


def test_erase_in_rejects_an_oversized_tenant():
    with pytest.raises(ValidationError):
        EraseIn(tenant="t" * 129, subject="s")


def test_erase_in_rejects_an_oversized_subject():
    with pytest.raises(ValidationError):
        EraseIn(tenant="t", subject="s" * 129)


def test_erase_in_accepts_the_boundary():
    EraseIn(tenant="t" * 128, subject="s" * 128)


def test_tick_in_rejects_an_oversized_tenant():
    with pytest.raises(ValidationError):
        TickIn(tenant="t" * 129)


def test_tick_in_rejects_a_negative_since():
    with pytest.raises(ValidationError):
        TickIn(since=-1)


def test_tick_in_defaults_still_work():
    t = TickIn()
    assert t.tenant == ""
    assert t.since == 0
