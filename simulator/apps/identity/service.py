"""App-specific: spawning a real `platform/services/identity-service` — needed for exactly one
reason in this simulator so far: `services/operations`' own `hire_member` route (the ONLY way to
give an employee a real login tied to a `person_id`, as opposed to the four-digit PIN, which is
attribution only, never authentication — see that route's own docstring) calls out to identity's
internal `POST /internal/tenancy/members` over real HTTP. Branch-scope checks need a REAL
`person_id` a JWT's own `sub` claim can match, so this is not optional infrastructure for that
scenario — it is the actual, real dependency operations has for hiring somebody, spawned the same
way any other real dependency in this simulator is (never mocked).

`IDENTITY_MEMBER_ADD_MODE=password` (rather than the platform's own default, "invite") is a
deliberate simplification: invite mode returns an unusable password and a one-time token that
must then be redeemed in a second real call before the person can sign in at all — real, but
extra infrastructure this scenario does not need to prove (the SAME "each stage adds one real
thing" discipline this whole simulator was built under). Password mode is a real, supported,
documented mode identity-service itself offers, not a shortcut invented here.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from simulator.common.environment import ServiceHandle, run_service
from simulator.shared.service_env import base_env

_SERVICE_DIR = Path(__file__).resolve().parents[3] / "platform" / "services" / "identity-service"


@asynccontextmanager
async def spawn(*, port: int | None = None,
                extra_env: dict[str, str] | None = None) -> AsyncIterator[ServiceHandle]:
    env = {
        **base_env(),
        "IDENTITY_MULTI_TENANT": "true",
        "IDENTITY_MEMBER_ADD_MODE": "password",
        # This simulator never mints a platform-wide '*'/'platform.*' capability on any
        # membership it creates — every scenario is single-tenant test data, never a real
        # multi-tenant deployment — so the boundary `PLATFORM_TENANT` exists to enforce has
        # nothing to protect here. Real deployments must still set PLATFORM_TENANT; this is the
        # documented single-tenant escape hatch identity-service's own config offers instead.
        "IDENTITY_ALLOW_UNBOUNDED_PLATFORM": "true",
        **(extra_env or {}),
    }
    async with run_service("identity-service", app_import="app.main:app", cwd=_SERVICE_DIR,
                           port=port, env=env) as svc:
        yield svc
