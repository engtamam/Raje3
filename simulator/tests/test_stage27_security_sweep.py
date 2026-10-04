"""Stage 27: a security sweep across EVERY real app wired into this simulator — the same four
generic checks stage 7 proved once against two operations routes (`common/checks.py`), now run
against a representative real route in each of the ten apps. Each check takes only (method, url,
headers, body) — never an app-specific Action class — so this is genuinely the same code reused
ten times, not ten new checks written to look similar.

ONE REPRESENTATIVE ROUTE PER APP, not every route — a full per-route sweep is `common/rbac_matrix.
py`'s own job (already proven for services/operations' full catalogue in
`tests/test_stage9_rbac_matrix.py`); this sweep's job is breadth ACROSS apps, catching an app whose
auth wiring is subtly different from the others, not depth within one.
"""
from __future__ import annotations

import asyncio

import pytest

from simulator.apps.bookings.service import spawn as spawn_bookings
from simulator.apps.campaigns.service import spawn as spawn_campaigns
from simulator.apps.coworking.service import spawn as spawn_coworking
from simulator.apps.error_collector.service import spawn as spawn_error_collector
from simulator.apps.insights.service import spawn as spawn_insights
from simulator.apps.loyalty.service import spawn as spawn_loyalty
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.apps.referrals.service import spawn as spawn_referrals
from simulator.apps.reminders.service import spawn as spawn_reminders
from simulator.apps.whatsapp_assistant.service import CONNECTOR_API_TOKEN
from simulator.apps.whatsapp_assistant.service import spawn as spawn_whatsapp_assistant
from simulator.common.checks import (
    check_adversarial_input_never_crashes, check_forged_signature_is_refused,
    check_wrong_capability_is_refused,
)
from simulator.shared.auth import auth_header, forged_auth_header

TENANT_A = "sim-sec-a"


def run(coro):
    return asyncio.run(coro)


# Each entry: (app label, spawn fn, method, path builder, real capability the route enforces,
# a hostile body to throw at it if it takes one).
CASES = [
    ("operations", spawn_operations, "GET", "/api/v1/staff/operators", "operations.read", None),
    ("loyalty", spawn_loyalty, "GET", "/api/v1/loyalty/balance/sub-sec-1", "loyalty.read", None),
    ("bookings", spawn_bookings, "GET",
     "/api/v1/bookings?branch_id=branch-1&date=2026-01-01", "bookings.read", None),
    ("reminders", spawn_reminders, "GET", "/api/v1/reminders/schedule", "reminders.read", None),
    ("campaigns", spawn_campaigns, "GET", "/api/v1/campaigns/goals", "campaigns.read", None),
    ("insights", spawn_insights, "GET", "/api/v1/insights/dashboard", "insights.read", None),
    ("referrals", spawn_referrals, "GET", "/api/v1/referrals/campaigns", "referrals.manage", None),
    ("coworking", spawn_coworking, "GET", "/api/v1/coworking/resources", "coworking.manage", None),
    ("error-collector", spawn_error_collector, "GET", "/api/v1/signals",
     "platform.observability", None),
]


@pytest.mark.parametrize("label,spawn_fn,method,path,cap,body", CASES, ids=[c[0] for c in CASES])
def test_a_forged_signature_is_refused_across_every_app(label, spawn_fn, method, path, cap, body):
    async def _go():
        async with spawn_fn() as svc:
            url = f"{svc.base_url}{path}"
            forged = forged_auth_header(tenant=TENANT_A, caps=(cap,))
            return await check_forged_signature_is_refused(
                method=method, url=url, json_body=body, forged_headers=forged)

    result = run(_go())
    assert result.ok, f"{label}: {result.detail}"


@pytest.mark.parametrize("label,spawn_fn,method,path,cap,body", CASES, ids=[c[0] for c in CASES])
def test_a_missing_capability_is_refused_across_every_app(label, spawn_fn, method, path, cap, body):
    async def _go():
        async with spawn_fn() as svc:
            url = f"{svc.base_url}{path}"
            # A REAL, validly-signed token, deliberately holding NO capability at all — the route
            # must refuse it with 403, never let it through for lacking a check.
            headers = auth_header(tenant=TENANT_A, caps=())
            return await check_wrong_capability_is_refused(
                method=method, url=url, json_body=body, headers=headers)

    result = run(_go())
    assert result.ok, f"{label}: {result.detail}"


@pytest.mark.parametrize("label,spawn_fn,method,path,cap,body", CASES, ids=[c[0] for c in CASES])
def test_adversarial_query_and_headers_never_crash_any_app(label, spawn_fn, method, path, cap, body):
    async def _go():
        async with spawn_fn() as svc:
            # An adversarial-shaped value riding along as an EXTRA query param no route reads as
            # real data — proves a hostile caller (injection-shaped strings, odd unicode) never
            # reaches code that assumed it would never see one, without needing a route-specific
            # malformed body. A raw HTTP header cannot legally carry non-ASCII bytes at all (httpx
            # itself refuses to encode one, correctly, per RFC 7230) — a query param is the real,
            # legal place a hostile string actually arrives on the wire.
            import urllib.parse
            headers = auth_header(tenant=TENANT_A, caps=(cap,))
            adversarial = urllib.parse.quote("'; DROP TABLE users; --‮<script>alert(1)")
            sep = "&" if "?" in path else "?"
            url = f"{svc.base_url}{path}{sep}sim_adversarial={adversarial}"
            return await check_adversarial_input_never_crashes(
                method=method, url=url, json_body=body, headers=headers)

    result = run(_go())
    assert result.ok, f"{label}: {result.detail}"


# CROSS-TENANT ISOLATION IS DELIBERATELY NOT SWEPT HERE THE SAME BLANKET WAY. `check_cross_tenant_
# isolation` flags a "leak" on `status==200 and identical body` — the right signal for a route
# answering REAL, distinguishing data, but a false positive for a list-shaped route on two FRESH
# tenants that both legitimately answer the same empty `{"...": []}`. Real per-app cross-tenant
# proofs already exist where they matter and are seeded with real, distinguishing data first:
# `test_stage10_branches.py` (operations), `test_stage24_referrals.py` (referrals) — duplicating a
# shallow, unseeded version here would either need per-app setup this sweep's own "one shared check
# across every app" design intentionally avoids, or risk exactly that false alarm.


def test_whatsapp_assistants_own_connector_door_refuses_a_forged_bearer():
    """The connector door uses a SEPARATE static secret, never a JWT — a distinct auth shape from
    every other app in this sweep, proven separately rather than forced into the same signature
    check the other nine use."""

    async def _go():
        import httpx
        async with spawn_whatsapp_assistant() as svc:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{svc.base_url}/api/v1/connectors/check_consent",
                    json={"tenant": TENANT_A, "from_number": "0500000000",
                         "conversation_id": "conv-sec"},
                    headers={"Authorization": "Bearer wrong-token-entirely"}, timeout=10.0)
                return r.status_code

    status = run(_go())
    assert status == 401, f"a wrong connector token must be refused with 401, got {status}"


def test_whatsapp_assistants_own_connector_door_accepts_the_real_token():
    """The control for the test above — proves the 401 is really about the WRONG token, not the
    route itself being broken."""

    async def _go():
        import httpx
        async with spawn_whatsapp_assistant() as svc:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{svc.base_url}/api/v1/connectors/check_consent",
                    json={"tenant": TENANT_A, "from_number": "0500000000",
                         "conversation_id": "conv-sec"},
                    headers={"Authorization": f"Bearer {CONNECTOR_API_TOKEN}"}, timeout=10.0)
                return r.status_code

    status = run(_go())
    assert status == 200
