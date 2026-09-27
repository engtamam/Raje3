"""App-specific (see the README's own taxonomy: `apps/<name>/` — one folder per real service,
knowledge specific to THAT app only) — how to spawn a REAL services/operations process for a
scenario to drive. Nothing here is app-agnostic; `common/environment.py::run_service` is the
general mechanism, this module is just operations' own recipe for using it.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.auth import env_for_hs256_auth
from simulator.shared.service_env import base_env

# services/operations, relative to this file: simulator/apps/operations/service.py -> repo root
# is 3 parents up, then into services/operations.
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "services" / "operations"


@asynccontextmanager
async def spawn(*, port: int | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    """A REAL services/operations, booted with the DATASTORE_DRIVER default (in-memory) unless
    `extra_env` overrides it — memory is fine for proving the mechanism end to end; a scenario
    that wants to hunt a genuine cross-process datastore race needs `DATASTORE_DRIVER=postgres`
    and a real `DATASTORE_DSN` passed in via `extra_env` (see the README's own note on why
    MemoryDataStore's `claim()` never actually races even under real concurrent HTTP)."""
    env = {**base_env(), **env_for_hs256_auth(), **(extra_env or {})}
    async with run_service("operations", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
