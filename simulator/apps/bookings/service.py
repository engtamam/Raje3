"""App-specific (see the README's own taxonomy): how to spawn a REAL `services/bookings` process.

UNLIKE loyalty, bookings genuinely CANNOT run standalone for anything beyond its own read routes:
`create()` asks a real peer over HTTP for a service's own duration in minutes
(`POST /internal/operations/service-durations` — operations owns `Service.duration_minutes`,
bookings does not and never imports operations' code, since these services deploy independently).
`operations_url` is therefore not optional the way `apps/operations/service.py`'s own
`identity_url` is — a scenario that wants a real booking created needs a real Fleet
(`ServiceSpec(name="operations", ...)` + `ServiceSpec(name="bookings", spawn=spawn,
needs={"OPERATIONS_SERVICE_URL": "operations"})`), never bookings alone.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.auth import env_for_hs256_auth
from simulator.shared.service_env import base_env

# services/bookings, relative to this file: simulator/apps/bookings/service.py -> repo root is 3
# parents up, then into services/bookings.
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "services" / "bookings"


@asynccontextmanager
async def spawn(*, port: int | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    """A REAL services/bookings. `extra_env["OPERATIONS_SERVICE_URL"]` is what `run_fleet`'s own
    dependency resolution fills in automatically when this spawn is used as a `ServiceSpec` — see
    this module's own docstring for why booking creation needs it wired at all."""
    env = {**base_env(), **env_for_hs256_auth()}
    env.update(extra_env or {})
    async with run_service("bookings", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
