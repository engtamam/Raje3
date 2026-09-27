"""Stage 16: the simulator composing its OWN scenario from a catalog of real, proven moves — never
a human hand-ordering "create a branch, then hire, then visit". `common/story.py`'s generic
composer + `apps/operations/story.py`'s own step catalog, run against a real spawned
services/operations.
"""
from __future__ import annotations

import asyncio
import random

from simulator.apps.operations.service import spawn as spawn_operations
from simulator.apps.operations.story import build_steps, new_world
from simulator.common.story import compose_story

TENANT = "sim-story"


def run(coro):
    return asyncio.run(coro)


def test_the_composer_picks_a_real_varied_multi_step_narrative_entirely_on_its_own():
    """The main proof: given only a catalog of possible moves and a starting (empty) world, the
    composer runs a real, multi-step story — more than one DISTINCT kind of move, every single
    call a genuinely valid one against whatever the PRIOR step actually left behind — with no
    human specifying which move comes after which."""

    async def _go():
        async with spawn_operations() as svc:
            steps = build_steps(svc.base_url, TENANT)
            return await compose_story(steps, world=new_world(), max_steps=40,
                                       rng=random.Random(1))

    result = run(_go())
    assert len(result.history) > 10, "a real, non-trivial story should run many moves"
    distinct_moves = set(result.step_names)
    assert len(distinct_moves) >= 4, \
        f"a realistic narrative should touch several kinds of moves, not repeat one: {distinct_moves}"
    assert result.ok_count == len(result.history), \
        "every move the composer chose must have been a genuinely valid one, never refused"


def test_two_different_random_seeds_produce_two_different_stories():
    """Proves this is genuinely composed, not a fixed script with a random-looking label: two
    different seeds must pick a different SEQUENCE of moves — the composer, not a human, is
    deciding the order."""

    async def _go(seed: int):
        async with spawn_operations() as svc:
            steps = build_steps(svc.base_url, TENANT)
            result = await compose_story(steps, world=new_world(), max_steps=25,
                                        rng=random.Random(seed))
            return result.step_names

    seq_a = run(_go(1))
    seq_b = run(_go(2))
    assert seq_a != seq_b, "two different seeds produced the identical story — not really composed"


def test_a_mobile_request_the_composer_created_can_reach_every_real_terminal_state():
    """A weaker, structural proof that the world-state tracking itself is real: across a long
    enough run, the composer's own choices must have driven at least one request all the way to a
    genuine terminal status (completed, rejected, or no_show) — not just created and abandoned."""

    async def _go():
        async with spawn_operations() as svc:
            steps = build_steps(svc.base_url, TENANT, max_requests=6)
            return await compose_story(steps, world=new_world(), max_steps=60,
                                       rng=random.Random(7))

    result = run(_go())
    terminal = {"completed", "rejected", "no_show"}
    reached = {status for status in result.world["requests"].values() if status in terminal}
    assert reached, f"expected at least one request to reach a terminal state: " \
                    f"{result.world['requests']}"
