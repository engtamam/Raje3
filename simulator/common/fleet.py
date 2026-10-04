"""Platform-scale infrastructure, piece 1: running MULTIPLE real services together as one unit,
automatically wired to each other — never a scenario hand-wiring "spawn A, read its base_url,
pass it into B's env" every time it needs two real services at once (exactly what
`test_stage10_branches.py` had to do by hand for operations+identity, and what every future
scenario needing three, four, or more real services together would otherwise repeat).

A `ServiceSpec` is just an app's own `spawn(*, port=None, extra_env=None)` (every app module in
`apps/` already has one shaped this way) plus which OTHER named services' URLs it needs, and under
which env var. `run_fleet` spawns them in DEPENDENCY ORDER (a service that needs another's URL is
started only after that other one is already up and healthy — never a guess about "probably fast
enough"), and tears every one of them down together, in reverse order, the moment the fleet's own
`with` block exits — the SAME teardown guarantee `environment.py::run_service` already gives one
service, extended to however many a scenario asks for.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from .environment import ServiceHandle

# An app's own spawn() — e.g. apps/operations/service.py::spawn — called here only with
# `extra_env=`, since that is the one keyword every app module's spawn() already accepts.
SpawnFn = Callable[..., Any]


class FleetUnknownDependencyError(Exception):
    """A spec names a dependency that is not itself one of the specs being spawned together —
    refused at fleet-build time, before anything is spawned, rather than discovered as a missing
    env var deep inside some OTHER service's own boot failure."""


class FleetCycleError(Exception):
    """Two or more specs need each other, directly or through a chain — there is no valid spawn
    order, and guessing one (e.g. "just start both at once") would silently hand at least one of
    them an empty/wrong URL for whichever it started before."""


@dataclass
class ServiceSpec:
    name: str
    spawn: SpawnFn
    #: {env var name on THIS service: the OTHER service (by its own `name` above) whose base_url
    #: belongs there} — e.g. `{"IDENTITY_SERVICE_URL": "identity"}` for services/operations.
    needs: dict[str, str] = field(default_factory=dict)
    #: Anything else this service's own spawn() should be booted with, merged UNDER the resolved
    #: dependency URLs (a dependency URL always wins if the same key appears in both).
    extra_env: dict[str, str] = field(default_factory=dict)


@dataclass
class Fleet:
    """Every service this fleet spawned, by name, still running — accessible for the rest of a
    scenario's own actions to point their `base_url` at."""

    services: dict[str, ServiceHandle]

    def url(self, name: str) -> str:
        return self.services[name].base_url


def _spawn_order(specs: dict[str, ServiceSpec]) -> list[str]:
    """Dependency-first order (a post-order DFS) — every service a spec `needs` appears earlier
    in the returned list than the spec itself."""
    order: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise FleetCycleError(f"circular dependency involving {name!r}")
        spec = specs.get(name)
        if spec is None:
            raise FleetUnknownDependencyError(f"unknown service {name!r} named as a dependency")
        visiting.add(name)
        for dep_name in spec.needs.values():
            visit(dep_name)
        visiting.discard(name)
        visited.add(name)
        order.append(name)

    for name in specs:
        visit(name)
    return order


@asynccontextmanager
async def run_fleet(specs: list[ServiceSpec]) -> AsyncIterator[Fleet]:
    """Spawn every spec, each only once every service it `needs` is already up, wired
    automatically; yield a `Fleet` naming all of them; tear every one down together (reverse
    order, via `AsyncExitStack`) the moment the `with` block exits — success, failure, or an
    exception raised inside it all take the same path, the same guarantee `run_service` itself
    already gives for one process alone."""
    by_name = {spec.name: spec for spec in specs}
    order = _spawn_order(by_name)

    handles: dict[str, ServiceHandle] = {}
    async with AsyncExitStack() as stack:
        for name in order:
            spec = by_name[name]
            env = dict(spec.extra_env)
            for env_var, dep_name in spec.needs.items():
                # `dep_name` is guaranteed already in `handles` — `_spawn_order` only ever
                # returns an order where every dependency appears before its own dependents.
                env[env_var] = handles[dep_name].base_url
            handle = await stack.enter_async_context(spec.spawn(extra_env=env))
            handles[name] = handle
        yield Fleet(services=handles)
