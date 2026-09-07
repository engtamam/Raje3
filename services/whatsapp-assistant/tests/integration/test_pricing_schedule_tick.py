"""A scheduled pricing change actually lands via the real /tick route — end to end, not just
core/pricing_schedule.py's own unit-level `apply_due` (see tests/unit for that). Uses the shared
`client`/`INTERNAL_TOKEN` fixtures from tests/conftest.py, the same app instance every other
internal-route test in this suite already shares.
"""
from __future__ import annotations

import time

from tests.conftest import INTERNAL_TOKEN


def _container(client):
    return client.app.state.container


async def test_a_due_scheduled_pricing_change_lands_on_the_next_tick(client):
    from app.core.pricing_schedule import schedule

    c = _container(client)
    now = int(time.time())
    # ALREADY DUE — effective_at in the past, exactly what a real 15-day-old schedule looks like
    # the moment the tick that finally applies it runs.
    await schedule(c.datastore, key="PRICING_USAGE_HALALAS_PER_1K_TOKENS", value=40,
                   effective_at=now - 60, actor="test:operator", now=now - 15 * 86_400)

    before = await c.runtime_config.get(
        tenant="", key="PRICING_USAGE_HALALAS_PER_1K_TOKENS", default=0)
    assert before == 0   # not yet applied — the schedule alone never changes the effective value

    resp = client.post("/internal/whatsapp_assistant/tick", json={},
                       headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert resp.status_code == 200, resp.text

    after = await c.runtime_config.get(
        tenant="", key="PRICING_USAGE_HALALAS_PER_1K_TOKENS", default=0)
    assert after == 40   # landed

    from app.core.pricing_schedule import pending

    assert await pending(c.datastore) == []   # and the pending row is gone, not left behind


async def test_a_not_yet_due_scheduled_change_never_lands_early(client):
    from app.core.pricing_schedule import schedule

    c = _container(client)
    now = int(time.time())
    await schedule(c.datastore, key="PRICING_TIER_BASE_HALALAS", value=500,
                   effective_at=now + 10 * 86_400, actor="test:operator", now=now)

    client.post("/internal/whatsapp_assistant/tick", json={},
               headers={"X-Internal-Token": INTERNAL_TOKEN})

    value = await c.runtime_config.get(tenant="", key="PRICING_TIER_BASE_HALALAS", default=0)
    assert value == 0   # ten days out — this tick must not touch it

    from app.core.pricing_schedule import pending

    assert len(await pending(c.datastore)) == 1   # still sitting there, waiting for its own day
