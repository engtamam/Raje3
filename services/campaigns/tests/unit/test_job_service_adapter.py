"""The `NullJobService` default — the honest "not configured" answer, not a silent no-op that
lets a campaign believe it was scheduled when nothing will ever fire it."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.job_service import JobServiceUnavailable, NullJobService


def run(c):
    return asyncio.run(c)


def test_enqueue_raises_rather_than_pretending():
    with pytest.raises(JobServiceUnavailable):
        run(NullJobService().enqueue(queue="campaigns", tenant="t1", type="campaigns.fire",
                                     payload={}))


def test_claim_returns_nothing_ever():
    assert run(NullJobService().claim(worker="w1", queue="campaigns")) == []


def test_ack_and_nack_are_harmless_no_ops():
    # A claim never returns anything, so these are never called for real — but a stray call
    # (a race, a test double left over) must not raise.
    run(NullJobService().ack("job_1", "lease_1"))
    run(NullJobService().nack("job_1", "lease_1", "error"))
