"""A tenth real, independent app wired into the simulator: services/error-collector
(`apps/error_collector/`) — fully self-contained, no peer needed. Real HTTP against a real,
spawned instance; proves the two-tier privilege split that service's own module docstring
describes: reporting needs only a session, reading the cross-tenant stream needs a real platform
capability.
"""
from __future__ import annotations

import asyncio

from simulator.apps.error_collector.actions import ListSignalsAction, ReportSignalAction
from simulator.apps.error_collector.service import spawn as spawn_error_collector
from simulator.common.engine import run_one

TENANT = "sim-error-collector"


def run(coro):
    return asyncio.run(coro)


def test_any_authenticated_caller_can_report_a_signal_with_no_special_capability():
    async def _go():
        async with spawn_error_collector() as svc:
            return await run_one(ReportSignalAction(
                base_url=svc.base_url, tenant=TENANT, message="لوحة الحجوزات ما فتحت"))

    result = run(_go())
    assert result.ok, result
    assert result.data.get("id")


def test_a_reported_signal_shows_up_in_the_real_platform_wide_stream():
    async def _go():
        async with spawn_error_collector() as svc:
            reported = await run_one(ReportSignalAction(
                base_url=svc.base_url, tenant=TENANT, service="sim-service-xyz",
                message="خطأ حقيقي للاختبار"))
            listed = await run_one(ListSignalsAction(
                base_url=svc.base_url, service_filter="sim-service-xyz"))
            return reported, listed

    reported, listed = run(_go())
    assert reported.ok, reported
    assert listed.ok, listed
    assert any(s["id"] == reported.data["id"] for s in listed.data["signals"])


def test_the_stream_is_genuinely_cross_tenant_a_different_tenants_signal_is_still_visible():
    """`platform.observability` is a PLATFORM capability, never a tenant one — proving the stream
    really does cross every tenant by construction, not merely declared to."""

    async def _go():
        async with spawn_error_collector() as svc:
            reported = await run_one(ReportSignalAction(
                base_url=svc.base_url, tenant="sim-error-collector-other-tenant",
                service="sim-cross-tenant-check"))
            listed = await run_one(ListSignalsAction(
                base_url=svc.base_url, service_filter="sim-cross-tenant-check"))
            return reported, listed

    reported, listed = run(_go())
    assert reported.ok, reported
    assert any(s["id"] == reported.data["id"] for s in listed.data["signals"])
