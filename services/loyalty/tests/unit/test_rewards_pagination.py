"""loyalty-006 (QA audit, 2026-09-12): Rewards.list() capped the catalogue at a single 500-row
page with no pagination — a shop with more rewards than that silently lost some from every reader
(the rewards list, `affordable()`, the portal balance)."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.rewards import Rewards

T = "shop"


def run(c):
    return asyncio.run(c)


def test_list_reads_past_a_single_page_of_rewards():
    store = MemoryDataStore()
    rewards = Rewards(store)
    for i in range(550):
        run(rewards.create(T, name=f"مكافأة {i:04d}", cost=10 + i, type="item"))
    out = run(rewards.list(T, active_only=False))
    assert len(out) == 550
