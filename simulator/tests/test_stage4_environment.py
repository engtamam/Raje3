"""Stage 4 proof: a REAL running process (a real uvicorn server on a real socket), reachable over
real HTTP, guaranteed torn down afterward — plus the two safety primitives, BlastRadius and
RollbackOnFailure, proven on their own (no real process needed for those two; they're pure
Python control-flow, tested directly)."""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from simulator.common.environment import (
    BlastRadius, BlastRadiusViolation, RollbackOnFailure, run_service,
)

TOY_SERVICE_DIR = Path(__file__).parent / "fixtures" / "toy_service"


def run(coro):
    return asyncio.run(coro)


# ── run_service: a real process, real health check, real teardown ──────────────────────────────
def test_a_real_service_actually_boots_and_answers_real_http():
    async def _go():
        async with run_service("toy", app_import="app.main:app", cwd=TOY_SERVICE_DIR) as svc:
            async with httpx.AsyncClient() as client:
                r = await client.get(svc.base_url + "/echo")
                assert r.status_code == 200
                assert "pid" in r.json()
            # the process is genuinely running, not a stub — its own pid is a real OS process
            assert svc.process.poll() is None
            return svc.process
    process = run(_go())
    # torn down after the `with` block exited — the real teardown guarantee, checked AFTER exit.
    assert process.poll() is not None


def test_teardown_still_happens_when_the_caller_raises_inside_the_with_block():
    proc_ref = {}

    async def _wrapped():
        async with run_service("toy", app_import="app.main:app", cwd=TOY_SERVICE_DIR) as svc:
            proc_ref["p"] = svc.process
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        run(_wrapped())
    assert proc_ref["p"].poll() is not None  # torn down even though we raised, not left running


def test_two_concurrent_services_get_different_free_ports_and_dont_collide():
    async def _go():
        async with run_service("toy-a", app_import="app.main:app", cwd=TOY_SERVICE_DIR) as a:
            async with run_service("toy-b", app_import="app.main:app", cwd=TOY_SERVICE_DIR) as b:
                assert a.base_url != b.base_url
                async with httpx.AsyncClient() as client:
                    ra = await client.get(a.base_url + "/echo")
                    rb = await client.get(b.base_url + "/echo")
                assert ra.json()["pid"] != rb.json()["pid"]
    run(_go())


def test_a_genuinely_unreachable_app_import_fails_with_the_real_process_output_attached():
    async def _go():
        async with run_service("broken", app_import="app.no_such_module:app",
                               cwd=TOY_SERVICE_DIR, startup_timeout=3.0):
            pass  # never reached

    with pytest.raises(TimeoutError) as exc_info:
        run(_go())
    assert "own stdout/stderr" in str(exc_info.value)


# ── BlastRadius: a scenario's declared scope, checked against a real action's target tenant ────
def test_blast_radius_allows_its_own_declared_tenant():
    radius = BlastRadius(tenant="shop-a")
    radius.check("shop-a")  # must not raise


def test_blast_radius_refuses_any_other_tenant():
    radius = BlastRadius(tenant="shop-a")
    with pytest.raises(BlastRadiusViolation):
        radius.check("shop-b")


def test_blast_radius_enforced_against_a_real_http_response_from_a_real_service():
    async def _go():
        radius = BlastRadius(tenant="shop-allowed")
        async with run_service("toy", app_import="app.main:app", cwd=TOY_SERVICE_DIR) as svc:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{svc.base_url}/tenants/shop-allowed/widgets")
                radius.check(r.json()["tenant"])  # must not raise

                r2 = await client.post(f"{svc.base_url}/tenants/shop-NOT-allowed/widgets")
                with pytest.raises(BlastRadiusViolation):
                    radius.check(r2.json()["tenant"])
    run(_go())


# ── RollbackOnFailure: runs only on failure, before the exception propagates ────────────────────
def test_rollback_never_runs_on_the_success_path():
    ran = []

    async def _cleanup():
        ran.append("cleanup")

    async def _go():
        async with RollbackOnFailure(_cleanup):
            pass  # nothing goes wrong

    run(_go())
    assert ran == []


def test_rollback_runs_before_the_exception_propagates():
    order = []

    async def _cleanup():
        order.append("cleanup")

    async def _go():
        try:
            async with RollbackOnFailure(_cleanup):
                order.append("body")
                raise ValueError("scenario action failed")
        except ValueError:
            order.append("caller sees it")
            raise

    with pytest.raises(ValueError):
        run(_go())
    assert order == ["body", "cleanup", "caller sees it"]
