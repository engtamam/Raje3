"""App-specific (see the README's own taxonomy): how to spawn a REAL `services/whatsapp-assistant`
process. The connector door (`app/api/v1/connectors.py`) needs its OWN separate secret,
`CONNECTOR_API_TOKEN` — deliberately never `INTERNAL_SERVICE_TOKEN` (that route's own
`require_connector_token` comment: "a SEPARATE secret ... never INTERNAL_SERVICE_TOKEN") — so this
spawn recipe mints one, exposed as a module constant the same way `shared/service_env.py` exposes
`INTERNAL_SERVICE_TOKEN`, for an Action to use directly rather than guess.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.auth import env_for_hs256_auth
from simulator.shared.service_env import base_env

_SERVICE_DIR = Path(__file__).resolve().parents[3] / "services" / "whatsapp-assistant"

# 32+ chars, same minimum this service's own config.py enforces in production — kept obviously
# fake, the same discipline `shared/auth.py::SECRET` already documents for its own constant.
CONNECTOR_API_TOKEN = "simulator-connector-token-" + "z" * 20


@asynccontextmanager
async def spawn(*, port: int | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    env = {**base_env(), **env_for_hs256_auth(), "CONNECTOR_API_TOKEN": CONNECTOR_API_TOKEN}
    env.update(extra_env or {})
    async with run_service("whatsapp-assistant", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
