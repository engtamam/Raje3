"""app/api/internal.py's tick — the empty-body ("every tenant") fallback and the per-tenant
outbound cap. See test_internal_auth_and_malformed_input.py for the HTTP-level proof; this file
tests the two pieces the route is built from directly.

WHY THIS MATTERS. The platform's CronJob template posts an EMPTY body — one fixed TARGET_URL, no
per-tenant templating (platform/deploy/chart/templates/cronjob.yaml) — so a tick that required
`tenant` in the body would fail on EVERY scheduled invocation while every probe stayed green. This
is the same defect class services/reminders' own /reminders/tick already carries the fix for.
"""
from __future__ import annotations

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.rate_limiter.memory import MemoryRateLimiter
from app.api.internal import _active_tenants, outbound_allowed
from app.core.models import CONVERSATIONS


class _C:
    def __init__(self, datastore, rate_limiter):
        self.datastore = datastore
        self.rate_limiter = rate_limiter


class _Settings:
    CONVERSATION_OUTBOUND_MAX_PER_10MIN = 2
    OUTBOUND_MAX_PER_NUMBER_PER_HOUR = 2


async def test_active_tenants_discovers_every_distinct_tenant_with_a_conversation_row():
    store = MemoryDataStore()
    await store.put(CONVERSATIONS, "t1|sub1", {"tenant": "t1", "subject_ref": "sub1"})
    await store.put(CONVERSATIONS, "t2|sub1", {"tenant": "t2", "subject_ref": "sub1"})
    # A second conversation for a tenant already seen must not duplicate it.
    await store.put(CONVERSATIONS, "t1|sub2", {"tenant": "t1", "subject_ref": "sub2"})

    tenants = await _active_tenants(_C(store, None), limit=2000)
    assert sorted(tenants) == ["t1", "t2"]


async def test_active_tenants_is_empty_when_no_conversation_exists_anywhere():
    store = MemoryDataStore()
    tenants = await _active_tenants(_C(store, None), limit=2000)
    assert tenants == []


async def test_outbound_allowed_true_under_the_cap_false_once_it_is_spent():
    limiter = MemoryRateLimiter(1000, 3600)
    c = _C(MemoryDataStore(), limiter)
    settings = _Settings()
    assert await outbound_allowed(c, settings, "t1") is True
    assert await outbound_allowed(c, settings, "t1") is True
    # The cap is 2 per hour — a third call for the SAME tenant in the same window is refused.
    assert await outbound_allowed(c, settings, "t1") is False


async def test_outbound_allowed_is_a_separate_budget_per_tenant():
    limiter = MemoryRateLimiter(1000, 3600)
    c = _C(MemoryDataStore(), limiter)
    settings = _Settings()
    assert await outbound_allowed(c, settings, "t1") is True
    assert await outbound_allowed(c, settings, "t1") is True
    # t1's budget is spent; t2 is unaffected — a runaway loop on one tenant must not silence every
    # OTHER shop's replies too.
    assert await outbound_allowed(c, settings, "t2") is True
