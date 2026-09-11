"""The custom-template ceiling — a flat, local, LIFETIME 2000 cap per shop, never billed per plan
and never a monthly allowance."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.template_quota import CUSTOM_TEMPLATE_LIMIT, QuotaError, TemplateQuota

T = "shop"


def run(c):
    return asyncio.run(c)


def quota(limit: int = 5) -> TemplateQuota:
    return TemplateQuota(MemoryDataStore(), limit=limit)


# ── spent, once ─────────────────────────────────────────────────────────────────────────────────
def test_a_submission_spends_one_unit():
    q = quota()
    run(q.take(T))
    out = run(q.remaining(T))
    assert out["current"] == 1


def test_two_different_shops_are_independent():
    q = quota()
    run(q.take(T))
    run(q.take("other_shop"))
    assert run(q.remaining(T))["current"] == 1
    assert run(q.remaining("other_shop"))["current"] == 1


# ── the flat number — never per plan, never per month ─────────────────────────────────────────
def test_the_default_limit_is_the_owners_own_number():
    """No plan is asked, no billing is asked — this is the whole point of retiring the per-app
    sale (owner's own call, 2026-09-11): every shop gets this SAME number, for its whole life."""
    assert CUSTOM_TEMPLATE_LIMIT == 2000


def test_two_concurrent_submissions_near_the_cap_never_both_pass():
    """reminders-006 (QA audit, 2026-09-12): the check-then-write used to be two separate round
    trips with nothing between them — two concurrent submissions AT the cap could both read a
    count under the limit before either wrote the increment. Proved with a slow-yielding store
    wrapper so the two `take()` calls genuinely interleave."""
    class _SlowStore:
        def __init__(self, inner):
            self._inner = inner

        async def get(self, *a, **kw):
            await asyncio.sleep(0)
            return await self._inner.get(*a, **kw)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    store = MemoryDataStore()
    q = TemplateQuota(_SlowStore(store), limit=1)

    async def go():
        return await asyncio.gather(q.take(T), q.take(T), return_exceptions=True)

    out = run(go())
    ok = [o for o in out if o is None]
    refused = [o for o in out if isinstance(o, QuotaError)]
    assert len(ok) == 1, f"expected exactly one submission to succeed, got {out}"
    assert len(refused) == 1
    assert run(TemplateQuota(store, limit=1).remaining(T))["current"] == 1


def test_exhausting_the_limit_refuses_the_next_submission():
    q = quota(limit=2)
    run(q.take(T))
    run(q.take(T))
    with pytest.raises(QuotaError) as exc:
        run(q.take(T))
    assert "بلغت الحدّ الأقصى" in str(exc.value)


def test_it_never_resets_on_its_own():
    """«2000 قالب كأقصى حد» — a TOTAL, never a monthly allowance. Nothing about this counter reads
    the clock at all, so there is no month boundary that could ever bring spent units back."""
    q = quota(limit=1)
    run(q.take(T))
    with pytest.raises(QuotaError):
        run(q.take(T))                                # spent, and stays spent — forever


# ── refunded on a Meta rejection ───────────────────────────────────────────────────────────────
def test_a_release_gives_the_unit_back():
    q = quota(limit=2)
    run(q.take(T))
    run(q.release(T))
    assert run(q.remaining(T))["current"] == 0


def test_a_released_unit_can_be_spent_again():
    q = quota(limit=1)
    run(q.take(T))
    run(q.release(T))
    run(q.take(T))                                    # must not raise — the unit came back
    with pytest.raises(QuotaError):
        run(q.take(T))                                 # and is spent again


def test_a_release_on_a_shop_with_nothing_spent_does_not_go_negative():
    q = quota(limit=2)
    run(q.release(T))                                  # no prior take() — must not raise
    assert run(q.remaining(T))["current"] == 0
