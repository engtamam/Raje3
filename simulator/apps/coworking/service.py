"""App-specific (see the README's own taxonomy): how to spawn a REAL `services/coworking` process.

Every admin route still WORKS standalone — an unconfigured `OPERATIONS_SERVICE_URL` reads as
unscoped everywhere `branch_scope` is asked (same lenient default bookings/reminders/loyalty
already take), never a boot failure. A scenario that wants to prove REAL branch narrowing needs a
real Fleet (`ServiceSpec(name="operations", ...)` + `ServiceSpec(name="coworking", spawn=spawn,
needs={"OPERATIONS_SERVICE_URL": "operations"})`) — this spawn recipe already accepts
`extra_env`, so no code change here was needed for that, only the Fleet spec itself.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.auth import env_for_hs256_auth
from simulator.shared.service_env import base_env

_SERVICE_DIR = Path(__file__).resolve().parents[3] / "services" / "coworking"


@asynccontextmanager
async def spawn(*, port: int | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    env = {**base_env(), **env_for_hs256_auth()}
    env.update(extra_env or {})
    async with run_service("coworking", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
