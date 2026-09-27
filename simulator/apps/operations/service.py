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
# THE SAME REAL FILE shared/roles.py already reads — smart-linked the same way: hire()
# (core/signup.py) refuses EVERY role as "غير متاح" unless SIGNUP_ROLES_FILE points at a real
# roles list, and pointing it at the actual seed file (rather than a fixture copy) means a role
# renamed or added there is valid here too, with zero edits to this module.
_ROLES_FILE = _SERVICE_DIR / "data" / "roles.seed.json"


@asynccontextmanager
async def spawn(*, port: int | None = None, identity_url: str | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    """A REAL services/operations, booted with the DATASTORE_DRIVER default (in-memory) unless
    `extra_env` overrides it — memory is fine for proving the mechanism end to end; a scenario
    that wants to hunt a genuine cross-process datastore race needs `DATASTORE_DRIVER=postgres`
    and a real `DATASTORE_DSN` passed in via `extra_env` (see the README's own note on why
    MemoryDataStore's `claim()` never actually races even under real concurrent HTTP).

    `identity_url` wires `IDENTITY_SERVICE_URL` — needed only by scenarios that hire a REAL member
    (a login, not a PIN — see `apps/identity/service.py`'s own module docstring for why branch
    scoping specifically needs this); omitted, `hire_member` simply cannot be used."""
    env = {**base_env(), **env_for_hs256_auth(), "SIGNUP_ROLES_FILE": str(_ROLES_FILE)}
    if identity_url:
        env["IDENTITY_SERVICE_URL"] = identity_url
    env.update(extra_env or {})
    async with run_service("operations", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
