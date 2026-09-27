"""App-specific (see the README's own taxonomy): how to spawn a REAL `services/referrals` process
— the global, standalone anonymous-referral-code campaign engine (distinct from
`services/operations`' own affiliate/referral_redemption door already wired in `apps/operations/`).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.auth import env_for_hs256_auth
from simulator.shared.service_env import base_env

_SERVICE_DIR = Path(__file__).resolve().parents[3] / "services" / "referrals"


@asynccontextmanager
async def spawn(*, port: int | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    env = {**base_env(), **env_for_hs256_auth()}
    env.update(extra_env or {})
    async with run_service("referrals", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
