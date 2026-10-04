"""App-specific (see the README's own taxonomy): how to spawn a REAL `services/loyalty` process.

A genuinely SECOND real service in the fleet, not another route on operations — proves the
`common/` engine (Fleet, population, background noise, all of it) really is app-agnostic, not
quietly shaped around operations' own conventions because it was the only app that ever exercised
it. Its config guards (`assert_peers_config_ok`/`assert_licence_config_ok`, config.py) only fire
when `ENV=production` — `shared/service_env.py::base_env()` sets `ENV=test`, so this spawns
standalone with no billing/reminders/tenant peer wired in, same as every other app here defaults to
memory/null drivers until a scenario asks for more.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.auth import env_for_hs256_auth
from simulator.shared.service_env import base_env

# services/loyalty, relative to this file: simulator/apps/loyalty/service.py -> repo root is 3
# parents up, then into services/loyalty.
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "services" / "loyalty"


@asynccontextmanager
async def spawn(*, port: int | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    """A REAL services/loyalty, booted with the DATASTORE_DRIVER default (in-memory) unless
    `extra_env` overrides it — same convention as `apps/operations/service.py::spawn`."""
    env = {**base_env(), **env_for_hs256_auth()}
    env.update(extra_env or {})
    async with run_service("loyalty", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
