"""Stage 13: generating Actions FROM a route's own schema instead of hand-writing one per route —
the answer to "why do we write the scenario, can't the simulator understand the app and generate
the actions itself?" (see the README's own section on `common/autogen.py` for the scope this
covers and does not).
"""
from __future__ import annotations

import asyncio

from simulator.apps.operations.service import _SERVICE_DIR
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.autogen import autogen_actions, fetch_openapi, generate_object
from simulator.common.discovery import discover_actions
from simulator.common.engine import run_one

TENANT = "sim-autogen"


def run(coro):
    return asyncio.run(coro)


def test_the_live_services_own_openapi_is_reachable_in_test_env():
    async def _go():
        async with spawn_operations() as svc:
            return await fetch_openapi(svc.base_url)

    openapi = run(_go())
    assert "paths" in openapi
    assert "/api/v1/field/visits" in openapi["paths"]


def test_a_body_generated_from_the_real_visit_schema_is_accepted_by_the_real_route():
    """The mechanical proof: NOTHING here hand-writes `{"phone": ..., "service_ids": [...]}` — the
    body comes entirely from the real route's own JSON schema, and the real route accepts it."""

    async def _go():
        async with spawn_operations() as svc:
            openapi = await fetch_openapi(svc.base_url)
            op = openapi["paths"]["/api/v1/field/visits"]["post"]
            schema = op["requestBody"]["content"]["application/json"]["schema"]
            body = generate_object(schema, openapi)
            from simulator.shared.auth import auth_header
            import httpx
            headers = auth_header(tenant=TENANT, caps=("operations.record",))
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{svc.base_url}/api/v1/field/visits", json=body,
                                      headers=headers, timeout=10.0)
            return body, r.status_code

    body, status = run(_go())
    assert "phone" in body and "service_ids" in body
    assert status == 201, (body, status)


def test_every_declared_parameterless_route_accepts_its_own_generated_body_without_a_500():
    """The real coverage claim this module makes: run EVERY declared, parameterless route through
    an auto-generated call, against the real service, and require none of them to 500 — the exact
    "does every declared route survive a well-formed call" question Schemathesis asks of a spec."""

    async def _go():
        async with spawn_operations() as svc:
            declared = discover_actions(_SERVICE_DIR)
            actions = await autogen_actions(svc.base_url, declared, tenant=TENANT)
            assert actions, "discovery + autogen must find at least one real, callable route"
            results = []
            for action in actions:
                results.append(await run_one(action))
            return actions, results

    actions, results = run(_go())
    failures = [(a.declared.method, a.declared.path, r.detail)
               for a, r in zip(actions, results) if not r.ok]
    assert not failures, failures
