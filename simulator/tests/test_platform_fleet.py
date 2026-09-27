"""Platform-scale infrastructure, piece 1 proof: `common/fleet.py::run_fleet` spawns MULTIPLE
real services together, wired to each other automatically, torn down together — proven against
the SAME two real services `test_stage10_branches.py` already wired by hand (identity +
operations), showing the fleet mechanism produces the identical, working result with none of
that manual base_url-passing.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import pytest

from simulator.apps.identity.service import spawn as spawn_identity
from simulator.apps.operations.actions import CreateBranchAction, HireMemberAction
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one
from simulator.common.fleet import (
    Fleet, FleetCycleError, FleetUnknownDependencyError, ServiceSpec, run_fleet,
)

TENANT = "sim-fleet"


def run(coro):
    return asyncio.run(coro)


def test_two_real_services_spawn_together_healthy_and_wired():
    """The main proof: operations, wired to identity automatically through the fleet's own
    dependency resolution — never a hand-passed `identity_url=` — can actually hire a real
    member end to end, which only succeeds if operations' own IDENTITY_SERVICE_URL genuinely
    points at the real, spawned identity-service."""
    specs = [
        ServiceSpec(name="identity", spawn=spawn_identity),
        ServiceSpec(name="operations", spawn=spawn_operations,
                   needs={"IDENTITY_SERVICE_URL": "identity"}),
    ]

    async def _go():
        async with run_fleet(specs) as fleet:
            assert isinstance(fleet, Fleet)
            ops_url = fleet.url("operations")
            branch = await run_one(CreateBranchAction(
                base_url=ops_url, tenant=TENANT, branch_name="الفرع الرئيسي"))
            assert branch.ok, branch
            hire = await run_one(HireMemberAction(
                base_url=ops_url, tenant=TENANT, phone="0511111111", password="Passw0rd1",
                role="operator", branch_id=branch.data["id"]))
            return fleet, hire

    fleet, hire = run(_go())
    assert hire.ok, hire
    # torn down after the `with` block exited.
    assert fleet.services["identity"].process.poll() is not None
    assert fleet.services["operations"].process.poll() is not None


def test_teardown_happens_for_every_spawned_service_even_if_a_later_one_fails():
    """A fleet that fails PART WAY THROUGH spawning must still tear down whatever it already
    started — the same guarantee a single `run_service` gives, extended across the whole list.

    NOTE ON THE TEST'S OWN SHAPE: when a LATER spec fails to spawn, `run_fleet`'s own `__aenter__`
    never reaches its `yield` — so the caller's `async with run_fleet(...) as fleet:` body never
    runs at all, and `fleet` is never bound. That is correct behaviour, not a bug to work around;
    it just means this test cannot observe "what got spawned" through the `fleet` object the way
    the happy-path test does, and instead captures the handle via a side channel as it is spawned,
    from OUTSIDE the fleet, to check its process state after the fleet's own internal unwind."""
    captured: dict[str, Any] = {}

    @asynccontextmanager
    async def _tracked_identity(*, port=None, extra_env=None):
        async with spawn_identity(port=port, extra_env=extra_env) as handle:
            captured["identity"] = handle
            yield handle

    def _broken_spawn(*, port=None, extra_env=None):
        raise RuntimeError("this service refuses to spawn at all")

    specs = [
        ServiceSpec(name="identity", spawn=_tracked_identity),
        ServiceSpec(name="broken", spawn=_broken_spawn, needs={"X": "identity"}),
    ]

    async def _go():
        with pytest.raises(RuntimeError):
            async with run_fleet(specs):
                pytest.fail("unreachable — __aenter__ must raise before this body ever runs")

    run(_go())
    assert "identity" in captured
    assert captured["identity"].process.poll() is not None, (
        "identity was already up when 'broken' failed to spawn — it must still be torn down")


def test_an_unknown_dependency_is_refused_before_anything_is_spawned():
    specs = [ServiceSpec(name="operations", spawn=spawn_operations,
                        needs={"IDENTITY_SERVICE_URL": "no-such-service"})]

    async def _go():
        async with run_fleet(specs):
            pass  # never reached

    with pytest.raises(FleetUnknownDependencyError):
        run(_go())


def test_a_circular_dependency_is_refused_before_anything_is_spawned():
    specs = [
        ServiceSpec(name="a", spawn=spawn_identity, needs={"X": "b"}),
        ServiceSpec(name="b", spawn=spawn_identity, needs={"Y": "a"}),
    ]

    async def _go():
        async with run_fleet(specs):
            pass  # never reached

    with pytest.raises(FleetCycleError):
        run(_go())


def test_a_service_with_no_dependencies_spawns_fine_alone_in_a_fleet_of_one():
    specs = [ServiceSpec(name="identity", spawn=spawn_identity)]

    async def _go():
        async with run_fleet(specs) as fleet:
            return fleet.url("identity")

    url = run(_go())
    assert url.startswith("http://127.0.0.1:")
