"""App-specific (see the README's own taxonomy): how to spawn a REAL `services/reminders` process.

Self-contained the same way loyalty is: no peer required for the doors this session wires in
(customer prefs, the owner's own schedule/rules reads and writes) — the parts of this service that
DO need a peer (visit events over a real bus, operations' own catalogue for display) are simply
out of scope for what is driven here, the same honest split `apps/operations/mutual_benefit_
actions.py` already documents for its own peer-dependent parts.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.auth import env_for_hs256_auth
from simulator.shared.service_env import base_env

# services/reminders, relative to this file: simulator/apps/reminders/service.py -> repo root is 3
# parents up, then into services/reminders.
_SERVICE_DIR = Path(__file__).resolve().parents[3] / "services" / "reminders"


@asynccontextmanager
async def spawn(*, port: int | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    """A REAL services/reminders, booted with the DATASTORE_DRIVER default (in-memory) unless
    `extra_env` overrides it — same convention as `apps/loyalty/service.py::spawn`."""
    env = {**base_env(), **env_for_hs256_auth()}
    env.update(extra_env or {})
    async with run_service("reminders", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
